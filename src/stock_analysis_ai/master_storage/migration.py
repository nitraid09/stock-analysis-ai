"""Schema preflight, migration, and verification for master storage."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stock_analysis_ai.html_generation.exceptions import ContractError

from .contracts import ALL_TABLES, CHILD_TABLES, MasterStoragePaths, MasterStorageSnapshot
from .schema import (
    EXPECTED_COLUMNS,
    EXPECTED_INDEX_NAMES,
    HEADER_TABLES,
    NON_HEADER_COLUMNS,
    SCHEMA_VERSION,
    configure_connection,
    create_completed_schema,
    get_table_columns,
    get_table_indexes,
    list_user_tables,
    load_snapshot_from_connection,
    replace_snapshot_in_connection,
    validate_completed_schema,
)

LEGACY_COLUMN_ALIASES: dict[str, dict[str, str]] = {
    "position_cycle_registry": {"status": "position_status"},
}
BLOCKING_PAYLOAD_TABLES = set(CHILD_TABLES) | {"position_cycle_registry", "evidence_ref"}


@dataclass(frozen=True)
class PreflightIssue:
    """Single schema or row-contract issue discovered during preflight."""

    code: str
    message: str
    table_name: str | None = None
    blocking: bool = True


@dataclass(frozen=True)
class MasterStoragePreflightResult:
    """Preflight result for an on-disk master_storage SQLite file."""

    database_path: Path
    schema_version: int | None
    database_state: str
    issues: tuple[PreflightIssue, ...] = ()
    tables: tuple[str, ...] = ()

    @property
    def blocking_issues(self) -> tuple[PreflightIssue, ...]:
        return tuple(issue for issue in self.issues if issue.blocking)

    @property
    def needs_migration(self) -> bool:
        return self.database_state in {"empty", "legacy"} and not self.blocking_issues

    @property
    def is_ready(self) -> bool:
        return self.database_state == "ready" and not self.issues

    def require_migratable(self) -> None:
        if self.blocking_issues:
            details = "; ".join(issue.message for issue in self.blocking_issues)
            raise ContractError(f"master_storage preflight failed: {details}")


@dataclass(frozen=True)
class MasterStorageVerifyResult:
    """Post-migration verification result."""

    database_path: Path
    schema_version: int
    verified_tables: tuple[str, ...]
    row_counts: dict[str, int]


@dataclass(frozen=True)
class MasterStorageMigrationResult:
    """End result of a completed migration run."""

    database_path: Path
    backup_path: Path | None
    migrated: bool
    preflight: MasterStoragePreflightResult
    verify: MasterStorageVerifyResult


def _connect(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    configure_connection(connection)
    return connection


def _new_issue(
    code: str,
    message: str,
    *,
    table_name: str | None = None,
    blocking: bool = True,
) -> PreflightIssue:
    return PreflightIssue(code=code, message=message, table_name=table_name, blocking=blocking)


def _schema_version(connection: sqlite3.Connection) -> int:
    return int(connection.execute("PRAGMA user_version").fetchone()[0])


def _normalize_relaxed_payload(table_name: str, payload_json: str) -> dict[str, Any]:
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise ContractError(f"{table_name}.payload_json must contain valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ContractError(f"{table_name}.payload_json must decode to an object.")
    return payload


def _merge_typed_field(decoded: dict[str, Any], field_name: str, value: Any, table_name: str) -> None:
    payload_value = decoded.get(field_name)
    if payload_value is not None and value is not None and payload_value != value:
        raise ContractError(
            f"{table_name} contains mismatched stable/typed field {field_name}: "
            f"payload={payload_value!r} column={value!r}"
        )
    if value is not None:
        decoded[field_name] = value


def _detect_column_issues(table_name: str, columns: tuple[str, ...]) -> tuple[PreflightIssue, ...]:
    issues: list[PreflightIssue] = []
    expected = EXPECTED_COLUMNS[table_name]
    alias_map = LEGACY_COLUMN_ALIASES.get(table_name, {})
    tolerated_extras = {"internal_row_id"}
    normalized_actual = {alias_map.get(column_name, column_name) for column_name in columns}

    if table_name in BLOCKING_PAYLOAD_TABLES and "payload_json" in columns:
        issues.append(
            _new_issue(
                "legacy_payload_json",
                f"{table_name} still contains legacy payload_json storage and requires manual review.",
                table_name=table_name,
            )
        )

    unexpected = sorted(
        column_name
        for column_name in columns
        if column_name not in expected and column_name not in alias_map and column_name not in tolerated_extras
    )
    if unexpected:
        issues.append(
            _new_issue(
                "unexpected_columns",
                f"{table_name} has unsupported columns: {', '.join(unexpected)}",
                table_name=table_name,
            )
        )

    missing = sorted(column_name for column_name in expected if column_name not in normalized_actual)
    for column_name in missing:
        issues.append(
            _new_issue(
                "missing_columns",
                f"{table_name} is missing completed-schema column {column_name}",
                table_name=table_name,
                blocking=False,
            )
        )
    return tuple(issues)


def _ensure_evidence_ids(rows: list[dict[str, Any]]) -> None:
    current_max = 0
    for row in rows:
        value = row.get("evidence_ref_id")
        if not isinstance(value, str) or "-" not in value:
            continue
        suffix = value.rsplit("-", 1)[-1]
        if suffix.isdigit():
            current_max = max(current_max, int(suffix))
    for row in rows:
        if isinstance(row.get("evidence_ref_id"), str) and row["evidence_ref_id"].strip():
            continue
        current_max += 1
        row["evidence_ref_id"] = f"evidence-ref-{current_max:06d}"


def _load_relaxed_snapshot(connection: sqlite3.Connection) -> MasterStorageSnapshot:
    tables = set(list_user_tables(connection))
    logical_tables: dict[str, tuple[dict[str, Any], ...]] = {}

    for table_name in ALL_TABLES:
        if table_name not in tables:
            logical_tables[table_name] = ()
            continue
        order_by = "internal_row_id" if "internal_row_id" in get_table_columns(connection, table_name) else EXPECTED_COLUMNS[table_name][0]
        rows = connection.execute(f"SELECT * FROM {table_name} ORDER BY {order_by}").fetchall()
        if table_name in HEADER_TABLES:
            decoded_rows: list[dict[str, Any]] = []
            for row in rows:
                if "payload_json" not in row.keys():
                    raise ContractError(f"{table_name} is missing payload_json.")
                decoded = _normalize_relaxed_payload(table_name, row["payload_json"])
                for field_name in EXPECTED_COLUMNS[table_name]:
                    if field_name in {"payload_json", "primary_subject_type", "primary_subject_id"}:
                        continue
                    if field_name in row.keys():
                        _merge_typed_field(decoded, field_name, row[field_name], table_name)
                if table_name == "review_header":
                    if "primary_subject_type" in row.keys() and "primary_subject_id" in row.keys():
                        decoded["primary_subject"] = {
                            "subject_type": row["primary_subject_type"],
                            "subject_id": row["primary_subject_id"],
                        }
                decoded_rows.append(decoded)
            logical_tables[table_name] = tuple(decoded_rows)
            continue

        if table_name == "proposal_target":
            logical_tables[table_name] = tuple(
                {"proposal_id": row["proposal_id"], "target_code": row["target_code"]}
                for row in rows
            )
            continue
        if table_name == "order_fill":
            logical_tables[table_name] = tuple(
                {
                    key: row[key]
                    for key in ("order_id", "fill_id", "position_cycle_id", "security_code", "signed_quantity", "executed_at", "fill_status")
                    if key in row.keys() and row[key] is not None
                }
                for row in rows
            )
            continue
        if table_name == "holding_snapshot_position":
            logical_tables[table_name] = tuple(
                {
                    key: row[key]
                    for key in ("snapshot_id", "position_cycle_id", "security_code", "quantity")
                    if key in row.keys() and row[key] is not None
                }
                for row in rows
            )
            continue
        if table_name == "position_cycle_registry":
            decoded_rows = []
            for row in rows:
                decoded = {"position_cycle_id": row["position_cycle_id"]}
                for key in (
                    "security_code",
                    "entry_order_id",
                    "remaining_quantity",
                    "opened_by_order_id",
                    "closed_by_order_id",
                    "last_order_id",
                    "opened_at",
                    "closed_at",
                ):
                    if key in row.keys() and row[key] is not None:
                        decoded[key] = row[key]
                if "position_status" in row.keys() and row["position_status"] is not None:
                    decoded["status"] = row["position_status"]
                elif "status" in row.keys() and row["status"] is not None:
                    decoded["status"] = row["status"]
                decoded_rows.append(decoded)
            logical_tables[table_name] = tuple(decoded_rows)
            continue
        if table_name == "evidence_ref":
            decoded_rows = []
            for row in rows:
                parent_type = row["parent_type"] if "parent_type" in row.keys() else None
                parent_id = row["parent_id"] if "parent_id" in row.keys() else None
                decoded = {
                    "parent": {"parent_type": parent_type, "parent_id": parent_id},
                    "reference_path": row["reference_path"],
                }
                for key in ("evidence_ref_id", "status", "created_at", "updated_at"):
                    if key in row.keys() and row[key] is not None:
                        decoded[key] = row[key]
                decoded_rows.append(decoded)
            _ensure_evidence_ids(decoded_rows)
            logical_tables[table_name] = tuple(decoded_rows)
            continue
        raise ContractError(f"Unsupported table during migration: {table_name}")

    snapshot = MasterStorageSnapshot(tables=logical_tables)
    return snapshot


def preflight_master_storage(project_root: Path) -> MasterStoragePreflightResult:
    paths = MasterStoragePaths(project_root=Path(project_root))
    database_path = paths.sqlite_file
    if not database_path.exists():
        return MasterStoragePreflightResult(
            database_path=database_path,
            schema_version=None,
            database_state="missing",
        )

    connection = _connect(database_path)
    try:
        tables = list_user_tables(connection)
        if not tables:
            return MasterStoragePreflightResult(
                database_path=database_path,
                schema_version=_schema_version(connection),
                database_state="empty",
                tables=tables,
            )

        issues: list[PreflightIssue] = []
        unexpected_tables = sorted(table_name for table_name in tables if table_name not in ALL_TABLES)
        for table_name in unexpected_tables:
            issues.append(
                _new_issue(
                    "unexpected_table",
                    f"Unexpected master_storage table detected: {table_name}",
                    table_name=table_name,
                )
            )

        missing_tables = sorted(table_name for table_name in ALL_TABLES if table_name not in tables)
        for table_name in missing_tables:
            issues.append(
                _new_issue(
                    "missing_table",
                    f"Missing completed-schema table: {table_name}",
                    table_name=table_name,
                    blocking=False,
                )
            )

        for table_name in ALL_TABLES:
            if table_name not in tables:
                continue
            issues.extend(_detect_column_issues(table_name, get_table_columns(connection, table_name)))

        actual_indexes = frozenset().union(
            *(get_table_indexes(connection, table_name) for table_name in ALL_TABLES if table_name in tables)
        )
        missing_indexes = sorted(EXPECTED_INDEX_NAMES - actual_indexes)
        for index_name in missing_indexes:
            issues.append(
                _new_issue(
                    "missing_index",
                    f"Missing required index: {index_name}",
                    blocking=False,
                )
            )

        schema_version = _schema_version(connection)
        if schema_version not in (0, SCHEMA_VERSION):
            issues.append(
                _new_issue(
                    "schema_version_mismatch",
                    f"Unsupported schema version: {schema_version}",
                )
            )
        elif schema_version == 0 and set(tables) == set(ALL_TABLES):
            issues.append(
                _new_issue(
                    "schema_version_unset",
                    "Schema version is unset and requires explicit migration/verification.",
                    blocking=False,
                )
            )

        if not [issue for issue in issues if issue.blocking]:
            try:
                snapshot = (
                    load_snapshot_from_connection(connection)
                    if not issues
                    else _load_relaxed_snapshot(connection)
                )
                from .contracts import validate_master_storage_snapshot

                validate_master_storage_snapshot(snapshot)
            except ContractError as exc:
                issues.append(_new_issue("row_contract", str(exc)))

        if not issues:
            database_state = "ready"
        elif [issue for issue in issues if issue.blocking]:
            database_state = "invalid"
        else:
            database_state = "legacy"

        return MasterStoragePreflightResult(
            database_path=database_path,
            schema_version=schema_version,
            database_state=database_state,
            issues=tuple(issues),
            tables=tables,
        )
    finally:
        connection.close()


def verify_master_storage(project_root: Path) -> MasterStorageVerifyResult:
    paths = MasterStoragePaths(project_root=Path(project_root))
    database_path = paths.sqlite_file
    if not database_path.exists():
        raise ContractError("master_storage database does not exist.")
    connection = _connect(database_path)
    try:
        validate_completed_schema(connection)
        snapshot = load_snapshot_from_connection(connection)
        row_counts = {
            table_name: len(snapshot.tables[table_name])
            for table_name in ALL_TABLES
        }
        return MasterStorageVerifyResult(
            database_path=database_path,
            schema_version=_schema_version(connection),
            verified_tables=ALL_TABLES,
            row_counts=row_counts,
        )
    finally:
        connection.close()


def _backup_database(source_path: Path, backup_root: Path) -> Path:
    backup_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_root / f"{source_path.stem}_{timestamp}.sqlite3"
    if backup_path.exists():
        raise ContractError(f"Backup file already exists: {backup_path}")
    source = sqlite3.connect(source_path)
    backup = sqlite3.connect(backup_path)
    try:
        source.backup(backup)
    finally:
        backup.close()
        source.close()
    return backup_path


def _shadow_database_path(database_path: Path) -> Path:
    shadow_path = database_path.with_suffix(".migrating.sqlite3")
    if shadow_path.exists():
        raise ContractError(f"Shadow database already exists: {shadow_path}")
    return shadow_path


def _materialize_shadow_database(source_path: Path, shadow_path: Path) -> None:
    source_connection = _connect(source_path)
    try:
        snapshot = _load_relaxed_snapshot(source_connection)
    finally:
        source_connection.close()
    shadow_connection = _connect(shadow_path)
    try:
        create_completed_schema(shadow_connection)
        replace_snapshot_in_connection(shadow_connection, snapshot)
        shadow_connection.commit()
        validate_completed_schema(shadow_connection)
        load_snapshot_from_connection(shadow_connection)
    finally:
        shadow_connection.close()


def migrate_master_storage(project_root: Path) -> MasterStorageMigrationResult:
    paths = MasterStoragePaths(project_root=Path(project_root))
    preflight = preflight_master_storage(project_root)
    preflight.require_migratable()

    database_path = paths.sqlite_file
    backup_path: Path | None = None
    migrated = False

    if preflight.database_state == "missing":
        paths.storage_root.mkdir(parents=True, exist_ok=True)
        connection = _connect(database_path)
        try:
            create_completed_schema(connection)
            connection.commit()
        finally:
            connection.close()
        migrated = True
    elif preflight.database_state == "empty":
        connection = _connect(database_path)
        try:
            create_completed_schema(connection)
            connection.commit()
        finally:
            connection.close()
        migrated = True
    elif preflight.database_state == "legacy":
        backup_path = _backup_database(database_path, paths.backup_root)
        shadow_path = _shadow_database_path(database_path)
        try:
            _materialize_shadow_database(database_path, shadow_path)
            shadow_path.replace(database_path)
        finally:
            if shadow_path.exists():
                shadow_path.unlink()
        migrated = True

    verify = verify_master_storage(project_root)
    return MasterStorageMigrationResult(
        database_path=database_path,
        backup_path=backup_path,
        migrated=migrated,
        preflight=preflight,
        verify=verify,
    )
