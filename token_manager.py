"""
OAuth token manager for Zoho CRM with automatic refresh.

This module handles OAuth 2.0 token acquisition and automatic refresh
so tokens never expire. It stores tokens securely and refreshes them
before expiration, requiring manual authentication only once.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx


class ZohoTokenManager:
    """
    Manages Zoho OAuth tokens with automatic refresh.

    Tokens are stored in a local file and automatically refreshed
    before expiration, ensuring continuous access without manual intervention.
    """

    TOKEN_FILE = Path(".tokens.json")
    TOKEN_REFRESH_BUFFER_SECONDS = 300  # Refresh 5 minutes before expiry

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scope: str = "ZohoCRM.modules.ALL",
        accounts_server: str = "https://accounts.zoho.com",
    ):
        """
        Initialize the token manager.

        Args:
            client_id: Zoho OAuth client ID
            client_secret: Zoho OAuth client secret
            redirect_uri: OAuth redirect URI (must match Zoho app config)
            scope: OAuth scope (default: full CRM access)
            accounts_server: Zoho accounts server URL
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scope = scope
        self.accounts_server = accounts_server.rstrip("/")
        self.token_data: Optional[Dict[str, Any]] = None
        self._load_tokens()

    def _load_tokens(self) -> None:
        """Load tokens from the local storage file."""
        if self.TOKEN_FILE.exists():
            try:
                with open(self.TOKEN_FILE, "r") as f:
                    self.token_data = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load tokens from {self.TOKEN_FILE}: {e}")
                self.token_data = None

    def _save_tokens(self, token_data: Dict[str, Any]) -> None:
        """Save tokens to the local storage file."""
        self.token_data = token_data
        try:
            with open(self.TOKEN_FILE, "w") as f:
                json.dump(token_data, f, indent=2)
            # Set restrictive file permissions (owner read/write only)
            os.chmod(self.TOKEN_FILE, 0o600)
        except IOError as e:
            raise RuntimeError(f"Failed to save tokens: {e}") from e

    def get_authorization_url(self) -> str:
        """
        Generate the OAuth authorization URL for initial authentication.

        Returns:
            URL to visit in a browser to authorize the application
        """
        params = {
            "scope": self.scope,
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "access_type": "offline",
        }
        return f"{self.accounts_server}/oauth/v2/auth?{urlencode(params)}"

    def exchange_code_for_tokens(self, authorization_code: str) -> Dict[str, Any]:
        """
        Exchange an authorization code for access and refresh tokens.

        Args:
            authorization_code: Authorization code from OAuth callback

        Returns:
            Token data dictionary with access_token, refresh_token, expires_in, etc.
        """
        url = f"{self.accounts_server}/oauth/v2/token"
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "code": authorization_code,
        }

        with httpx.Client() as client:
            response = client.post(url, data=data)
            response.raise_for_status()
            token_data = response.json()

        # Add expiration timestamp for easier checking
        token_data["expires_at"] = time.time() + token_data.get("expires_in", 3600)
        self._save_tokens(token_data)
        return token_data

    def refresh_access_token(self) -> Dict[str, Any]:
        """
        Refresh the access token using the refresh token.

        Returns:
            Updated token data with new access_token and expires_at

        Raises:
            RuntimeError: If refresh token is missing or refresh fails
        """
        if not self.token_data or "refresh_token" not in self.token_data:
            raise RuntimeError(
                "No refresh token available. Please run initial OAuth flow."
            )

        url = f"{self.accounts_server}/oauth/v2/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.token_data["refresh_token"],
        }

        with httpx.Client() as client:
            response = client.post(url, data=data)
            response.raise_for_status()
            new_token_data = response.json()

        # Preserve refresh token if not returned (some providers don't return it)
        if "refresh_token" not in new_token_data:
            new_token_data["refresh_token"] = self.token_data["refresh_token"]

        # Update expiration timestamp
        new_token_data["expires_at"] = time.time() + new_token_data.get(
            "expires_in", 3600
        )
        self._save_tokens(new_token_data)
        return new_token_data

    def get_valid_access_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.

        This method ensures the token is always valid by automatically
        refreshing it before expiration. This is the main method to use
        for getting tokens in your application.

        Returns:
            Valid access token string

        Raises:
            RuntimeError: If tokens are missing or refresh fails
        """
        if not self.token_data or "access_token" not in self.token_data:
            raise RuntimeError(
                "No access token available. Please run initial OAuth flow:\n"
                f"1. Visit: {self.get_authorization_url()}\n"
                "2. Authorize the application\n"
                "3. Copy the 'code' parameter from the redirect URL\n"
                "4. Call exchange_code_for_tokens(code)"
            )

        # Check if token needs refresh (with buffer time)
        expires_at = self.token_data.get("expires_at", 0)
        current_time = time.time()
        buffer_time = expires_at - self.TOKEN_REFRESH_BUFFER_SECONDS

        if current_time >= buffer_time:
            print("Access token expired or expiring soon. Refreshing...")
            self.refresh_access_token()

        return self.token_data["access_token"]

    def is_authenticated(self) -> bool:
        """
        Check if valid tokens are available.

        Returns:
            True if tokens exist and are valid, False otherwise
        """
        try:
            self.get_valid_access_token()
            return True
        except RuntimeError:
            return False



