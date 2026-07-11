"""
Low-level Delta Lake client for Fabric OneLake.

A thin wrapper around `deltalake` (delta-rs) that reads and writes Delta
tables either to:

* a **local** directory (``storage_backend = "local"``) — used for
  development and tests; or
* a **Fabric OneLake Lakehouse** (``storage_backend = "onelake"``) over the
  ``abfss`` endpoint, authenticated with Microsoft Entra ID via
  ``DefaultAzureCredential``.

The same code path serves both backends — only the table URI and storage
options differ. delta-rs is synchronous, so blocking calls are off-loaded to
a worker thread and serialised per-table with an asyncio lock to keep
read-modify-write updates consistent within the process.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from collections import defaultdict
from typing import Any

import pyarrow as pa
from deltalake import DeltaTable, write_deltalake

from app.config import get_settings

logger = logging.getLogger(__name__)

# Scope used to obtain an Entra token for OneLake / ADLS Gen2.
_STORAGE_SCOPE = "https://storage.azure.com/.default"


class LakehouseClient:
    """Reads/writes Delta tables to a local dir or a Fabric OneLake Lakehouse."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._backend = self._settings.storage_backend.lower()
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._credential = None
        self._token: str | None = None
        self._token_expiry: float = 0.0
        self._token_lock = threading.Lock()

        if self._backend == "local":
            os.makedirs(self._settings.local_lakehouse_path, exist_ok=True)
            logger.info(
                "Lakehouse backend = local (%s)",
                os.path.abspath(self._settings.local_lakehouse_path),
            )
        else:
            logger.info(
                "Lakehouse backend = onelake (%s)",
                self._settings.onelake_tables_uri,
            )

    # ------------------------------------------------------------------ #
    # URI + auth helpers                                                 #
    # ------------------------------------------------------------------ #
    def _table_uri(self, table: str) -> str:
        if self._backend == "local":
            return os.path.join(self._settings.local_lakehouse_path, table)
        # Schema-enabled lakehouses nest tables under Tables/<schema>/<name>.
        schema = (self._settings.onelake_schema or "").strip().strip("/")
        prefix = self._settings.onelake_tables_uri
        if schema:
            return f"{prefix}/{schema}/{table}"
        return f"{prefix}/{table}"

    def _storage_options(self) -> dict[str, str] | None:
        if self._backend == "local":
            return None
        return {
            "bearer_token": self._get_storage_token(),
            "use_fabric_endpoint": "true",
        }

    def _get_storage_token(self) -> str:
        """Cached Entra token for OneLake (refreshed ~5 min before expiry)."""
        with self._token_lock:
            now = time.time()
            if self._token and now < self._token_expiry - 300:
                return self._token
            if self._credential is None:
                from azure.identity import DefaultAzureCredential

                self._credential = DefaultAzureCredential()
            tok = self._credential.get_token(_STORAGE_SCOPE)
            self._token = tok.token
            self._token_expiry = float(tok.expires_on)
            return self._token

    # ------------------------------------------------------------------ #
    # Blocking IO primitives (run via asyncio.to_thread)                 #
    # ------------------------------------------------------------------ #
    def _exists(self, table: str) -> bool:
        uri = self._table_uri(table)
        if self._backend == "local":
            return os.path.isdir(os.path.join(uri, "_delta_log"))
        try:
            DeltaTable(uri, storage_options=self._storage_options())
            return True
        except Exception:  # noqa: BLE001 — delta-rs raises TableNotFoundError
            return False

    def _read_all(self, table: str, schema: pa.Schema) -> list[dict[str, Any]]:
        uri = self._table_uri(table)
        # Open the Delta table once; a missing table raises and reads as empty.
        try:
            dt = DeltaTable(uri, storage_options=self._storage_options())
        except Exception:  # noqa: BLE001 — delta-rs raises TableNotFoundError
            return []
        return dt.to_pyarrow_table().to_pylist()

    def _write(
        self,
        table: str,
        rows: list[dict[str, Any]],
        schema: pa.Schema,
        mode: str,
    ) -> None:
        uri = self._table_uri(table)
        arrow_table = pa.Table.from_pylist(rows, schema=schema)
        write_deltalake(
            uri,
            arrow_table,
            mode=mode,
            schema_mode="overwrite" if mode == "overwrite" else None,
            storage_options=self._storage_options(),
        )

    def _create_empty(self, table: str, schema: pa.Schema) -> bool:
        """Create an empty Delta table with *schema* if it doesn't exist.

        Returns True if the table was created, False if it already existed.
        delta-rs cannot write a zero-row batch, so we use DeltaTable.create
        (mode='ignore' makes it idempotent).
        """
        if self._exists(table):
            return False
        uri = self._table_uri(table)
        if self._backend == "local":
            os.makedirs(uri, exist_ok=True)
        DeltaTable.create(
            uri,
            schema,
            mode="ignore",
            name=table,
            storage_options=self._storage_options(),
        )
        return True

    # ------------------------------------------------------------------ #
    # Async public API                                                   #
    # ------------------------------------------------------------------ #
    async def read_all(self, table: str, schema: pa.Schema) -> list[dict[str, Any]]:
        async with self._locks[table]:
            return await asyncio.to_thread(self._read_all, table, schema)

    async def append(
        self, table: str, rows: list[dict[str, Any]], schema: pa.Schema
    ) -> None:
        if not rows:
            return
        async with self._locks[table]:
            await asyncio.to_thread(self._write, table, rows, schema, "append")

    async def overwrite(
        self, table: str, rows: list[dict[str, Any]], schema: pa.Schema
    ) -> None:
        async with self._locks[table]:
            await asyncio.to_thread(self._write, table, rows, schema, "overwrite")

    async def create_table(self, table: str, schema: pa.Schema) -> bool:
        """Create an empty Delta table with *schema* if it doesn't exist.

        Returns True if it was created, False if it already existed.
        """
        async with self._locks[table]:
            return await asyncio.to_thread(self._create_empty, table, schema)

    async def read_modify_write(
        self,
        table: str,
        schema: pa.Schema,
        mutate,
    ) -> list[dict[str, Any]]:
        """Atomically (per-process) read all rows, apply ``mutate`` and overwrite.

        ``mutate`` receives the current list of rows and returns the new list.
        Serialised by the per-table lock so concurrent edits don't clobber.
        """
        async with self._locks[table]:
            def _do() -> list[dict[str, Any]]:
                current = self._read_all(table, schema)
                updated = mutate(list(current))
                self._write(table, updated, schema, "overwrite")
                return updated

            return await asyncio.to_thread(_do)

    async def health_check(self) -> dict[str, Any]:
        """Verify the storage backend is reachable."""
        info: dict[str, Any] = {"backend": self._backend}
        try:
            if self._backend == "local":
                os.makedirs(self._settings.local_lakehouse_path, exist_ok=True)
                info["path"] = os.path.abspath(self._settings.local_lakehouse_path)
            else:
                # Acquiring a token proves Entra auth works.
                await asyncio.to_thread(self._get_storage_token)
                info["tables_uri"] = self._settings.onelake_tables_uri
            info["status"] = "ok"
        except Exception as exc:  # noqa: BLE001
            info["status"] = "error"
            info["detail"] = str(exc)
        return info


_client: LakehouseClient | None = None


def get_lakehouse() -> LakehouseClient:
    """Return the process-wide lakehouse client (lazily created)."""
    global _client
    if _client is None:
        _client = LakehouseClient()
    return _client
