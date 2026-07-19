"""
app/security/oidc_service.py

OpenID Connect 1.0 service.

Provides ID token issuance, UserInfo responses, and discovery document
generation on top of the existing JWT infrastructure.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt

from app.core.config import settings


_OIDC_ISSUER = "https://api.hireai.io"   # Override via settings in production


class OIDCService:
    """OpenID Connect token and discovery document service."""

    @staticmethod
    def build_id_token(
        subject: str,          # user_id as string
        audience: str,         # client_id
        nonce: Optional[str],
        email: Optional[str] = None,
        name: Optional[str] = None,
        organization_id: Optional[str] = None,
        expires_in: int = 3600,
    ) -> str:
        """Issue a signed OIDC ID token (JWT).

        Standard claims per OIDC Core 1.0 section 2.
        """
        now = datetime.now(timezone.utc)
        payload: Dict[str, Any] = {
            "iss": _OIDC_ISSUER,
            "sub": subject,
            "aud": audience,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
            "jti": str(uuid.uuid4()),
        }
        if nonce:
            payload["nonce"] = nonce
        if email:
            payload["email"] = email
        if name:
            payload["name"] = name
        if organization_id:
            payload["org_id"] = organization_id

        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def validate_id_token(
        token: str,
        audience: str,
        nonce: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate an ID token and return decoded claims.

        Raises jwt.InvalidTokenError on failure.
        """
        claims = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            audience=audience,
        )
        if claims.get("iss") != _OIDC_ISSUER:
            raise jwt.InvalidIssuerError("ID token issuer mismatch")
        if nonce and claims.get("nonce") != nonce:
            raise jwt.DecodeError("ID token nonce mismatch")
        return claims

    @staticmethod
    def get_userinfo(
        user_id: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a UserInfo endpoint response per OIDC Core 5.3."""
        info: Dict[str, Any] = {"sub": user_id}
        if email:
            info["email"] = email
        if name:
            info["name"] = name
        if organization_id:
            info["org_id"] = organization_id
        return info

    @staticmethod
    def discovery_document(base_url: str = _OIDC_ISSUER) -> Dict[str, Any]:
        """Return the OpenID Connect Discovery 1.0 document (.well-known/openid-configuration)."""
        return {
            "issuer": base_url,
            "authorization_endpoint": f"{base_url}/api/v1/security/oauth/authorize",
            "token_endpoint": f"{base_url}/api/v1/security/oauth/token",
            "userinfo_endpoint": f"{base_url}/api/v1/security/oidc/userinfo",
            "jwks_uri": f"{base_url}/api/v1/security/oidc/jwks",
            "response_types_supported": ["code"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": [settings.ALGORITHM],
            "scopes_supported": ["openid", "profile", "email"],
            "token_endpoint_auth_methods_supported": ["none"],
            "code_challenge_methods_supported": ["S256"],
            "claims_supported": ["sub", "iss", "aud", "exp", "iat", "email", "name", "org_id"],
        }
