"""
One-time OAuth setup script for Zoho CRM authentication.

This script helps you complete the initial OAuth flow to obtain
refresh tokens. After running this once, tokens will automatically
refresh forever without manual intervention.
"""

from __future__ import annotations

import sys
from urllib.parse import parse_qs, urlparse

from agent_config import (
    ZOHO_CLIENT_ID,
    ZOHO_CLIENT_SECRET,
    ZOHO_REDIRECT_URI,
    ZOHO_SCOPE,
    ZOHO_ACCOUNTS_SERVER,
    validate_oauth_config,
)
from token_manager import ZohoTokenManager


def main():
    """Run the OAuth setup flow."""
    print("Zoho OAuth Setup - One-time authentication\n")
    print("=" * 60)

    # Validate configuration
    try:
        validate_oauth_config()
    except RuntimeError as e:
        print(f"Error: {e}\n")
        print(
            "Please set the following environment variables in your .env file:\n"
            "  - ZOHO_CLIENT_ID\n"
            "  - ZOHO_CLIENT_SECRET\n"
            "  - ZOHO_REDIRECT_URI (optional, defaults to http://localhost:8080/oauth/callback)\n"
        )
        sys.exit(1)

    # Initialize token manager
    token_manager = ZohoTokenManager(
        client_id=ZOHO_CLIENT_ID,
        client_secret=ZOHO_CLIENT_SECRET,
        redirect_uri=ZOHO_REDIRECT_URI,
        scope=ZOHO_SCOPE,
        accounts_server=ZOHO_ACCOUNTS_SERVER,
    )

    # Check if already authenticated
    if token_manager.is_authenticated():
        print("✓ You are already authenticated!")
        print("Tokens are stored and will automatically refresh.\n")
        return

    # Step 1: Generate authorization URL
    auth_url = token_manager.get_authorization_url()
    print("\nStep 1: Authorize the application")
    print("-" * 60)
    print(f"Visit this URL in your browser:\n\n{auth_url}\n")
    print(
        "After authorizing, you will be redirected to your redirect URI.\n"
        "Copy the full redirect URL (including the 'code' parameter).\n"
    )

    # Step 2: Get authorization code from user
    redirect_url = input("Paste the full redirect URL here: ").strip()

    if not redirect_url:
        print("Error: No URL provided.")
        sys.exit(1)

    # Extract authorization code from redirect URL
    try:
        parsed = urlparse(redirect_url)
        query_params = parse_qs(parsed.query)
        if "code" not in query_params:
            raise ValueError("No 'code' parameter found in redirect URL")
        auth_code = query_params["code"][0]
    except Exception as e:
        print(f"Error: Could not extract authorization code from URL: {e}")
        print("\nThe redirect URL should look like:")
        print(f"{ZOHO_REDIRECT_URI}?code=YOUR_AUTHORIZATION_CODE")
        sys.exit(1)

    # Step 3: Exchange code for tokens
    print("\nStep 2: Exchanging authorization code for tokens...")
    print("-" * 60)
    try:
        token_data = token_manager.exchange_code_for_tokens(auth_code)
        print("✓ Successfully obtained tokens!")
        print(f"  - Access token expires in: {token_data.get('expires_in', 'unknown')} seconds")
        print(f"  - Refresh token obtained: {'Yes' if 'refresh_token' in token_data else 'No'}")
        print("\nTokens have been saved and will automatically refresh.")
        print("You will not need to run this setup again.\n")
    except Exception as e:
        print(f"Error: Failed to exchange code for tokens: {e}")
        print("\nPlease check:")
        print("  1. Your CLIENT_ID and CLIENT_SECRET are correct")
        print("  2. The redirect URI matches your Zoho app configuration")
        print("  3. The authorization code hasn't expired")
        sys.exit(1)


if __name__ == "__main__":
    main()

