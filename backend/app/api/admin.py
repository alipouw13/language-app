"""
Admin / diagnostics API routes.

GET  /api/admin/tables    — per-table existence + row counts in the lakehouse
POST /api/admin/provision — create any missing Delta tables (idempotent)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.auth.entra import get_principal
from app.config import get_settings
from app.repository import store

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(get_principal)],
)


@router.get("/tables")
async def get_tables():
    """Confirm which Delta tables exist in the lakehouse and their row counts."""
    s = get_settings()
    status = await store.table_status()
    return {
        "storage_backend": s.storage_backend,
        "tables_uri": s.onelake_tables_uri if s.storage_backend == "onelake" else s.local_lakehouse_path,
        "tables": status,
    }


@router.post("/provision")
async def provision_tables():
    """Create any missing Delta tables (and seed the calendar dimension)."""
    result = await store.ensure_tables()
    status = await store.table_status()
    return {"result": result, "tables": status}
