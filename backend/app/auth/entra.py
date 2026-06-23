"""
Microsoft Entra ID bearer-token validation.

Every ``/api`` route depends on :func:`get_principal`, which:

1. reads the ``Authorization: Bearer <jwt>`` header,
2. fetches the tenant signing keys (JWKS, cached by ``PyJWKClient``),
3. verifies the token signature, audience and issuer, and
4. returns a :class:`Principal` identifying the caller.

When ``ENTRA_AUTH_ENABLED`` is ``false`` (local development) validation is
skipped and a stable development principal is returned, so the app runs
without an app registration while remaining fully wired for production.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

logger = logging.getLogger(__name__)

# Stable id used for all requests when auth is disabled (local dev).
DEV_PRINCIPAL_ID = "00000000-0000-0000-0000-000000000001"

_bearer = HTTPBearer(auto_error=False)
_jwk_client: "jwt.PyJWKClient | None" = None


@dataclass
class Principal:
    """An authenticated caller."""

    id: str
    name: str
    username: str

    @property
    def is_dev(self) -> bool:
        return self.id == DEV_PRINCIPAL_ID


def _dev_principal() -> Principal:
    return Principal(id=DEV_PRINCIPAL_ID, name="Local Developer", username="dev@localhost")


def _accepted_audiences(settings) -> list[str]:
    auds: list[str] = []
    if settings.entra_api_audience:
        auds.append(settings.entra_api_audience)
        if not settings.entra_api_audience.startswith("api://"):
            auds.append(f"api://{settings.entra_api_audience}")
    auds.extend(settings.entra_additional_audiences)
    return auds


def _accepted_issuers(settings) -> set[str]:
    tid = settings.entra_tenant_id
    return {
        f"https://login.microsoftonline.com/{tid}/v2.0",
        f"https://sts.windows.net/{tid}/",
    }


def _get_jwk_client(settings) -> "jwt.PyJWKClient":
    global _jwk_client
    if _jwk_client is None:
        url = (
            f"https://login.microsoftonline.com/"
            f"{settings.entra_tenant_id}/discovery/v2.0/keys"
        )
        _jwk_client = jwt.PyJWKClient(url)
    return _jwk_client


def validate_token(token: str) -> Principal:
    """Validate a raw JWT string and return the caller principal."""
    settings = get_settings()
    try:
        signing_key = _get_jwk_client(settings).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=_accepted_audiences(settings) or None,
            options={"verify_aud": bool(_accepted_audiences(settings))},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Token validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    issuer = claims.get("iss", "")
    if issuer not in _accepted_issuers(settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Untrusted token issuer",
            headers={"WWW-Authenticate": "Bearer"},
        )

    oid = claims.get("oid") or claims.get("sub")
    if not oid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject")

    return Principal(
        id=str(oid),
        name=claims.get("name", ""),
        username=claims.get("preferred_username") or claims.get("upn") or "",
    )


async def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    """FastAPI dependency: resolve the authenticated principal."""
    settings = get_settings()
    if not settings.entra_auth_enabled:
        return _dev_principal()

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return validate_token(credentials.credentials)


def authenticate_ws(token: str | None) -> Principal:
    """Validate a token supplied on a WebSocket connection (query param)."""
    settings = get_settings()
    if not settings.entra_auth_enabled:
        return _dev_principal()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    return validate_token(token)
