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
        proposal_target_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(proposal_target)")
        }
        order_fill_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(order_fill)")
        }
        holding_position_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(holding_snapshot_position)")
        }
        position_cycle_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(position_cycle_registry)")
        }
        evidence_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(evidence_ref)")
        }
    assert table_names == set(ALL_TABLES)
    assert "payload_json" not in proposal_target_columns
    assert "payload_json" not in order_fill_columns
    assert "payload_json" not in holding_position_columns
    assert "payload_json" not in position_cycle_columns
    assert "payload_json" not in evidence_columns


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


def test_proposal_target_is_immutable_once_formalized(tmp_path) -> None:
    repository = MasterStorageRepository(tmp_path)
    snapshot = MasterStorageSnapshot.empty()
    initial_snapshot = repository.apply_table_changes(
        snapshot,
        {
            "proposal_header": [{"proposal_id": "proposal-000001"}],
            "proposal_target": [{"proposal_id": "proposal-000001", "target_code": "7203"}],
        },
    )

    with pytest.raises(ContractError):
        repository.apply_table_changes(
            initial_snapshot,
            {
                "proposal_target": [{"proposal_id": "proposal-000001", "target_code": "6758"}],
            },
        )


def test_order_fill_is_append_only_for_existing_fill_id(tmp_path) -> None:
    repository = MasterStorageRepository(tmp_path)
    snapshot = repository.apply_table_changes(
        MasterStorageSnapshot.empty(),
        {
            "order_header": [
                {
                    "order_id": "order-000001",
                    "order_status": "filled",
                    "reconciliation_status": "reconciled",
                }
            ],
            "order_fill": [
                {
                    "order_id": "order-000001",
                    "fill_id": "fill-1",
                    "signed_quantity": "100",
                }
            ],
        },
    )

    with pytest.raises(ContractError):
        repository.apply_table_changes(
            snapshot,
            {
                "order_fill": [
                    {
                        "order_id": "order-000001",
                        "fill_id": "fill-1",
                        "signed_quantity": "90",
                    }
                ]
            },
        )


def test_holding_snapshot_positions_are_fixed_per_snapshot_id(tmp_path) -> None:
    repository = MasterStorageRepository(tmp_path)
    snapshot = repository.apply_table_changes(
        MasterStorageSnapshot.empty(),
        {
            "holding_snapshot_header": [{"snapshot_id": "snapshot-000001"}],
            "holding_snapshot_position": [
                {
                    "snapshot_id": "snapshot-000001",
                    "security_code": "7203",
                    "quantity": "100",
                }
            ],
        },
    )

    with pytest.raises(ContractError):
        repository.apply_table_changes(
            snapshot,
            {
                "holding_snapshot_position": [
                    {
                        "snapshot_id": "snapshot-000001",
                        "security_code": "7203",
                        "quantity": "50",
                    }
                ]
            },
        )


def test_evidence_ref_appends_without_replacing_sibling_references(tmp_path) -> None:
    repository = MasterStorageRepository(tmp_path)
    snapshot = repository.apply_table_changes(
        MasterStorageSnapshot.empty(),
        {
            "order_header": [
                {
                    "order_id": "order-000001",
                    "order_status": "filled",
                    "reconciliation_status": "reconciled",
                }
            ],
            "evidence_ref": [
                {
                    "parent": {"parent_type": "order", "parent_id": "order-000001"},
                    "reference_path": "evidence/orders/order-000001-a.png",
                }
            ],
        },
    )

    updated_snapshot = repository.apply_table_changes(
        snapshot,
        {
            "evidence_ref": [
                {
                    "parent": {"parent_type": "order", "parent_id": "order-000001"},
                    "reference_path": "evidence/orders/order-000001-a.png",
                    "status": "superseded",
                },
                {
                    "parent": {"parent_type": "order", "parent_id": "order-000001"},
                    "reference_path": "evidence/orders/order-000001-b.png",
                },
            ]
        },
    )

    evidence_rows = updated_snapshot.tables["evidence_ref"]
    assert len(evidence_rows) == 2
    assert any(row.get("status") == "superseded" for row in evidence_rows)
    assert any(row["reference_path"].endswith("-b.png") for row in evidence_rows)


def test_evidence_ref_rejects_non_header_standard_parent_types() -> None:
    tables = MasterStorageSnapshot.empty().to_mutable_tables()
    tables["position_cycle_registry"].append({"position_cycle_id": "position-cycle-000001"})
    tables["evidence_ref"].append(
        {
            "reference_path": "evidence/orders/position-cycle-000001.png",
            "parent": {
                "parent_type": "position_cycle",
                "parent_id": "position-cycle-000001",
            },
        }
    )

    with pytest.raises(ContractError):
        validate_master_storage_snapshot(
            MasterStorageSnapshot(tables={name: tuple(rows) for name, rows in tables.items()})
        )
