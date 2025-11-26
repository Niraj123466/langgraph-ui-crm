"""
LangGraph agent core for the Zoho MCP proof-of-concept.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from agent_config import (
    GOOGLE_API_KEY,
    ZOHO_MCP_URL,
    ZOHO_CLIENT_ID,
    ZOHO_CLIENT_SECRET,
    ZOHO_REDIRECT_URI,
    ZOHO_SCOPE,
    ZOHO_ACCOUNTS_SERVER,
)
from token_manager import ZohoTokenManager


def _get_auth_headers(
    client_id: str | None = None,
    client_secret: str | None = None,
    redirect_uri: str | None = None,
    scope: str | None = None,
    accounts_server: str | None = None,
) -> Optional[Dict[str, str]]:
    """
    Get authentication headers with a valid access token.

    Args:
        client_id: Optional client ID override
        client_secret: Optional client secret override
        redirect_uri: Optional redirect URI override
        scope: Optional scope override
        accounts_server: Optional accounts server override

    Returns:
        Dictionary with Authorization header, or None if OAuth is not configured
    """
    # Use provided values or fall back to global config
    c_id = client_id or ZOHO_CLIENT_ID
    c_secret = client_secret or ZOHO_CLIENT_SECRET
    r_uri = redirect_uri or ZOHO_REDIRECT_URI or "http://localhost:8080/oauth/callback"
    scp = scope or ZOHO_SCOPE
    acc_server = accounts_server or ZOHO_ACCOUNTS_SERVER

    if not c_id or not c_secret:
        # OAuth not configured, return None (will use URL-based auth if available)
        return None

    try:
        token_manager = ZohoTokenManager(
            client_id=c_id,
            client_secret=c_secret,
            redirect_uri=r_uri,
            scope=scp,
            accounts_server=acc_server,
        )
        access_token = token_manager.get_valid_access_token()
        return {"Authorization": f"Bearer {access_token}"}
    except RuntimeError as e:
        print(f"Warning: Could not get access token: {e}")
        print("Continuing without Bearer token authentication...")
        return None


async def create_mcp_client(
    mcp_url: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    redirect_uri: str | None = None,
    scope: str | None = None,
    accounts_server: str | None = None,
) -> MultiServerMCPClient:
    """
    Create and return a configured MultiServerMCPClient.
    """
    server_name = "zoho_crm"
    
    # Use provided URL or fall back to global config
    url = mcp_url or ZOHO_MCP_URL

    # Get authentication headers if OAuth is configured
    auth_headers = _get_auth_headers(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope,
        accounts_server=accounts_server,
    )

    # Configure the connection with optional auth headers
    connection_config: Dict[str, Any] = {
        "transport": "streamable_http",
        "url": url,
    }

    if auth_headers:
        connection_config["headers"] = auth_headers

    client = MultiServerMCPClient(
        connections={
            server_name: connection_config,
        }
    )
    return client


def create_agent(tools: list, google_api_key: str | None = None) -> Any:
    """
    Create the LangGraph ReAct agent with the given tools.
    """
    api_key = google_api_key or GOOGLE_API_KEY
    
    if not api_key:
        raise ValueError("Google API Key is required. Set GOOGLE_API_KEY env var or provide it explicitly.")

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        api_key=api_key,
        temperature=0,
    )

    agent_app = create_react_agent(llm, tools)
    return agent_app


async def run_conversation(agent_app, prompt: str) -> Dict[str, Any]:
    """
    Stream the agent's reasoning trace and return the final response payload.
    """
    print(">>> Prompt:", prompt)
    print("\n--- Agent Thoughts ---")

    inputs = {"messages": [("user", prompt)]}
    final_response: Dict[str, Any] | None = None

    # Use ainvoke instead of astream_events to avoid pickling issues with MCP tools
    # The event stream tracer tries to deepcopy state which fails with some async objects
    final_response = await agent_app.ainvoke(inputs)

    print("\n--- Conversation Complete ---")
    if final_response:
        messages = final_response.get("messages") or []
        if messages:
            print(messages[-1].content)
        else:
            print(final_response)
    else:
        print("No final response received.")

    return final_response or {}


async def refine_prompt(user_input: str, google_api_key: str | None = None) -> str:
    """
    Uses the LLM to convert raw user input into a clear, actionable prompt for the ReAct agent.
    """
    api_key = google_api_key or GOOGLE_API_KEY
    
    if not api_key:
        raise ValueError("Google API Key is required for prompt refinement.")

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        api_key=api_key,
        temperature=0,
    )
    
    system_prompt = (
        "You are an expert at translating user requests into clear, actionable instructions "
        "for an AI agent that manages Zoho CRM. The agent has tools to search, create, and update "
        "leads, contacts, and deals.\n\n"
        "Convert the user's input into a precise, step-by-step prompt for the agent. "
        "If the user input is already clear, just repeat it. "
        "Do not add any preamble or explanation, just return the refined prompt.\n\n"
        f"User Input: {user_input}"
    )
    
    response = await llm.ainvoke(system_prompt)
    return response.content
