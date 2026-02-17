"""
Async SQLAlchemy session factory.

Uses asyncpg driver for PostgreSQL with Entra authentication.
The session is injected into FastAPI route handlers via the `get_db` dependency.
"""

from __future__ import annotations

import logging
import ssl
from typing import AsyncGenerator
from urllib.parse import quote_plus, urlparse, urlunparse

from azure.identity import DefaultAzureCredential
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Global credential for token refresh
_credential: DefaultAzureCredential | None = None


def _get_credential() -> DefaultAzureCredential:
    """Get or create the DefaultAzureCredential."""
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
    return _credential


def _get_entra_token() -> str:
    """Get an Entra access token for Azure PostgreSQL."""
    credential = _get_credential()
    # Get token for Azure OSSRDBMS (PostgreSQL/MySQL)
    token = credential.get_token("https://ossrdbms-aad.database.windows.net/.default")
    return token.token


def _build_db_url_with_entra() -> str:
    """Build database URL using Entra token as password."""
    parsed = urlparse(settings.database_url)
    
    # Get Entra token to use as password
    token = _get_entra_token()
    
    # URL-encode username (contains @) and token (may contain special chars)
    username = quote_plus(parsed.username or "")
    password = quote_plus(token)
    
    # Reconstruct netloc with encoded credentials
    netloc = f"{username}:{password}@{parsed.hostname}"
    if parsed.port:
        netloc += f":{parsed.port}"
    
    # Reconstruct URL without query params (we handle SSL separately)
    new_url = urlunparse((
        parsed.scheme,
        netloc,
        parsed.path,
        "",  # params
        "",  # query - SSL handled via connect_args
        ""   # fragment
    ))
    logger.info(f"Built DB URL for user: {parsed.username}")
    return new_url


# Azure PostgreSQL requires SSL
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE  # Azure handles cert verification

connect_args = {"ssl": ssl_context}

# Use Entra auth if connecting to Azure
if "azure.com" in settings.database_url:
    db_url = _build_db_url_with_entra()
else:
    # Local development - use URL as-is
    db_url = settings.database_url.split("?")[0] if "?" in settings.database_url else settings.database_url
    connect_args = {}

engine = create_async_engine(
    db_url,
    echo=False,
    pool_size=10,
    max_overflow=20,
    connect_args=connect_args,
    pool_pre_ping=True,  # Verify connections are alive (important for token refresh)
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
