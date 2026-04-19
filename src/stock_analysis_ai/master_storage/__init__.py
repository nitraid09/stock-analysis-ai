"""SQLite-centered repository and migration boundary for master storage."""

from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Mapping, Sequence

from stock_analysis_ai.html_generation.exceptions import ContractError

from .contracts import ALL_TABLES, MasterStoragePaths, MasterStorageSnapshot, STABLE_KEY_FIELDS_BY_TABLE
from .key_factory import StableKeyFactory
from .migration import (
    MasterStorageMigrationResult,
    MasterStoragePreflightResult,
    MasterStorageVerifyResult,
    migrate_master_storage,
    preflight_master_storage,
    verify_master_storage,
)
from .schema import (
    create_completed_schema,
    configure_connection,
    ensure_completed_schema,
    load_snapshot_from_connection,
    normalize_non_header_row,
    replace_snapshot_in_connection,
)


def _canonical_row(row: Mapping[str, Any]) -> str:
    import json

    return json.dumps(dict(row), ensure_ascii=False, sort_keys=True)


def _canonical_row_collection(rows: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    return tuple(sorted(_canonical_row(row) for row in rows))


class SqliteMasterStorageAdapter:
    """Low-level SQLite adapter that persists the fixed 11-table structure."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)

    def connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        configure_connection(connection)
        try:
            ensure_completed_schema(connection)
        except ContractError as exc:
            connection.close()
            raise ContractError(
                "master_storage schema is not ready. Run explicit preflight/migrate/verify instead of silent auto-migration."
            ) from exc
        return connection

    def bootstrap_empty_database(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        try:
            configure_connection(connection)
            create_completed_schema(connection)
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def load_snapshot(connection: sqlite3.Connection) -> MasterStorageSnapshot:
        return load_snapshot_from_connection(connection)

    @staticmethod
    def replace_snapshot(
        connection: sqlite3.Connection,
        snapshot: MasterStorageSnapshot,
    ) -> None:
        replace_snapshot_in_connection(connection, snapshot)


class MasterStorageTransaction(AbstractContextManager["MasterStorageTransaction"]):
    """Atomic transaction boundary above the SQLite adapter."""

    def __init__(self, adapter: SqliteMasterStorageAdapter) -> None:
        self._adapter = adapter
        self._connection = adapter.connect()

    def __enter__(self) -> "MasterStorageTransaction":
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        try:
            if exc_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()
        finally:
            self._connection.close()
        return None

    def load_snapshot(self) -> MasterStorageSnapshot:
        return self._adapter.load_snapshot(self._connection)

    def replace_snapshot(self, snapshot: MasterStorageSnapshot) -> None:
        self._adapter.replace_snapshot(self._connection, snapshot)


class MasterStorageRepository:
    """Repository boundary that applies logical mutations onto the SQLite master store."""

    def __init__(self, project_root: Path) -> None:
        self.paths = MasterStoragePaths(project_root=Path(project_root))
        self._adapter = SqliteMasterStorageAdapter(self.paths.sqlite_file)

    def transaction(self) -> MasterStorageTransaction:
        if not self.paths.sqlite_file.exists():
            self._adapter.bootstrap_empty_database()
        return MasterStorageTransaction(self._adapter)

    def load_snapshot(self) -> MasterStorageSnapshot:
        with self.transaction() as transaction:
            return transaction.load_snapshot()

    def replace_snapshot(self, snapshot: MasterStorageSnapshot) -> MasterStorageSnapshot:
        with self.transaction() as transaction:
            transaction.replace_snapshot(snapshot)
        return snapshot

    def preflight(self) -> MasterStoragePreflightResult:
        return preflight_master_storage(self.paths.project_root)

    def migrate(self) -> MasterStorageMigrationResult:
        return migrate_master_storage(self.paths.project_root)

    def verify(self) -> MasterStorageVerifyResult:
        return verify_master_storage(self.paths.project_root)

    def apply_table_changes(
        self,
        snapshot: MasterStorageSnapshot,
        table_changes: Mapping[str, Sequence[Mapping[str, Any]]],
    ) -> MasterStorageSnapshot:
        tables = snapshot.to_mutable_tables()
        key_factory = StableKeyFactory.from_snapshot(snapshot)
        for table_name, rows in table_changes.items():
            if table_name not in ALL_TABLES:
                raise ContractError(f"Unsupported table_name: {table_name}")
            normalized_rows = [dict(row) for row in rows]
            if table_name == "proposal_target":
                self._merge_immutable_child_rows(tables[table_name], normalized_rows, "proposal_id", table_name)
                continue
            if table_name == "order_fill":
                self._append_only_child_rows(tables[table_name], normalized_rows)
                continue
            if table_name == "holding_snapshot_position":
                self._merge_immutable_child_rows(tables[table_name], normalized_rows, "snapshot_id", table_name)
                continue
            if table_name == "evidence_ref":
                self._append_or_supersede_evidence_rows(tables[table_name], normalized_rows, key_factory)
                continue
            if table_name == "position_cycle_registry":
                self._upsert_rows(
                    tables[table_name],
                    [normalize_non_header_row(table_name, row) for row in normalized_rows],
                    STABLE_KEY_FIELDS_BY_TABLE.get(table_name, ()),
                )
                continue
            self._upsert_rows(
                tables[table_name],
                normalized_rows,
                STABLE_KEY_FIELDS_BY_TABLE.get(table_name, ()),
            )
        return MasterStorageSnapshot(tables={name: tuple(rows) for name, rows in tables.items()})

    @staticmethod
    def _upsert_rows(
        existing_rows: list[dict[str, Any]],
        new_rows: list[dict[str, Any]],
        key_fields: tuple[str, ...],
    ) -> None:
        if not new_rows:
            return
        if not key_fields:
            existing_rows.extend(new_rows)
            return
        index = {
            tuple(row.get(field_name) for field_name in key_fields): position
            for position, row in enumerate(existing_rows)
        }
        for row in new_rows:
            key = tuple(row.get(field_name) for field_name in key_fields)
            if key in index:
                existing_rows[index[key]] = row
            else:
                index[key] = len(existing_rows)
                existing_rows.append(row)

    @staticmethod
    def _merge_immutable_child_rows(
        existing_rows: list[dict[str, Any]],
        new_rows: list[dict[str, Any]],
        parent_key_field: str,
        table_name: str,
    ) -> None:
        normalized_rows = [normalize_non_header_row(table_name, row) for row in new_rows]
        grouped_new_rows: dict[Any, list[dict[str, Any]]] = {}
        for row in normalized_rows:
            grouped_new_rows.setdefault(row.get(parent_key_field), []).append(row)
        for parent_id, rows_for_parent in grouped_new_rows.items():
            existing_for_parent = [
                row for row in existing_rows if row.get(parent_key_field) == parent_id
            ]
            if not existing_for_parent:
                existing_rows.extend(rows_for_parent)
                continue
            if _canonical_row_collection(existing_for_parent) != _canonical_row_collection(rows_for_parent):
                raise ContractError(
                    f"{table_name} is immutable once {parent_key_field}={parent_id} is formalized."
                )

    @staticmethod
    def _append_only_child_rows(
        existing_rows: list[dict[str, Any]],
        new_rows: list[dict[str, Any]],
    ) -> None:
        existing_canonical_rows = {_canonical_row(row) for row in existing_rows}
        fill_index = {
            (row.get("order_id"), row.get("fill_id")): _canonical_row(row)
            for row in existing_rows
            if row.get("fill_id") is not None
        }
        for row in [normalize_non_header_row("order_fill", row) for row in new_rows]:
            canonical_row = _canonical_row(row)
            if canonical_row in existing_canonical_rows:
                continue
            fill_id = row.get("fill_id")
            if fill_id is not None:
                identity = (row.get("order_id"), fill_id)
                existing_canonical = fill_index.get(identity)
                if existing_canonical is not None and existing_canonical != canonical_row:
                    raise ContractError(
                        f"order_fill is append-only and cannot overwrite existing fill_id={fill_id}."
                    )
                fill_index[identity] = canonical_row
            existing_rows.append(row)
            existing_canonical_rows.add(canonical_row)

    @staticmethod
    def _append_or_supersede_evidence_rows(
        existing_rows: list[dict[str, Any]],
        new_rows: list[dict[str, Any]],
        key_factory: StableKeyFactory,
    ) -> None:
        index = {
            (
                row.get("parent", {}).get("parent_type"),
                row.get("parent", {}).get("parent_id"),
                row.get("reference_path"),
            ): position
            for position, row in enumerate(existing_rows)
        }
        for row in [normalize_non_header_row("evidence_ref", row) for row in new_rows]:
            identity = (
                row["parent"].get("parent_type"),
                row["parent"].get("parent_id"),
                row.get("reference_path"),
            )
            existing_position = index.get(identity)
            if existing_position is None:
                if not row.get("evidence_ref_id"):
                    row["evidence_ref_id"] = key_factory.reserve("evidence_ref_id")
                index[identity] = len(existing_rows)
                existing_rows.append(row)
                continue
            persisted_row = dict(existing_rows[existing_position])
            if not row.get("evidence_ref_id"):
                row["evidence_ref_id"] = persisted_row.get("evidence_ref_id")
            if _canonical_row(persisted_row) != _canonical_row(row):
                existing_rows[existing_position] = row


__all__ = [
    "MasterStorageMigrationResult",
    "MasterStoragePaths",
    "MasterStoragePreflightResult",
    "MasterStorageRepository",
    "MasterStorageSnapshot",
    "MasterStorageTransaction",
    "MasterStorageVerifyResult",
    "SqliteMasterStorageAdapter",
    "migrate_master_storage",
    "preflight_master_storage",
    "verify_master_storage",
]
