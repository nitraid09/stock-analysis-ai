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
    MasterStoragePaths,
    MasterStorageSnapshot,
    STABLE_KEY_FIELDS_BY_TABLE,
    validate_master_storage_snapshot,
)

_HEADER_TABLES: tuple[str, ...] = (
    "proposal_header",
    "order_header",
    "holding_snapshot_header",
    "review_header",
    "us_virtual_watch_header",
    "us_pilot_header",
)

_NON_HEADER_COLUMNS: dict[str, tuple[str, ...]] = {
    "proposal_target": ("proposal_id", "target_code"),
    "order_fill": (
        "order_id",
        "fill_id",
        "position_cycle_id",
        "security_code",
        "signed_quantity",
        "executed_at",
        "fill_status",
    ),
    "holding_snapshot_position": ("snapshot_id", "security_code", "quantity"),
    "position_cycle_registry": (
        "position_cycle_id",
        "security_code",
        "entry_order_id",
        "status",
        "remaining_quantity",
        "opened_by_order_id",
        "closed_by_order_id",
        "last_order_id",
    ),
    "evidence_ref": ("parent_type", "parent_id", "reference_path", "status"),
}

_NON_HEADER_ALLOWED_FIELDS: dict[str, frozenset[str]] = {
    "proposal_target": frozenset({"proposal_id", "target_code"}),
    "order_fill": frozenset(
        {
            "order_id",
            "fill_id",
            "position_cycle_id",
            "security_code",
            "signed_quantity",
            "executed_at",
            "fill_status",
        }
    ),
    "holding_snapshot_position": frozenset({"snapshot_id", "security_code", "quantity"}),
    "position_cycle_registry": frozenset(
        {
            "position_cycle_id",
            "security_code",
            "entry_order_id",
            "status",
            "remaining_quantity",
            "opened_by_order_id",
            "closed_by_order_id",
            "last_order_id",
        }
    ),
    "evidence_ref": frozenset({"parent", "reference_path", "status"}),
}

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
            target_code TEXT
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
            fill_id TEXT,
            position_cycle_id TEXT,
            security_code TEXT,
            signed_quantity TEXT,
            executed_at TEXT,
            fill_status TEXT
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
            security_code TEXT,
            quantity TEXT
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
            security_code TEXT,
            entry_order_id TEXT,
            status TEXT,
            remaining_quantity TEXT,
            opened_by_order_id TEXT,
            closed_by_order_id TEXT,
            last_order_id TEXT
        )
    """,
    "evidence_ref": """
        CREATE TABLE IF NOT EXISTS evidence_ref (
            internal_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_type TEXT NOT NULL,
            parent_id TEXT NOT NULL,
            reference_path TEXT NOT NULL,
            status TEXT
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


def _canonical_row(row: Mapping[str, Any]) -> str:
    return json.dumps(dict(row), ensure_ascii=False, sort_keys=True)


def _canonical_row_collection(rows: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    return tuple(sorted(_canonical_row(row) for row in rows))


def _normalize_non_header_row(table_name: str, row: Mapping[str, Any]) -> dict[str, Any]:
    if "payload_json" in row:
        raise ContractError(f"{table_name} must not accept payload_json as a logical field.")
    unexpected = sorted(set(row) - _NON_HEADER_ALLOWED_FIELDS[table_name])
    if unexpected:
        raise ContractError(
            f"{table_name} received unsupported logical fields: {', '.join(unexpected)}"
        )
    if table_name == "evidence_ref":
        parent = row.get("parent")
        if not isinstance(parent, Mapping):
            raise ContractError("evidence_ref rows must provide parent.")
        normalized = {
            "parent": {
                "parent_type": parent.get("parent_type"),
                "parent_id": parent.get("parent_id"),
            },
            "reference_path": row.get("reference_path"),
        }
        if row.get("status") is not None:
            normalized["status"] = row.get("status")
        return normalized
    normalized_row = {field_name: row.get(field_name) for field_name in _NON_HEADER_ALLOWED_FIELDS[table_name]}
    return {
        field_name: value
        for field_name, value in normalized_row.items()
        if value is not None
    }


def _decode_non_header_row(table_name: str, row: sqlite3.Row) -> dict[str, Any]:
    if table_name == "evidence_ref":
        decoded: dict[str, Any] = {
            "parent": {
                "parent_type": row["parent_type"],
                "parent_id": row["parent_id"],
            },
            "reference_path": row["reference_path"],
        }
        if row["status"] is not None:
            decoded["status"] = row["status"]
        return decoded
    return {
        column_name: row[column_name]
        for column_name in _NON_HEADER_COLUMNS[table_name]
        if row[column_name] is not None
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
        self._validate_physical_schema(connection)

    def _validate_physical_schema(self, connection: sqlite3.Connection) -> None:
        for table_name in _HEADER_TABLES:
            columns = {
                row["name"]
                for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
            }
            if "payload_json" not in columns:
                raise ContractError(f"{table_name} must retain payload_json for header supplemental data.")
        for table_name, required_columns in _NON_HEADER_COLUMNS.items():
            columns = {
                row["name"]
                for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
            }
            if "payload_json" in columns:
                raise ContractError(
                    f"{table_name} still contains legacy payload_json storage and requires migration."
                )
            missing_columns = [column_name for column_name in required_columns if column_name not in columns]
            if missing_columns:
                raise ContractError(
                    f"{table_name} is missing required scaffold columns: {', '.join(missing_columns)}"
                )

    def load_snapshot(self, connection: sqlite3.Connection) -> MasterStorageSnapshot:
        tables: dict[str, tuple[dict[str, Any], ...]] = {}
        for table_name in ALL_TABLES:
            if table_name in _HEADER_TABLES:
                rows = connection.execute(
                    f"SELECT payload_json FROM {table_name} ORDER BY {_TABLE_ORDER_BY[table_name]}"
                ).fetchall()
                tables[table_name] = tuple(json.loads(row["payload_json"]) for row in rows)
                continue
            select_columns = ", ".join(_NON_HEADER_COLUMNS[table_name])
            rows = connection.execute(
                f"SELECT {select_columns} FROM {table_name} ORDER BY {_TABLE_ORDER_BY[table_name]}"
            ).fetchall()
            tables[table_name] = tuple(_decode_non_header_row(table_name, row) for row in rows)
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
            return "INSERT INTO proposal_target (proposal_id, target_code) VALUES (?, ?)"
        if table_name == "order_header":
            return (
                "INSERT INTO order_header "
                "(order_id, proposal_id, position_cycle_id, order_status, reconciliation_status, payload_json) "
                "VALUES (?, ?, ?, ?, ?, ?)"
            )
        if table_name == "order_fill":
            return (
                "INSERT INTO order_fill "
                "(order_id, fill_id, position_cycle_id, security_code, signed_quantity, executed_at, fill_status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)"
            )
        if table_name == "holding_snapshot_header":
            return "INSERT INTO holding_snapshot_header (snapshot_id, payload_json) VALUES (?, ?)"
        if table_name == "holding_snapshot_position":
            return (
                "INSERT INTO holding_snapshot_position (snapshot_id, security_code, quantity) "
                "VALUES (?, ?, ?)"
            )
        if table_name == "review_header":
            return (
                "INSERT INTO review_header "
                "(review_id, primary_subject_type, primary_subject_id, payload_json) VALUES (?, ?, ?, ?)"
            )
        if table_name == "position_cycle_registry":
            return (
                "INSERT INTO position_cycle_registry "
                "(position_cycle_id, security_code, entry_order_id, status, remaining_quantity, "
                "opened_by_order_id, closed_by_order_id, last_order_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            )
        if table_name == "evidence_ref":
            return (
                "INSERT INTO evidence_ref (parent_type, parent_id, reference_path, status) "
                "VALUES (?, ?, ?, ?)"
            )
        if table_name == "us_virtual_watch_header":
            return "INSERT INTO us_virtual_watch_header (us_virtual_watch_id, payload_json) VALUES (?, ?)"
        if table_name == "us_pilot_header":
            return "INSERT INTO us_pilot_header (us_pilot_id, payload_json) VALUES (?, ?)"
        raise ContractError(f"Unsupported table_name: {table_name}")

    @staticmethod
    def _extract_insert_values(table_name: str, row: Mapping[str, Any]) -> tuple[Any, ...]:
        if table_name in _HEADER_TABLES:
            payload_json = json.dumps(dict(row), ensure_ascii=False, sort_keys=True)
            if table_name == "proposal_header":
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
            if table_name == "holding_snapshot_header":
                return (row.get("snapshot_id"), payload_json)
            if table_name == "review_header":
                primary_subject = row.get("primary_subject", {})
                return (
                    row.get("review_id"),
                    primary_subject.get("subject_type"),
                    primary_subject.get("subject_id"),
                    payload_json,
                )
            if table_name == "us_virtual_watch_header":
                return (row.get("us_virtual_watch_id"), payload_json)
            if table_name == "us_pilot_header":
                return (row.get("us_pilot_id"), payload_json)
        normalized_row = _normalize_non_header_row(table_name, row)
        if table_name == "proposal_target":
            return (normalized_row.get("proposal_id"), normalized_row.get("target_code"))
        if table_name == "order_fill":
            return (
                normalized_row.get("order_id"),
                normalized_row.get("fill_id"),
                normalized_row.get("position_cycle_id"),
                normalized_row.get("security_code"),
                normalized_row.get("signed_quantity"),
                normalized_row.get("executed_at"),
                normalized_row.get("fill_status"),
            )
        if table_name == "holding_snapshot_position":
            return (
                normalized_row.get("snapshot_id"),
                normalized_row.get("security_code"),
                normalized_row.get("quantity"),
            )
        if table_name == "position_cycle_registry":
            return (
                normalized_row.get("position_cycle_id"),
                normalized_row.get("security_code"),
                normalized_row.get("entry_order_id"),
                normalized_row.get("status"),
                normalized_row.get("remaining_quantity"),
                normalized_row.get("opened_by_order_id"),
                normalized_row.get("closed_by_order_id"),
                normalized_row.get("last_order_id"),
            )
        if table_name == "evidence_ref":
            parent = normalized_row["parent"]
            return (
                parent.get("parent_type"),
                parent.get("parent_id"),
                normalized_row.get("reference_path"),
                normalized_row.get("status"),
            )
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
                self._append_or_supersede_evidence_rows(tables[table_name], normalized_rows)
                continue
            if table_name == "position_cycle_registry":
                self._upsert_rows(
                    tables[table_name],
                    [_normalize_non_header_row(table_name, row) for row in normalized_rows],
                    STABLE_KEY_FIELDS_BY_TABLE.get(table_name, ()),
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
    def _merge_immutable_child_rows(
        existing_rows: list[dict[str, Any]],
        new_rows: list[dict[str, Any]],
        parent_key_field: str,
        table_name: str,
    ) -> None:
        normalized_rows = [_normalize_non_header_row(table_name, row) for row in new_rows]
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
        for row in [_normalize_non_header_row("order_fill", row) for row in new_rows]:
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
    ) -> None:
        index = {
            (
                row.get("parent", {}).get("parent_type"),
                row.get("parent", {}).get("parent_id"),
                row.get("reference_path"),
            ): position
            for position, row in enumerate(existing_rows)
        }
        for row in [_normalize_non_header_row("evidence_ref", row) for row in new_rows]:
            identity = (
                row["parent"].get("parent_type"),
                row["parent"].get("parent_id"),
                row.get("reference_path"),
            )
            existing_position = index.get(identity)
            if existing_position is None:
                index[identity] = len(existing_rows)
                existing_rows.append(row)
                continue
            if _canonical_row(existing_rows[existing_position]) != _canonical_row(row):
                existing_rows[existing_position] = row


__all__ = [
    "MasterStorageRepository",
    "MasterStorageSnapshot",
    "MasterStoragePaths",
    "MasterStorageTransaction",
    "SqliteMasterStorageAdapter",
]
