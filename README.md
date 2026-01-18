VectorShift Integrations – HubSpot OAuth Integration

This repository contains the completed solution for the VectorShift Integrations Technical Assessment, which focuses on implementing a HubSpot OAuth 2.0 integration and loading HubSpot items using FastAPI (backend) and React (frontend).

 Features Implemented
HubSpot OAuth Integration

OAuth 2.0 authorization flow implemented using HubSpot APIs

Secure token exchange and refresh handling

Credentials stored and retrieved via Redis

Follows the same structure as existing Airtable and Notion integrations

 HubSpot Data Loading

Fetches HubSpot objects using authenticated API calls

Converts API responses into IntegrationItem objects

Displays fetched items in the UI / logs them to the console

 Frontend Integration

Added HubSpot integration to the UI

OAuth flow triggered directly from the frontend

Consistent UI behavior with existing integrations

 Tech Stack
Backend

Python

FastAPI

Redis

HTTPX

OAuth 2.0

Frontend

React

JavaScript

Fetch API

OAuth Flow Overview

User clicks Connect HubSpot

Redirected to HubSpot authorization page

HubSpot redirects back with authorization code

Backend exchanges code for access & refresh tokens

Tokens stored securely

HubSpot API queried using valid credentials

 HubSpot Items Retrieved

The integration retrieves:

Objects from HubSpot (e.g., contacts, companies)

Maps relevant fields to IntegrationItem

Logs or displays items for validation
