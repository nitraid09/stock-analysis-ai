from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from stock_analysis_ai.html_generation.exceptions import ContractError
from stock_analysis_ai.master_storage import MasterStorageRepository, migrate_master_storage
from stock_analysis_ai.master_storage.migration import preflight_master_storage


def _database_path(project_root: Path) -> Path:
    return project_root / "master" / "storage" / "master_storage.sqlite3"


def _create_legacy_schema(project_root: Path) -> Path:
    database_path = _database_path(project_root)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(
            """
            CREATE TABLE proposal_header (
                proposal_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE order_header (
                order_id TEXT PRIMARY KEY,
                proposal_id TEXT,
                position_cycle_id TEXT,
                order_status TEXT NOT NULL,
                reconciliation_status TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE order_fill (
                internal_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                fill_id TEXT,
                position_cycle_id TEXT,
                security_code TEXT,
                signed_quantity TEXT,
                executed_at TEXT,
                fill_status TEXT
            );
            CREATE TABLE evidence_ref (
                internal_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_type TEXT NOT NULL,
                parent_id TEXT NOT NULL,
                reference_path TEXT NOT NULL,
                status TEXT
            );
            """
        )
        connection.execute(
            "INSERT INTO proposal_header (proposal_id, payload_json) VALUES (?, ?)",
            (
                "proposal-000001",
                json.dumps(
                    {"proposal_id": "proposal-000001", "proposal_status": "proposed"},
                    ensure_ascii=False,
                ),
            ),
        )
        connection.execute(
            "INSERT INTO order_header (order_id, proposal_id, position_cycle_id, order_status, reconciliation_status, payload_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                "order-000001",
                "proposal-000001",
                None,
                "filled",
                "reconciled",
                json.dumps(
                    {
                        "order_id": "order-000001",
                        "proposal_id": "proposal-000001",
                        "order_status": "filled",
                        "reconciliation_status": "reconciled",
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        connection.execute(
            "INSERT INTO order_fill (order_id, fill_id, security_code, signed_quantity, fill_status) VALUES (?, ?, ?, ?, ?)",
            ("order-000001", "fill-1", "7203", "100", "filled"),
        )
        connection.execute(
            "INSERT INTO evidence_ref (parent_type, parent_id, reference_path, status) VALUES (?, ?, ?, ?)",
            ("order", "order-000001", "evidence/orders/order-000001.png", "active"),
        )
        connection.commit()
    finally:
        connection.close()
    return database_path


def test_preflight_detects_legacy_child_payload_json_schema(tmp_path: Path) -> None:
    database_path = _database_path(tmp_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(
            """
            CREATE TABLE proposal_header (
                proposal_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE proposal_target (
                internal_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposal_id TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            """
        )
        connection.commit()
    finally:
        connection.close()

    result = preflight_master_storage(tmp_path)

    assert result.database_state == "invalid"
    assert any(issue.code == "legacy_payload_json" for issue in result.blocking_issues)


def test_preflight_detects_parent_relation_mismatch_in_legacy_rows(tmp_path: Path) -> None:
    database_path = _database_path(tmp_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(
            """
            CREATE TABLE order_header (
                order_id TEXT PRIMARY KEY,
                proposal_id TEXT,
                position_cycle_id TEXT,
                order_status TEXT NOT NULL,
                reconciliation_status TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE order_fill (
                internal_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                fill_id TEXT,
                position_cycle_id TEXT,
                security_code TEXT,
                signed_quantity TEXT,
                executed_at TEXT,
                fill_status TEXT
            );
            """
        )
        connection.execute(
            "INSERT INTO order_fill (order_id, fill_id, signed_quantity) VALUES (?, ?, ?)",
            ("order-missing", "fill-1", "10"),
        )
        connection.commit()
    finally:
        connection.close()

    result = preflight_master_storage(tmp_path)

    assert result.database_state == "invalid"
    assert any(issue.code == "row_contract" for issue in result.blocking_issues)


def test_migrate_master_storage_creates_backup_and_completed_schema(tmp_path: Path) -> None:
    database_path = _create_legacy_schema(tmp_path)

    result = migrate_master_storage(tmp_path)

    assert result.migrated is True
    assert result.backup_path is not None
    assert result.backup_path.exists()
    assert result.verify.schema_version == 1
    with sqlite3.connect(database_path) as connection:
        index_names = {
            row[1]
            for row in connection.execute("PRAGMA index_list(evidence_ref)")
        }
    assert "idx_evidence_ref_parent_status" in index_names
    assert "ux_evidence_ref_parent_path" in index_names
    repository = MasterStorageRepository(tmp_path)
    snapshot = repository.load_snapshot()
    assert snapshot.tables["proposal_header"][0]["proposal_id"] == "proposal-000001"
    assert snapshot.tables["order_header"][0]["order_id"] == "order-000001"
    assert snapshot.tables["evidence_ref"][0]["evidence_ref_id"].startswith("evidence-ref-")


def test_repository_refuses_legacy_schema_without_explicit_migration(tmp_path: Path) -> None:
    _create_legacy_schema(tmp_path)

    with pytest.raises(ContractError):
        MasterStorageRepository(tmp_path).load_snapshot()
