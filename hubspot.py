# hubspot.py

import json
import secrets
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import asyncio
import base64
import requests
from integrations.integration_item import IntegrationItem

from redis_client import add_key_value_redis, get_value_redis, delete_key_redis

# HubSpot App credentials
CLIENT_ID = 'ae5d32f9-61b7-432e-9a18-f6656c21bfa0'
CLIENT_SECRET = '4d635b15-84cf-41e5-b32c-3377faa2702b'

REDIRECT_URI = 'http://localhost:8000/integrations/hubspot/oauth2callback'
authorization_url = f'https://app.hubspot.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}'

# HubSpot scopes for CRM access
scope = 'crm.objects.contacts.read crm.objects.companies.read'


async def authorize_hubspot(user_id, org_id):
    """
    Step 1 of OAuth Flow:
    Creates a state token, stores it in Redis, and returns the authorization URL.
    The user will be redirected to HubSpot to authorize the app.
    """
    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id
    }
    encoded_state = base64.urlsafe_b64encode(json.dumps(state_data).encode('utf-8')).decode('utf-8')
    
    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', json.dumps(state_data), expire=600)

    auth_url = f'{authorization_url}&state={encoded_state}&scope={scope}'
    return auth_url


async def oauth2callback_hubspot(request: Request):
    """
    Step 2 of OAuth Flow:
    HubSpot redirects back with an authorization code.
    We validate the state, exchange the code for tokens, and store credentials in Redis.
    """
    if request.query_params.get('error'):
        raise HTTPException(status_code=400, detail=request.query_params.get('error_description'))
    
    code = request.query_params.get('code')
    encoded_state = request.query_params.get('state')
    state_data = json.loads(base64.urlsafe_b64decode(encoded_state).decode('utf-8'))

    original_state = state_data.get('state')
    user_id = state_data.get('user_id')
    org_id = state_data.get('org_id')

    saved_state = await get_value_redis(f'hubspot_state:{org_id}:{user_id}')

    if not saved_state or original_state != json.loads(saved_state).get('state'):
        raise HTTPException(status_code=400, detail='State does not match.')

    async with httpx.AsyncClient() as client:
        response, _ = await asyncio.gather(
            client.post(
                'https://api.hubapi.com/oauth/v1/token',
                data={
                    'grant_type': 'authorization_code',
                    'client_id': CLIENT_ID,
                    'client_secret': CLIENT_SECRET,
                    'redirect_uri': REDIRECT_URI,
                    'code': code,
                },
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
            ),
            delete_key_redis(f'hubspot_state:{org_id}:{user_id}'),
        )

    await add_key_value_redis(f'hubspot_credentials:{org_id}:{user_id}', json.dumps(response.json()), expire=600)
    
    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)


async def get_hubspot_credentials(user_id, org_id):
    """
    Retrieves stored HubSpot OAuth credentials from Redis.
    Used before making any HubSpot API calls.
    """
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    credentials = json.loads(credentials)
    await delete_key_redis(f'hubspot_credentials:{org_id}:{user_id}')

    return credentials


def create_integration_item_metadata_object(response_json: dict, item_type: str) -> IntegrationItem:
    """
    Converts raw HubSpot API response objects into a standardized IntegrationItem.
    This normalization allows uniform handling of data from different integrations.
    """
    properties = response_json.get('properties', {})
    
    # Get name based on object type
    if item_type == 'contact':
        firstname = properties.get('firstname', '')
        lastname = properties.get('lastname', '')
        name = f"{firstname} {lastname}".strip() or properties.get('email', f"Contact {response_json.get('id')}")
    elif item_type == 'company':
        name = properties.get('name', f"Company {response_json.get('id')}")
    else:
        name = f"{item_type.capitalize()} {response_json.get('id')}"

    integration_item_metadata = IntegrationItem(
        id=response_json.get('id'),
        type=item_type,
        name=name,
        creation_time=properties.get('createdate'),
        last_modified_time=properties.get('hs_lastmodifieddate'),
        parent_id=None,
    )

    return integration_item_metadata


async def get_items_hubspot(credentials) -> list[IntegrationItem]:
    """
    Fetches data from HubSpot using stored OAuth credentials.
    Retrieves contacts and companies from the CRM API.
    Returns a unified list of IntegrationItem objects.
    """
    credentials = json.loads(credentials)
    access_token = credentials.get('access_token')
    headers = {'Authorization': f'Bearer {access_token}'}
    
    list_of_integration_item_metadata = []

    # Fetch contacts
    contacts_url = 'https://api.hubapi.com/crm/v3/objects/contacts'
    contacts_response = requests.get(
        contacts_url,
        headers=headers,
        params={'properties': 'firstname,lastname,email,createdate,hs_lastmodifieddate'}
    )
    
    if contacts_response.status_code == 200:
        contacts = contacts_response.json().get('results', [])
        for contact in contacts:
            list_of_integration_item_metadata.append(
                create_integration_item_metadata_object(contact, 'contact')
            )

    # Fetch companies
    companies_url = 'https://api.hubapi.com/crm/v3/objects/companies'
    companies_response = requests.get(
        companies_url,
        headers=headers,
        params={'properties': 'name,createdate,hs_lastmodifieddate'}
    )
    
    if companies_response.status_code == 200:
        companies = companies_response.json().get('results', [])
        for company in companies:
            list_of_integration_item_metadata.append(
                create_integration_item_metadata_object(company, 'company')
            )

    print(f'HubSpot Integration Items: {list_of_integration_item_metadata}')
    return list_of_integration_item_metadata