"""
app/security/oauth_service.py

OAuth 2.1 Authorization Code flow with PKCE.

ADR-021: Pluggable Security — OAuth is one of several auth methods in the
authentication pipeline. It does not replace JWT — it issues JWT tokens after
successful authorization.
"""
import base64
import hashlib
import secrets
import urllib.parse
import uuid
from dataclasses import dataclass
from typing import Optional


@dataclass
class PKCEChallenge:
    """PKCE code verifier/challenge pair (RFC 7636)."""
    code_verifier: str
    code_challenge: str
    code_challenge_method: str = "S256"


@dataclass
class OAuthTokenResponse:
    """OAuth 2.1 token endpoint response."""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 900          # 15 minutes (matches ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    id_token: Optional[str] = None  # Present when openid scope requested


class OAuthService:
    """OAuth 2.1 Authorization Code + PKCE service.

    This implementation provides the protocol mechanics. In production,
    actual authorization code storage and exchange use the DB via
    SecurityRepository.
    """

    # ── PKCE ──────────────────────────────────────────────────────────────────

    @staticmethod
    def generate_pkce() -> PKCEChallenge:
        """Generate a PKCE code_verifier + code_challenge pair."""
        # code_verifier: 43–128 chars from unreserved characters
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
        # code_challenge: BASE64URL(SHA256(code_verifier))
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return PKCEChallenge(code_verifier=verifier, code_challenge=challenge)

    @staticmethod
    def verify_pkce(code_verifier: str, code_challenge: str) -> bool:
        """Verify that code_verifier produces code_challenge (S256 method)."""
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return secrets.compare_digest(expected, code_challenge)

    # ── Authorization URL ──────────────────────────────────────────────────────

    @staticmethod
    def build_authorization_url(
        authorization_endpoint: str,
        client_id: str,
        redirect_uri: str,
        state: str,
        code_challenge: str,
        scope: str = "openid profile email",
        code_challenge_method: str = "S256",
    ) -> str:
        """Build the OAuth 2.1 authorization request URL."""
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
        }
        return f"{authorization_endpoint}?{urllib.parse.urlencode(params)}"

    # ── Token Exchange ─────────────────────────────────────────────────────────

    @staticmethod
    def build_token_request(
        code: str,
        code_verifier: str,
        client_id: str,
        redirect_uri: str,
    ) -> dict:
        """Build the token endpoint POST body for code exchange."""
        return {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": code_verifier,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
        }

    @staticmethod
    def build_refresh_request(refresh_token: str, client_id: str) -> dict:
        """Build the token endpoint POST body for token refresh (rotation)."""
        return {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }

    @staticmethod
    def generate_state() -> str:
        """Generate a CSRF-prevention state value."""
        return secrets.token_urlsafe(32)
