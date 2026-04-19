"""SQLite-centered repository and adapter for the master storage boundary."""

from __future__ import annotations

import json
import sqlite3
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Mapping, Sequence

from stock_analysis_ai.html_generation.exceptions import ContractError

from .contracts import (
    ALL_TABLES,
    CHILD_PARENT_FIELDS,
    MasterStoragePaths,
    MasterStorageSnapshot,
    STABLE_KEY_FIELDS_BY_TABLE,
    validate_master_storage_snapshot,
)

_CREATE_STATEMENTS: dict[str, str] = {
    "proposal_header": """
        CREATE TABLE IF NOT EXISTS proposal_header (
            proposal_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL
        )
    """,
    "proposal_target": """
        CREATE TABLE IF NOT EXISTS proposal_target (
            internal_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
    """,
    "order_header": """
        CREATE TABLE IF NOT EXISTS order_header (
            order_id TEXT PRIMARY KEY,
            proposal_id TEXT,
            position_cycle_id TEXT,
            order_status TEXT NOT NULL,
            reconciliation_status TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
    """,
    "order_fill": """
        CREATE TABLE IF NOT EXISTS order_fill (
            internal_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            position_cycle_id TEXT,
            payload_json TEXT NOT NULL
        )
    """,
    "holding_snapshot_header": """
        CREATE TABLE IF NOT EXISTS holding_snapshot_header (
            snapshot_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL
        )
    """,
    "holding_snapshot_position": """
        CREATE TABLE IF NOT EXISTS holding_snapshot_position (
            internal_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
    """,
    "review_header": """
        CREATE TABLE IF NOT EXISTS review_header (
            review_id TEXT PRIMARY KEY,
            primary_subject_type TEXT NOT NULL,
            primary_subject_id TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
    """,
    "position_cycle_registry": """
        CREATE TABLE IF NOT EXISTS position_cycle_registry (
            position_cycle_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL
        )
    """,
    "evidence_ref": """
        CREATE TABLE IF NOT EXISTS evidence_ref (
            internal_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_type TEXT NOT NULL,
            parent_id TEXT NOT NULL,
            reference_path TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
    """,
    "us_virtual_watch_header": """
        CREATE TABLE IF NOT EXISTS us_virtual_watch_header (
            us_virtual_watch_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL
        )
    """,
    "us_pilot_header": """
        CREATE TABLE IF NOT EXISTS us_pilot_header (
            us_pilot_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL
        )
    """,
}

_TABLE_ORDER_BY: dict[str, str] = {
    "proposal_header": "proposal_id",
    "proposal_target": "internal_row_id",
    "order_header": "order_id",
    "order_fill": "internal_row_id",
    "holding_snapshot_header": "snapshot_id",
    "holding_snapshot_position": "internal_row_id",
    "review_header": "review_id",
    "position_cycle_registry": "position_cycle_id",
    "evidence_ref": "internal_row_id",
    "us_virtual_watch_header": "us_virtual_watch_id",
    "us_pilot_header": "us_pilot_id",
}


class SqliteMasterStorageAdapter:
    """Low-level SQLite adapter that persists the fixed 11-table structure."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)

    def connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        self.ensure_schema(connection)
        return connection

    def ensure_schema(self, connection: sqlite3.Connection) -> None:
        for statement in _CREATE_STATEMENTS.values():
            connection.execute(statement)

    def load_snapshot(self, connection: sqlite3.Connection) -> MasterStorageSnapshot:
        tables: dict[str, tuple[dict[str, Any], ...]] = {}
        for table_name in ALL_TABLES:
            rows = connection.execute(
                f"SELECT payload_json FROM {table_name} ORDER BY {_TABLE_ORDER_BY[table_name]}"
            ).fetchall()
            tables[table_name] = tuple(json.loads(row["payload_json"]) for row in rows)
        snapshot = MasterStorageSnapshot(tables=tables)
        validate_master_storage_snapshot(snapshot)
        return snapshot

    def replace_snapshot(
        self,
        connection: sqlite3.Connection,
        snapshot: MasterStorageSnapshot,
    ) -> None:
        validate_master_storage_snapshot(snapshot)
        for table_name in ALL_TABLES:
            connection.execute(f"DELETE FROM {table_name}")
        for table_name in ALL_TABLES:
            for row in snapshot.tables[table_name]:
                connection.execute(
                    self._insert_statement(table_name),
                    self._extract_insert_values(table_name, row),
                )

    @staticmethod
    def _insert_statement(table_name: str) -> str:
        if table_name == "proposal_header":
            return "INSERT INTO proposal_header (proposal_id, payload_json) VALUES (?, ?)"
        if table_name == "proposal_target":
            return "INSERT INTO proposal_target (proposal_id, payload_json) VALUES (?, ?)"
        if table_name == "order_header":
            return (
                "INSERT INTO order_header "
                "(order_id, proposal_id, position_cycle_id, order_status, reconciliation_status, payload_json) "
                "VALUES (?, ?, ?, ?, ?, ?)"
            )
        if table_name == "order_fill":
            return "INSERT INTO order_fill (order_id, position_cycle_id, payload_json) VALUES (?, ?, ?)"
        if table_name == "holding_snapshot_header":
            return "INSERT INTO holding_snapshot_header (snapshot_id, payload_json) VALUES (?, ?)"
        if table_name == "holding_snapshot_position":
            return "INSERT INTO holding_snapshot_position (snapshot_id, payload_json) VALUES (?, ?)"
        if table_name == "review_header":
            return (
                "INSERT INTO review_header "
                "(review_id, primary_subject_type, primary_subject_id, payload_json) VALUES (?, ?, ?, ?)"
            )
        if table_name == "position_cycle_registry":
            return "INSERT INTO position_cycle_registry (position_cycle_id, payload_json) VALUES (?, ?)"
        if table_name == "evidence_ref":
            return (
                "INSERT INTO evidence_ref (parent_type, parent_id, reference_path, payload_json) "
                "VALUES (?, ?, ?, ?)"
            )
        if table_name == "us_virtual_watch_header":
            return "INSERT INTO us_virtual_watch_header (us_virtual_watch_id, payload_json) VALUES (?, ?)"
        if table_name == "us_pilot_header":
            return "INSERT INTO us_pilot_header (us_pilot_id, payload_json) VALUES (?, ?)"
        raise ContractError(f"Unsupported table_name: {table_name}")

    @staticmethod
    def _extract_insert_values(table_name: str, row: Mapping[str, Any]) -> tuple[Any, ...]:
        payload_json = json.dumps(dict(row), ensure_ascii=False, sort_keys=True)
        if table_name == "proposal_header":
            return (row.get("proposal_id"), payload_json)
        if table_name == "proposal_target":
            return (row.get("proposal_id"), payload_json)
        if table_name == "order_header":
            return (
                row.get("order_id"),
                row.get("proposal_id"),
                row.get("position_cycle_id"),
                row.get("order_status"),
                row.get("reconciliation_status"),
                payload_json,
            )
        if table_name == "order_fill":
            return (row.get("order_id"), row.get("position_cycle_id"), payload_json)
        if table_name == "holding_snapshot_header":
            return (row.get("snapshot_id"), payload_json)
        if table_name == "holding_snapshot_position":
            return (row.get("snapshot_id"), payload_json)
        if table_name == "review_header":
            primary_subject = row.get("primary_subject", {})
            return (
                row.get("review_id"),
                primary_subject.get("subject_type"),
                primary_subject.get("subject_id"),
                payload_json,
            )
        if table_name == "position_cycle_registry":
            return (row.get("position_cycle_id"), payload_json)
        if table_name == "evidence_ref":
            parent = row.get("parent", {})
            return (
                parent.get("parent_type"),
                parent.get("parent_id"),
                row.get("reference_path"),
                payload_json,
            )
        if table_name == "us_virtual_watch_header":
            return (row.get("us_virtual_watch_id"), payload_json)
        if table_name == "us_pilot_header":
            return (row.get("us_pilot_id"), payload_json)
        raise ContractError(f"Unsupported table_name: {table_name}")


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
        return MasterStorageTransaction(self._adapter)

    def load_snapshot(self) -> MasterStorageSnapshot:
        with self.transaction() as transaction:
            return transaction.load_snapshot()

    def replace_snapshot(self, snapshot: MasterStorageSnapshot) -> MasterStorageSnapshot:
        with self.transaction() as transaction:
            transaction.replace_snapshot(snapshot)
        return snapshot

    def apply_table_changes(
        self,
        snapshot: MasterStorageSnapshot,
        table_changes: Mapping[str, Sequence[Mapping[str, Any]]],
    ) -> MasterStorageSnapshot:
        tables = snapshot.to_mutable_tables()
        for table_name, rows in table_changes.items():
            if table_name not in ALL_TABLES:
                raise ContractError(f"Unsupported table_name: {table_name}")
            normalized_rows = [dict(row) for row in rows]
            if table_name == "evidence_ref":
                self._replace_evidence_groups(tables[table_name], normalized_rows)
                continue
            if table_name in CHILD_PARENT_FIELDS:
                self._replace_child_rows(
                    tables[table_name],
                    normalized_rows,
                    CHILD_PARENT_FIELDS[table_name],
                )
                continue
            self._upsert_rows(
                tables[table_name],
                normalized_rows,
                STABLE_KEY_FIELDS_BY_TABLE.get(table_name, ()),
            )
        updated_snapshot = MasterStorageSnapshot(tables={name: tuple(rows) for name, rows in tables.items()})
        validate_master_storage_snapshot(updated_snapshot)
        return updated_snapshot

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
    def _replace_child_rows(
        existing_rows: list[dict[str, Any]],
        new_rows: list[dict[str, Any]],
        parent_key_field: str,
    ) -> None:
        if not new_rows:
            return
        parent_ids = {row.get(parent_key_field) for row in new_rows}
        retained = [
            row
            for row in existing_rows
            if row.get(parent_key_field) not in parent_ids
        ]
        retained.extend(new_rows)
        existing_rows[:] = retained

    @staticmethod
    def _replace_evidence_groups(
        existing_rows: list[dict[str, Any]],
        new_rows: list[dict[str, Any]],
    ) -> None:
        if not new_rows:
            return
        parent_pairs = {
            (
                row.get("parent", {}).get("parent_type"),
                row.get("parent", {}).get("parent_id"),
            )
            for row in new_rows
        }
        retained = [
            row
            for row in existing_rows
            if (
                row.get("parent", {}).get("parent_type"),
                row.get("parent", {}).get("parent_id"),
            ) not in parent_pairs
        ]
        retained.extend(new_rows)
        existing_rows[:] = retained


__all__ = [
    "MasterStorageRepository",
    "MasterStorageSnapshot",
    "MasterStoragePaths",
    "MasterStorageTransaction",
    "SqliteMasterStorageAdapter",
]
