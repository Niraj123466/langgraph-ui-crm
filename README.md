# Zoho MCP LangGraph Agent (POC)

This proof of concept wires a LangGraph ReAct agent to a Zoho Model Context Protocol (MCP) server so the agent can call Zoho CRM tools (create leads, search contacts, etc.) when appropriate.

## Prerequisites

- Python 3.11+
- Active Zoho MCP server deployment with Zoho CRM tools enabled
- Google Generative AI API key (Gemini 2.5 Flash)

## Environment Variables

Create a `.env` file in the project root or export the variables in your shell:

### Required Variables

```
ZOHO_MCP_URL=<copy from Zoho MCP console>
GOOGLE_API_KEY=<your Gemini API key>
```

- `ZOHO_MCP_URL`: in the Zoho MCP Console, open your server, go to **Connect → HTTP**, and copy the streaming URL.
- `GOOGLE_API_KEY`: generate from Google AI Studio and ensure the Gemini 2.5 Flash model is enabled for the project.

### Optional: OAuth Token Authentication (Recommended)

For automatic token refresh (tokens never expire), add these OAuth credentials:

```
ZOHO_CLIENT_ID=<your Zoho OAuth client ID>
ZOHO_CLIENT_SECRET=<your Zoho OAuth client secret>
ZOHO_REDIRECT_URI=http://localhost:8080/oauth/callback
ZOHO_SCOPE=ZohoCRM.modules.ALL
ZOHO_ACCOUNTS_SERVER=https://accounts.zoho.com
```

- `ZOHO_CLIENT_ID` & `ZOHO_CLIENT_SECRET`: Create a Zoho OAuth app at https://api-console.zoho.com/
- `ZOHO_REDIRECT_URI`: Must match the redirect URI configured in your Zoho OAuth app
- `ZOHO_SCOPE`: OAuth scope (default: full CRM access)
- `ZOHO_ACCOUNTS_SERVER`: Zoho accounts server (default: `https://accounts.zoho.com`, use `https://accounts.zoho.eu` for EU, `https://accounts.zoho.in` for India)

> The sample URL in `agent_config.py` is a placeholder. Replace it with your own endpoint.

## Installation

```bash
cd /Users/nirajvaijinathmore/Desktop/dev/langgraph-zoho-mcp/zoho_mcp_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## OAuth Setup (One-Time, Required for Token Refresh)

If you've configured OAuth credentials, run the one-time setup to obtain refresh tokens:

```bash
python setup_oauth.py
```

This script will:
1. Generate an authorization URL for you to visit
2. Guide you through the OAuth flow
3. Exchange the authorization code for access and refresh tokens
4. Save tokens to `.tokens.json` (automatically refreshed forever)

**After this one-time setup, tokens will automatically refresh before expiration. You will never need to manually authenticate again.**

### Creating a Zoho OAuth App

1. Go to https://api-console.zoho.com/
2. Click "Add Client" → "Server-based Applications"
3. Configure:
   - **Client Name**: Your app name
   - **Homepage URL**: `http://localhost:8080` (or your domain)
   - **Authorized Redirect URIs**: `http://localhost:8080/oauth/callback` (must match `ZOHO_REDIRECT_URI`)
4. Copy the **Client ID** and **Client Secret** to your `.env` file

## Running the POC

```bash
python main.py
```

The script:

1. Loads env vars through `agent_config.py`.
2. **Automatically refreshes OAuth tokens if configured** (ensures tokens never expire).
3. Connects to the Zoho MCP server via `MultiServerMCPClient` with authentication headers.
4. Discovers all Zoho CRM tools using `load_mcp_tools`.
5. Spins up a LangGraph ReAct agent backed by Gemini 2.5 Flash (via `ChatGoogleGenerativeAI`).
6. Sends an actionable Zoho CRM prompt and streams the reasoning + final answer.

Ensure your Zoho MCP server is running; otherwise, the script will exit with a connection error.

## Token Management

The `token_manager.py` module handles all OAuth token operations:

- **Automatic Refresh**: Tokens are refreshed 5 minutes before expiration
- **Secure Storage**: Tokens are stored in `.tokens.json` with restrictive file permissions (600)
- **Zero Manual Intervention**: After initial setup, tokens refresh automatically forever

If you need to re-authenticate (e.g., after revoking access), simply delete `.tokens.json` and run `setup_oauth.py` again.


