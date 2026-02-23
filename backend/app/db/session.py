"""
Async SQLAlchemy session factory.

Uses asyncpg driver for PostgreSQL with Entra authentication.
The session is injected into FastAPI route handlers via the `get_db` dependency.

Engine and session factory are created lazily at startup (not at import time)
so the app can surface clear errors instead of crashing on import.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
import sys
from typing import AsyncGenerator
from urllib.parse import quote_plus, urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Module-level placeholders — populated by init_db()
# ---------------------------------------------------------------------------
engine = None  # type: ignore[assignment]
async_session = None  # type: ignore[assignment]

# Global credential for token refresh
_credential = None


def _get_credential():
    """Get or create the DefaultAzureCredential (import lazily)."""
    global _credential
    if _credential is None:
        from azure.identity import DefaultAzureCredential
        _credential = DefaultAzureCredential()
    return _credential


def _get_entra_token() -> str:
    """Get an Entra access token for Azure PostgreSQL."""
    credential = _get_credential()
    token = credential.get_token("https://ossrdbms-aad.database.windows.net/.default")
    return token.token


def _build_db_url_with_entra() -> str:
    """Build database URL using Entra token as password."""
    parsed = urlparse(settings.database_url)

    token = _get_entra_token()

    username = quote_plus(parsed.username or "")
    password = quote_plus(token)

    netloc = f"{username}:{password}@{parsed.hostname}"
    if parsed.port:
        netloc += f":{parsed.port}"

    new_url = urlunparse((
        parsed.scheme,
        netloc,
        parsed.path,
        "", "", "",
    ))
    logger.info("Built DB URL for user: %s", parsed.username)
    return new_url


def _create_engine_and_session():
    """Build the SQLAlchemy engine + session factory.

    For Azure URLs this acquires an Entra token (requires network + az login).
    For local URLs it uses the connection string as-is.
    """
    is_azure = "azure.com" in settings.database_url

    if is_azure:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        connect_args = {"ssl": ssl_context}

        db_url = _build_db_url_with_entra()
    else:
        db_url = settings.database_url.split("?")[0] if "?" in settings.database_url else settings.database_url
        connect_args = {}

    eng = create_async_engine(
        db_url,
        echo=False,
        pool_size=10,
        max_overflow=20,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    sess = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    return eng, sess


def _ensure_azure_pg_ready() -> None:
    """Pre-flight: start the Azure PG server and update firewall if configured.

    Uses the Azure CLI (must be on PATH and logged in).
    Skipped silently when azure_pg_resource_group / azure_pg_server_name are empty.
    """
    import json
    import subprocess

    rg = settings.azure_pg_resource_group
    server = settings.azure_pg_server_name
    if not rg or not server:
        return  # not configured — skip

    # 1. Ensure the server is running
    try:
        result = subprocess.run(
            ["az", "postgres", "flexible-server", "show",
             "--resource-group", rg, "--name", server,
             "--query", "state", "-o", "tsv"],
            capture_output=True, text=True, timeout=30,
        )
        state = result.stdout.strip()
        if state and state.lower() != "ready":
            logger.info("Azure PG server '%s' is %s — starting …", server, state)
            subprocess.run(
                ["az", "postgres", "flexible-server", "start",
                 "--resource-group", rg, "--name", server],
                capture_output=True, text=True, timeout=120,
            )
            logger.info("Azure PG server started.")
        else:
            logger.info("Azure PG server '%s' is Ready.", server)
    except Exception as exc:
        logger.warning("Could not check/start Azure PG server: %s", exc)

    # 2. Ensure current IP is in the firewall
    try:
        import urllib.request
        my_ip = urllib.request.urlopen("https://api.ipify.org", timeout=10).read().decode().strip()
        logger.info("Current public IP: %s", my_ip)

        # Check existing rule
        result = subprocess.run(
            ["az", "postgres", "flexible-server", "firewall-rule", "show",
             "--resource-group", rg, "--name", server,
             "--rule-name", "AllowMyIP", "-o", "json"],
            capture_output=True, text=True, timeout=30,
        )
        needs_update = True
        if result.returncode == 0:
            rule = json.loads(result.stdout)
            if rule.get("startIpAddress") == my_ip:
                logger.info("Firewall rule AllowMyIP already allows %s.", my_ip)
                needs_update = False

        if needs_update:
            logger.info("Updating firewall rule AllowMyIP → %s", my_ip)
            cmd = "update" if result.returncode == 0 else "create"
            subprocess.run(
                ["az", "postgres", "flexible-server", "firewall-rule", cmd,
                 "--resource-group", rg, "--name", server,
                 "--rule-name", "AllowMyIP",
                 "--start-ip-address", my_ip, "--end-ip-address", my_ip],
                capture_output=True, text=True, timeout=30,
            )
            logger.info("Firewall rule updated.")
    except Exception as exc:
        logger.warning("Could not update firewall rule: %s", exc)


async def init_db(max_retries: int = 5, delay: float = 3.0) -> None:
    """Initialise engine + session, retrying on transient auth/network errors.

    Called once from the FastAPI startup event.
    """
    global engine, async_session

    # Pre-flight: ensure Azure PG is running and firewall allows us
    if "azure.com" in settings.database_url:
        _ensure_azure_pg_ready()

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Database init attempt %d/%d …", attempt, max_retries)
            eng, sess = _create_engine_and_session()

            # Verify the connection is actually reachable
            async with eng.begin() as conn:
                await conn.run_sync(lambda c: None)  # lightweight ping

            engine = eng
            async_session = sess
            logger.info("Database connection established successfully.")
            return

        except Exception as exc:
            last_error = exc
            logger.warning(
                "Database init attempt %d/%d failed: %s",
                attempt, max_retries, exc,
            )
            if attempt < max_retries:
                logger.info("Retrying in %.0fs …", delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)  # exponential back-off, max 30s

    # All retries exhausted
    logger.error("Could not connect to the database after %d attempts.", max_retries)
    logger.error("Last error: %s", last_error)

    if "azure.com" in settings.database_url:
        logger.error(
            "Hint: ensure you have network connectivity and have run 'az login' "
            "so Entra authentication can obtain a token."
        )

    # Fatal — cannot serve without a database
    sys.exit(1)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if async_session is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
