"""
Entry point for the Zoho MCP LangGraph proof-of-concept.
"""

from __future__ import annotations

import asyncio

from agent_config import validate_config
from langchain_mcp_adapters.tools import load_mcp_tools
from agent_core import run_conversation, create_mcp_client, create_agent, refine_prompt


async def main():
    validate_config()

    client = await create_mcp_client()
    server_name = "zoho_crm"

    async with client.session(server_name) as session:
        tools = await load_mcp_tools(
            session,
            connection=client.connections[server_name],
            server_name=server_name,
        )

        agent_app = create_agent(tools)
        
        print("Zoho CRM Agent Ready! (Type 'exit' to quit)")
        print("-" * 50)

        while True:
            try:
                user_input = input("\nYou: ").strip()
                if user_input.lower() in ["exit", "quit"]:
                    print("Goodbye!")
                    break
                
                if not user_input:
                    continue

                print("Processing input...")
                refined_prompt = await refine_prompt(user_input)
                print(f"Refined Prompt: {refined_prompt}")
                
                try:
                    await run_conversation(agent_app, refined_prompt)
                except Exception as e:
                    print(f"Error during conversation: {e}")
                    print("The agent encountered an error but is still running. Please try again.")
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (ConnectionError, OSError, RuntimeError) as exc:
        print("Failed to reach the Zoho MCP server:", exc)


