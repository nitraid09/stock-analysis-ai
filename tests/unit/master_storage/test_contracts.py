from __future__ import annotations

import inspect
import sqlite3

import pytest

import stock_analysis_ai.master_storage as master_storage_module
from stock_analysis_ai.html_generation.exceptions import ContractError
from stock_analysis_ai.master_storage import MasterStorageRepository
from stock_analysis_ai.master_storage.contracts import (
    ALL_TABLES,
    MasterStorageSnapshot,
    validate_master_storage_snapshot,
)


def test_master_storage_snapshot_exposes_exact_eleven_table_boundaries() -> None:
    snapshot = MasterStorageSnapshot.empty()

    assert tuple(snapshot.tables.keys()) == ALL_TABLES
    assert len(snapshot.tables) == 11
    assert "us_virtual_watch_header" in snapshot.tables
    assert "us_pilot_header" in snapshot.tables


def test_master_storage_repository_uses_sqlite_core_without_json_master_file(tmp_path) -> None:
    repository = MasterStorageRepository(tmp_path)
    repository.replace_snapshot(MasterStorageSnapshot.empty())

    assert repository.paths.sqlite_file.exists()
    assert repository.paths.sqlite_file.name == "master_storage.sqlite3"
    assert not (repository.paths.storage_root / "master_storage.json").exists()

    with sqlite3.connect(repository.paths.sqlite_file) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
    assert table_names == set(ALL_TABLES)


def test_master_storage_source_does_not_expose_json_primary_contract_naming() -> None:
    source = inspect.getsource(master_storage_module)

    assert "master_storage.json" not in source
    assert "JSON-backed" not in source


def test_review_header_requires_single_primary_subject() -> None:
    tables = MasterStorageSnapshot.empty().to_mutable_tables()
    tables["review_header"].append(
        {
            "review_id": "review-000001",
            "primary_subject": {},
        }
    )

    with pytest.raises(ContractError):
        validate_master_storage_snapshot(MasterStorageSnapshot(tables={name: tuple(rows) for name, rows in tables.items()}))


def test_child_tables_allow_multiple_rows_under_the_same_parent_boundary() -> None:
    tables = MasterStorageSnapshot.empty().to_mutable_tables()
    tables["order_header"].append(
        {
            "order_id": "order-000001",
            "order_status": "filled",
            "reconciliation_status": "reconciled",
        }
    )
    tables["order_fill"].extend(
        [
            {
                "order_id": "order-000001",
                "fill_id": "fill-1",
                "signed_quantity": "50",
            },
            {
                "order_id": "order-000001",
                "fill_id": "fill-2",
                "signed_quantity": "50",
            },
        ]
    )

    snapshot = MasterStorageSnapshot(tables={name: tuple(rows) for name, rows in tables.items()})

    validate_master_storage_snapshot(snapshot)
    assert len(snapshot.tables["order_fill"]) == 2


def test_evidence_ref_requires_exactly_one_parent_lineage() -> None:
    tables = MasterStorageSnapshot.empty().to_mutable_tables()
    tables["order_header"].append(
        {
            "order_id": "order-000001",
            "order_status": "filled",
            "reconciliation_status": "reconciled",
        }
    )
    tables["evidence_ref"].append(
        {
            "reference_path": "evidence/orders/order-000001.png",
            "parent": {"parent_type": "order", "parent_id": ""},
        }
    )

    with pytest.raises(ContractError):
        validate_master_storage_snapshot(MasterStorageSnapshot(tables={name: tuple(rows) for name, rows in tables.items()}))
