"""Completed SQLite schema and row codec for master storage."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Mapping

from stock_analysis_ai.html_generation.exceptions import ContractError

from .contracts import (
    ALL_TABLES,
    EVIDENCE_PARENT_TYPES,
    MasterStorageSnapshot,
    ORDER_STATUSES,
    POSITION_STATUSES,
    PROPOSAL_STATUSES,
    RECONCILIATION_STATUSES,
    REVIEW_SCOPE_TYPES,
    validate_master_storage_snapshot,
)

SCHEMA_VERSION = 1

HEADER_TABLES: tuple[str, ...] = (
    "proposal_header",
    "order_header",
    "holding_snapshot_header",
    "review_header",
    "us_virtual_watch_header",
    "us_pilot_header",
)

HEADER_SELECT_COLUMNS: dict[str, tuple[str, ...]] = {
    "proposal_header": ("proposal_id", "proposal_status", "created_at", "updated_at", "payload_json"),
    "order_header": (
        "order_id",
        "proposal_id",
        "position_cycle_id",
        "order_status",
        "reconciliation_status",
        "created_at",
        "updated_at",
        "payload_json",
    ),
    "holding_snapshot_header": (
        "snapshot_id",
        "position_status",
        "created_at",
        "updated_at",
        "payload_json",
    ),
    "review_header": (
        "review_id",
        "primary_subject_type",
        "primary_subject_id",
        "review_scope_type",
        "created_at",
        "updated_at",
        "payload_json",
    ),
    "us_virtual_watch_header": (
        "us_virtual_watch_id",
        "created_at",
        "updated_at",
        "payload_json",
    ),
    "us_pilot_header": (
        "us_pilot_id",
        "pilot_status",
        "created_at",
        "updated_at",
        "payload_json",
    ),
}

HEADER_TYPED_FIELDS: dict[str, tuple[str, ...]] = {
    table_name: tuple(column for column in columns if column != "payload_json")
    for table_name, columns in HEADER_SELECT_COLUMNS.items()
}

NON_HEADER_COLUMNS: dict[str, tuple[str, ...]] = {
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
    "holding_snapshot_position": ("snapshot_id", "position_cycle_id", "security_code", "quantity"),
    "position_cycle_registry": (
        "position_cycle_id",
        "security_code",
        "entry_order_id",
        "position_status",
        "remaining_quantity",
        "opened_by_order_id",
        "closed_by_order_id",
        "last_order_id",
        "opened_at",
        "closed_at",
    ),
    "evidence_ref": (
        "evidence_ref_id",
        "parent_type",
        "parent_id",
        "reference_path",
        "status",
        "created_at",
        "updated_at",
    ),
}

NON_HEADER_ALLOWED_FIELDS: dict[str, frozenset[str]] = {
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
    "holding_snapshot_position": frozenset(
        {"snapshot_id", "position_cycle_id", "security_code", "quantity"}
    ),
    "position_cycle_registry": frozenset(
        {
            "position_cycle_id",
            "security_code",
            "entry_order_id",
            "status",
            "position_status",
            "remaining_quantity",
            "opened_by_order_id",
            "closed_by_order_id",
            "last_order_id",
            "opened_at",
            "closed_at",
        }
    ),
    "evidence_ref": frozenset(
        {"evidence_ref_id", "parent", "reference_path", "status", "created_at", "updated_at"}
    ),
}

EXPECTED_COLUMNS: dict[str, tuple[str, ...]] = {
    "proposal_header": ("proposal_id", "proposal_status", "created_at", "updated_at", "payload_json"),
    "proposal_target": ("internal_row_id", "proposal_id", "target_code"),
    "order_header": (
        "order_id",
        "proposal_id",
        "position_cycle_id",
        "order_status",
        "reconciliation_status",
        "created_at",
        "updated_at",
        "payload_json",
    ),
    "order_fill": (
        "internal_row_id",
        "order_id",
        "fill_id",
        "position_cycle_id",
        "security_code",
        "signed_quantity",
        "executed_at",
        "fill_status",
    ),
    "holding_snapshot_header": (
        "snapshot_id",
        "position_status",
        "created_at",
        "updated_at",
        "payload_json",
    ),
    "holding_snapshot_position": (
        "internal_row_id",
        "snapshot_id",
        "position_cycle_id",
        "security_code",
        "quantity",
    ),
    "review_header": (
        "review_id",
        "primary_subject_type",
        "primary_subject_id",
        "review_scope_type",
        "created_at",
        "updated_at",
        "payload_json",
    ),
    "position_cycle_registry": (
        "position_cycle_id",
        "security_code",
        "entry_order_id",
        "position_status",
        "remaining_quantity",
        "opened_by_order_id",
        "closed_by_order_id",
        "last_order_id",
        "opened_at",
        "closed_at",
    ),
    "evidence_ref": (
        "evidence_ref_id",
        "parent_type",
        "parent_id",
        "reference_path",
        "status",
        "created_at",
        "updated_at",
    ),
    "us_virtual_watch_header": ("us_virtual_watch_id", "created_at", "updated_at", "payload_json"),
    "us_pilot_header": ("us_pilot_id", "pilot_status", "created_at", "updated_at", "payload_json"),
}

TABLE_ORDER_BY: dict[str, str] = {
    "proposal_header": "proposal_id",
    "proposal_target": "internal_row_id",
    "order_header": "order_id",
    "order_fill": "internal_row_id",
    "holding_snapshot_header": "snapshot_id",
    "holding_snapshot_position": "internal_row_id",
    "review_header": "review_id",
    "position_cycle_registry": "position_cycle_id",
    "evidence_ref": "evidence_ref_id",
    "us_virtual_watch_header": "us_virtual_watch_id",
    "us_pilot_header": "us_pilot_id",
}

TABLE_INSERT_ORDER: tuple[str, ...] = (
    "proposal_header",
    "position_cycle_registry",
    "order_header",
    "proposal_target",
    "order_fill",
    "holding_snapshot_header",
    "holding_snapshot_position",
    "review_header",
    "us_virtual_watch_header",
    "us_pilot_header",
    "evidence_ref",
)

TABLE_DELETE_ORDER: tuple[str, ...] = (
    "evidence_ref",
    "proposal_target",
    "order_fill",
    "holding_snapshot_position",
    "review_header",
    "us_pilot_header",
    "us_virtual_watch_header",
    "holding_snapshot_header",
    "order_header",
    "position_cycle_registry",
    "proposal_header",
)

CREATE_TABLE_STATEMENTS: dict[str, str] = {
    "proposal_header": """
        CREATE TABLE IF NOT EXISTS proposal_header (
            proposal_id TEXT PRIMARY KEY,
            proposal_status TEXT CHECK (
                proposal_status IS NULL
                OR proposal_status IN ('proposed', 'pass', 'zero_new_entry', 'invalidated', 'closed')
            ),
            created_at TEXT,
            updated_at TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}'
        )
    """,
    "proposal_target": """
        CREATE TABLE IF NOT EXISTS proposal_target (
            internal_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id TEXT NOT NULL,
            target_code TEXT,
            FOREIGN KEY (proposal_id) REFERENCES proposal_header (proposal_id)
        )
    """,
    "order_header": """
        CREATE TABLE IF NOT EXISTS order_header (
            order_id TEXT PRIMARY KEY,
            proposal_id TEXT,
            position_cycle_id TEXT,
            order_status TEXT NOT NULL CHECK (
                order_status IN ('none', 'submitted', 'partially_filled', 'filled', 'cancelled', 'expired')
            ),
            reconciliation_status TEXT NOT NULL CHECK (
                reconciliation_status IN ('unreconciled', 'reconciled', 'evidence_replaced')
            ),
            created_at TEXT,
            updated_at TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (proposal_id) REFERENCES proposal_header (proposal_id),
            FOREIGN KEY (position_cycle_id) REFERENCES position_cycle_registry (position_cycle_id)
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
            fill_status TEXT,
            FOREIGN KEY (order_id) REFERENCES order_header (order_id),
            FOREIGN KEY (position_cycle_id) REFERENCES position_cycle_registry (position_cycle_id)
        )
    """,
    "holding_snapshot_header": """
        CREATE TABLE IF NOT EXISTS holding_snapshot_header (
            snapshot_id TEXT PRIMARY KEY,
            position_status TEXT CHECK (
                position_status IS NULL
                OR position_status IN ('not_open', 'open', 'closed')
            ),
            created_at TEXT,
            updated_at TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}'
        )
    """,
    "holding_snapshot_position": """
        CREATE TABLE IF NOT EXISTS holding_snapshot_position (
            internal_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id TEXT NOT NULL,
            position_cycle_id TEXT,
            security_code TEXT,
            quantity TEXT,
            FOREIGN KEY (snapshot_id) REFERENCES holding_snapshot_header (snapshot_id),
            FOREIGN KEY (position_cycle_id) REFERENCES position_cycle_registry (position_cycle_id)
        )
    """,
    "review_header": """
        CREATE TABLE IF NOT EXISTS review_header (
            review_id TEXT PRIMARY KEY,
            primary_subject_type TEXT NOT NULL,
            primary_subject_id TEXT NOT NULL,
            review_scope_type TEXT CHECK (
                review_scope_type IS NULL
                OR review_scope_type IN ('individual', 'period')
            ),
            created_at TEXT,
            updated_at TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}'
        )
    """,
    "position_cycle_registry": """
        CREATE TABLE IF NOT EXISTS position_cycle_registry (
            position_cycle_id TEXT PRIMARY KEY,
            security_code TEXT,
            entry_order_id TEXT,
            position_status TEXT,
            remaining_quantity TEXT,
            opened_by_order_id TEXT,
            closed_by_order_id TEXT,
            last_order_id TEXT,
            opened_at TEXT,
            closed_at TEXT
        )
    """,
    "evidence_ref": """
        CREATE TABLE IF NOT EXISTS evidence_ref (
            evidence_ref_id TEXT PRIMARY KEY,
            parent_type TEXT NOT NULL CHECK (
                parent_type IN ('proposal', 'order', 'holding_snapshot', 'review', 'us_pilot')
            ),
            parent_id TEXT NOT NULL,
            reference_path TEXT NOT NULL,
            status TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """,
    "us_virtual_watch_header": """
        CREATE TABLE IF NOT EXISTS us_virtual_watch_header (
            us_virtual_watch_id TEXT PRIMARY KEY,
            created_at TEXT,
            updated_at TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}'
        )
    """,
    "us_pilot_header": """
        CREATE TABLE IF NOT EXISTS us_pilot_header (
            us_pilot_id TEXT PRIMARY KEY,
            pilot_status TEXT,
            created_at TEXT,
            updated_at TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}'
        )
    """,
}

CREATE_INDEX_STATEMENTS: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_proposal_header_status_updated_at ON proposal_header (proposal_status, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_proposal_target_proposal_id ON proposal_target (proposal_id)",
    "CREATE INDEX IF NOT EXISTS idx_order_header_proposal_id ON order_header (proposal_id)",
    "CREATE INDEX IF NOT EXISTS idx_order_header_position_cycle_id ON order_header (position_cycle_id)",
    "CREATE INDEX IF NOT EXISTS idx_order_header_reconciliation_status_order_status ON order_header (reconciliation_status, order_status)",
    "CREATE INDEX IF NOT EXISTS idx_order_fill_order_id ON order_fill (order_id)",
    "CREATE INDEX IF NOT EXISTS idx_order_fill_position_cycle_id_executed_at ON order_fill (position_cycle_id, executed_at)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_order_fill_order_id_fill_id ON order_fill (order_id, fill_id) WHERE fill_id IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_holding_snapshot_header_updated_at ON holding_snapshot_header (updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_holding_snapshot_position_snapshot_id ON holding_snapshot_position (snapshot_id)",
    "CREATE INDEX IF NOT EXISTS idx_holding_snapshot_position_cycle_id ON holding_snapshot_position (position_cycle_id)",
    "CREATE INDEX IF NOT EXISTS idx_review_header_primary_subject ON review_header (primary_subject_type, primary_subject_id)",
    "CREATE INDEX IF NOT EXISTS idx_review_header_scope_updated_at ON review_header (review_scope_type, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_position_cycle_registry_security_code ON position_cycle_registry (security_code)",
    "CREATE INDEX IF NOT EXISTS idx_evidence_ref_parent_status ON evidence_ref (parent_type, parent_id, status)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_evidence_ref_parent_path ON evidence_ref (parent_type, parent_id, reference_path)",
    "CREATE INDEX IF NOT EXISTS idx_us_pilot_header_status_updated_at ON us_pilot_header (pilot_status, updated_at)",
)

EXPECTED_INDEX_NAMES: frozenset[str] = frozenset(
    statement.split("INDEX IF NOT EXISTS ", 1)[1].split(" ON ", 1)[0]
    for statement in CREATE_INDEX_STATEMENTS
)


def configure_connection(connection: sqlite3.Connection) -> None:
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")


def list_user_tables(connection: sqlite3.Connection) -> tuple[str, ...]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return tuple(str(row["name"]) for row in rows)


def get_table_columns(connection: sqlite3.Connection, table_name: str) -> tuple[str, ...]:
    return tuple(
        str(row["name"])
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    )


def get_table_indexes(connection: sqlite3.Connection, table_name: str) -> frozenset[str]:
    return frozenset(
        str(row["name"])
        for row in connection.execute(f"PRAGMA index_list({table_name})").fetchall()
        if isinstance(row["name"], str)
    )


def create_completed_schema(connection: sqlite3.Connection) -> None:
    for table_name in ALL_TABLES:
        connection.execute(CREATE_TABLE_STATEMENTS[table_name])
    for statement in CREATE_INDEX_STATEMENTS:
        connection.execute(statement)
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def ensure_completed_schema(connection: sqlite3.Connection) -> None:
    if not list_user_tables(connection):
        create_completed_schema(connection)
    validate_completed_schema(connection)


def validate_completed_schema(connection: sqlite3.Connection) -> None:
    table_names = set(list_user_tables(connection))
    missing_tables = [table_name for table_name in ALL_TABLES if table_name not in table_names]
    unexpected_tables = [table_name for table_name in table_names if table_name not in ALL_TABLES]
    if missing_tables or unexpected_tables:
        details: list[str] = []
        if missing_tables:
            details.append(f"missing tables: {', '.join(sorted(missing_tables))}")
        if unexpected_tables:
            details.append(f"unexpected tables: {', '.join(sorted(unexpected_tables))}")
        raise ContractError("; ".join(details))

    for table_name, expected_columns in EXPECTED_COLUMNS.items():
        columns = get_table_columns(connection, table_name)
        if columns != expected_columns:
            raise ContractError(
                f"{table_name} schema mismatch. expected={expected_columns!r} actual={columns!r}"
            )

    actual_indexes = frozenset().union(
        *(get_table_indexes(connection, table_name) for table_name in ALL_TABLES)
    )
    missing_indexes = EXPECTED_INDEX_NAMES - actual_indexes
    if missing_indexes:
        raise ContractError(f"Missing required indexes: {', '.join(sorted(missing_indexes))}")

    schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
    if int(schema_version) != SCHEMA_VERSION:
        raise ContractError(
            f"master_storage schema_version mismatch. expected={SCHEMA_VERSION} actual={schema_version}"
        )


def _decode_payload_json(table_name: str, payload_json: str) -> dict[str, Any]:
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise ContractError(f"{table_name}.payload_json must contain valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ContractError(f"{table_name}.payload_json must decode to an object.")
    return payload


def _decode_header_row(table_name: str, row: sqlite3.Row) -> dict[str, Any]:
    decoded = _decode_payload_json(table_name, row["payload_json"])
    for field_name in HEADER_TYPED_FIELDS[table_name]:
        if field_name in ("primary_subject_type", "primary_subject_id"):
            continue
        value = row[field_name]
        if value is not None:
            decoded[field_name] = value
    if table_name == "review_header":
        decoded["primary_subject"] = {
            "subject_type": row["primary_subject_type"],
            "subject_id": row["primary_subject_id"],
        }
    return decoded


def decode_non_header_row(table_name: str, row: sqlite3.Row) -> dict[str, Any]:
    if table_name == "evidence_ref":
        decoded: dict[str, Any] = {
            "evidence_ref_id": row["evidence_ref_id"],
            "parent": {
                "parent_type": row["parent_type"],
                "parent_id": row["parent_id"],
            },
            "reference_path": row["reference_path"],
        }
        if row["status"] is not None:
            decoded["status"] = row["status"]
        if row["created_at"] is not None:
            decoded["created_at"] = row["created_at"]
        if row["updated_at"] is not None:
            decoded["updated_at"] = row["updated_at"]
        return decoded
    if table_name == "position_cycle_registry":
        decoded = {
            "position_cycle_id": row["position_cycle_id"],
        }
        for column_name in NON_HEADER_COLUMNS[table_name][1:]:
            value = row[column_name]
            if value is None:
                continue
            if column_name == "position_status":
                decoded["status"] = value
                continue
            decoded[column_name] = value
        return decoded
    return {
        column_name: row[column_name]
        for column_name in NON_HEADER_COLUMNS[table_name]
        if row[column_name] is not None
    }


def normalize_non_header_row(table_name: str, row: Mapping[str, Any]) -> dict[str, Any]:
    if "payload_json" in row:
        raise ContractError(f"{table_name} must not accept payload_json as a logical field.")
    unexpected = sorted(set(row) - NON_HEADER_ALLOWED_FIELDS[table_name])
    if unexpected:
        raise ContractError(
            f"{table_name} received unsupported logical fields: {', '.join(unexpected)}"
        )
    if table_name == "evidence_ref":
        parent = row.get("parent")
        if not isinstance(parent, Mapping):
            raise ContractError("evidence_ref rows must provide parent.")
        normalized: dict[str, Any] = {
            "parent": {
                "parent_type": parent.get("parent_type"),
                "parent_id": parent.get("parent_id"),
            },
            "reference_path": row.get("reference_path"),
        }
        for optional_field in ("evidence_ref_id", "status", "created_at", "updated_at"):
            if row.get(optional_field) is not None:
                normalized[optional_field] = row.get(optional_field)
        return normalized
    if table_name == "position_cycle_registry":
        normalized_registry: dict[str, Any] = {"position_cycle_id": row.get("position_cycle_id")}
        position_status = row.get("position_status", row.get("status"))
        for field_name in (
            "security_code",
            "entry_order_id",
            "remaining_quantity",
            "opened_by_order_id",
            "closed_by_order_id",
            "last_order_id",
            "opened_at",
            "closed_at",
        ):
            if row.get(field_name) is not None:
                normalized_registry[field_name] = row.get(field_name)
        if position_status is not None:
            normalized_registry["status"] = position_status
        return normalized_registry
    normalized_row = {field_name: row.get(field_name) for field_name in NON_HEADER_ALLOWED_FIELDS[table_name]}
    return {field_name: value for field_name, value in normalized_row.items() if value is not None}


def load_snapshot_from_connection(connection: sqlite3.Connection) -> MasterStorageSnapshot:
    validate_completed_schema(connection)
    tables: dict[str, tuple[dict[str, Any], ...]] = {}
    for table_name in ALL_TABLES:
        order_by = TABLE_ORDER_BY[table_name]
        if table_name in HEADER_TABLES:
            select_columns = ", ".join(HEADER_SELECT_COLUMNS[table_name])
            rows = connection.execute(
                f"SELECT {select_columns} FROM {table_name} ORDER BY {order_by}"
            ).fetchall()
            tables[table_name] = tuple(_decode_header_row(table_name, row) for row in rows)
            continue
        select_columns = ", ".join(NON_HEADER_COLUMNS[table_name])
        rows = connection.execute(
            f"SELECT {select_columns} FROM {table_name} ORDER BY {order_by}"
        ).fetchall()
        tables[table_name] = tuple(decode_non_header_row(table_name, row) for row in rows)
    snapshot = MasterStorageSnapshot(tables=tables)
    validate_master_storage_snapshot(snapshot)
    return snapshot


def _encode_header_row(table_name: str, row: Mapping[str, Any]) -> tuple[Any, ...]:
    payload = dict(row)
    for field_name in HEADER_TYPED_FIELDS[table_name]:
        payload.pop(field_name, None)
    if table_name == "review_header":
        primary_subject = row.get("primary_subject", {})
        if not isinstance(primary_subject, Mapping):
            raise ContractError("review_header rows must provide primary_subject.")
        payload.pop("primary_subject", None)
        return (
            row.get("review_id"),
            primary_subject.get("subject_type"),
            primary_subject.get("subject_id"),
            row.get("review_scope_type"),
            row.get("created_at"),
            row.get("updated_at"),
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
        )
    ordered_values = [row.get(field_name) for field_name in HEADER_TYPED_FIELDS[table_name]]
    ordered_values.append(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return tuple(ordered_values)


def _encode_non_header_row(table_name: str, row: Mapping[str, Any]) -> tuple[Any, ...]:
    normalized_row = normalize_non_header_row(table_name, row)
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
            normalized_row.get("position_cycle_id"),
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
            normalized_row.get("opened_at"),
            normalized_row.get("closed_at"),
        )
    if table_name == "evidence_ref":
        parent = normalized_row["parent"]
        return (
            normalized_row.get("evidence_ref_id"),
            parent.get("parent_type"),
            parent.get("parent_id"),
            normalized_row.get("reference_path"),
            normalized_row.get("status"),
            normalized_row.get("created_at"),
            normalized_row.get("updated_at"),
        )
    raise ContractError(f"Unsupported table_name: {table_name}")


def _insert_statement(table_name: str) -> str:
    if table_name == "proposal_header":
        return (
            "INSERT INTO proposal_header "
            "(proposal_id, proposal_status, created_at, updated_at, payload_json) VALUES (?, ?, ?, ?, ?)"
        )
    if table_name == "proposal_target":
        return "INSERT INTO proposal_target (proposal_id, target_code) VALUES (?, ?)"
    if table_name == "order_header":
        return (
            "INSERT INTO order_header "
            "(order_id, proposal_id, position_cycle_id, order_status, reconciliation_status, created_at, updated_at, payload_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        )
    if table_name == "order_fill":
        return (
            "INSERT INTO order_fill "
            "(order_id, fill_id, position_cycle_id, security_code, signed_quantity, executed_at, fill_status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
    if table_name == "holding_snapshot_header":
        return (
            "INSERT INTO holding_snapshot_header "
            "(snapshot_id, position_status, created_at, updated_at, payload_json) VALUES (?, ?, ?, ?, ?)"
        )
    if table_name == "holding_snapshot_position":
        return (
            "INSERT INTO holding_snapshot_position "
            "(snapshot_id, position_cycle_id, security_code, quantity) VALUES (?, ?, ?, ?)"
        )
    if table_name == "review_header":
        return (
            "INSERT INTO review_header "
            "(review_id, primary_subject_type, primary_subject_id, review_scope_type, created_at, updated_at, payload_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
    if table_name == "position_cycle_registry":
        return (
            "INSERT INTO position_cycle_registry "
            "(position_cycle_id, security_code, entry_order_id, position_status, remaining_quantity, "
            "opened_by_order_id, closed_by_order_id, last_order_id, opened_at, closed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
    if table_name == "evidence_ref":
        return (
            "INSERT INTO evidence_ref "
            "(evidence_ref_id, parent_type, parent_id, reference_path, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
    if table_name == "us_virtual_watch_header":
        return (
            "INSERT INTO us_virtual_watch_header "
            "(us_virtual_watch_id, created_at, updated_at, payload_json) VALUES (?, ?, ?, ?)"
        )
    if table_name == "us_pilot_header":
        return (
            "INSERT INTO us_pilot_header "
            "(us_pilot_id, pilot_status, created_at, updated_at, payload_json) VALUES (?, ?, ?, ?, ?)"
        )
    raise ContractError(f"Unsupported table_name: {table_name}")


def replace_snapshot_in_connection(
    connection: sqlite3.Connection,
    snapshot: MasterStorageSnapshot,
) -> None:
    validate_master_storage_snapshot(snapshot)
    validate_completed_schema(connection)
    for table_name in TABLE_DELETE_ORDER:
        connection.execute(f"DELETE FROM {table_name}")
    for table_name in TABLE_INSERT_ORDER:
        for row in snapshot.tables[table_name]:
            if table_name in HEADER_TABLES:
                connection.execute(_insert_statement(table_name), _encode_header_row(table_name, row))
            else:
                connection.execute(_insert_statement(table_name), _encode_non_header_row(table_name, row))


def is_supported_evidence_parent(parent_type: str) -> bool:
    return parent_type in EVIDENCE_PARENT_TYPES


def status_sets() -> dict[str, tuple[str, ...]]:
    return {
        "proposal_status": PROPOSAL_STATUSES,
        "order_status": ORDER_STATUSES,
        "reconciliation_status": RECONCILIATION_STATUSES,
        "position_status": POSITION_STATUSES,
        "review_scope_type": REVIEW_SCOPE_TYPES,
    }

