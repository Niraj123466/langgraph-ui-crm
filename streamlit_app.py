import streamlit as st
import asyncio
import asyncio
import os
import traceback
from agent_core import create_mcp_client, create_agent, run_conversation, refine_prompt
from token_manager import ZohoTokenManager
from langchain_mcp_adapters.tools import load_mcp_tools

# Page config
st.set_page_config(page_title="CRM Agent", page_icon="🤖", layout="wide")

st.title("🤖 Generic CRM Agent")

# Sidebar for Configuration
with st.sidebar:
    st.header("🔌 Connection Setup")
    
    crm_type = st.selectbox("CRM Type", ["Zoho CRM", "HubSpot (Coming Soon)", "Salesforce (Coming Soon)"])
    
    with st.expander("Credentials", expanded=True):
        google_api_key = st.text_input("Google API Key", type="password", help="Gemini API Key")
        client_id = st.text_input("Client ID", type="password", help="Zoho OAuth Client ID")
        client_secret = st.text_input("Client Secret", type="password", help="Zoho OAuth Client Secret")
        mcp_url = st.text_input("MCP Server URL", value="http://localhost:8000/sse", help="URL of the running MCP server")
        redirect_uri = st.text_input("Redirect URI", value="http://localhost:8501", help="Streamlit app URL (usually http://localhost:8501)")
        
    st.info("Ensure your Zoho App Redirect URI matches the one above.")

# Session State Initialization
if "messages" not in st.session_state:
    st.session_state.messages = []

if "auth_status" not in st.session_state:
    st.session_state.auth_status = "unauthenticated" # unauthenticated, authorized, authenticated

if "token_data" not in st.session_state:
    st.session_state.token_data = None

# Authentication Logic
def authenticate():
    if not client_id or not client_secret:
        st.error("Please provide Client ID and Client Secret.")
        return

    try:
        # Initialize token manager with dynamic credentials
        token_manager = ZohoTokenManager(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope="ZohoCRM.modules.ALL", # Default scope
            accounts_server="https://accounts.zoho.com"
        )
        
        # Check if we have a valid token already (maybe from previous run or local file if we want to support that, 
        # but for this dynamic UI, we might want to force fresh auth or check if the credentials match the stored ones.
        # For simplicity, let's rely on the flow.)
        
        # If we have an auth code from the URL query params
        query_params = st.query_params
        if "code" in query_params:
            code = query_params["code"]
            with st.spinner("Exchanging code for tokens..."):
                try:
                    token_data = token_manager.exchange_code_for_tokens(code)
                    st.session_state.token_data = token_data
                    st.session_state.auth_status = "authenticated"
                    st.success("Authentication successful!")
                    # Clear query params to clean up URL
                    st.query_params.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Authentication failed: {e}")
        else:
            # Generate Auth URL
            auth_url = token_manager.get_authorization_url()
            st.markdown(f"[**Click here to Authorize with Zoho**]({auth_url})")
            st.caption("After authorization, you will be redirected back to this page.")
            
            st.divider()
            st.markdown("### Manual Entry")
            st.caption("If you are not redirected automatically, copy the full URL you were redirected to and paste it here:")
            
            manual_url = st.text_input("Paste Redirect URL or Code", key="manual_url_input")
            if st.button("Authenticate with Code"):
                if manual_url:
                    # Extract code from URL or use as is
                    code_to_exchange = manual_url
                    if "code=" in manual_url:
                        from urllib.parse import parse_qs, urlparse
                        try:
                            parsed = urlparse(manual_url)
                            qs = parse_qs(parsed.query)
                            if "code" in qs:
                                code_to_exchange = qs["code"][0]
                        except:
                            pass
                    
                    with st.spinner("Exchanging code for tokens..."):
                        try:
                            token_data = token_manager.exchange_code_for_tokens(code_to_exchange)
                            st.session_state.token_data = token_data
                            st.session_state.auth_status = "authenticated"
                            st.success("Authentication successful!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Authentication failed: {e}")

    except Exception as e:
        st.error(f"Error initializing auth: {e}")

# Main Interface
if st.session_state.auth_status != "authenticated":
    st.warning("Please connect to your CRM to start.")
    authenticate()
else:
    st.success("✅ Connected to Zoho CRM")
    
    # Chat Interface
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("What would you like to do?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            async def process_request():
                try:
                    # Create client with dynamic credentials
                    client = await create_mcp_client(
                        mcp_url=mcp_url,
                        client_id=client_id,
                        client_secret=client_secret,
                        redirect_uri=redirect_uri
                    )
                    
                    server_name = "zoho_crm"
                    async with client.session(server_name) as session:
                        tools = await load_mcp_tools(
                            session,
                            connection=client.connections[server_name],
                            server_name=server_name,
                        )
                        
                        agent_app = create_agent(tools, google_api_key=google_api_key)
                        
                        # Refine prompt
                        refined_prompt = await refine_prompt(prompt, google_api_key=google_api_key)
                        message_placeholder.markdown(f"*Thinking: {refined_prompt}*")
                        
                        # Run conversation
                        # Note: run_conversation prints to stdout, we might want to capture that or modify it to yield
                        # For now, we'll just get the final response.
                        response = await run_conversation(agent_app, refined_prompt)
                        
                        final_msg = "I couldn't get a response."
                        if response and "messages" in response:
                            final_msg = response["messages"][-1].content
                        
                        return final_msg

                except Exception as e:
                    return f"Error: {e}\n\nTraceback:\n{traceback.format_exc()}"

            # Run async loop
            response_text = asyncio.run(process_request())
            message_placeholder.markdown(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text})

