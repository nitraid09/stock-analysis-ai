from __future__ import annotations

import pytest

from stock_analysis_ai.html_generation.exceptions import ContractError
from stock_analysis_ai.master_storage.reconciliation import (
    ReconciliationContext,
    apply_reconciliation,
)


def test_order_status_and_reconciliation_status_remain_separate() -> None:
    row, evidence_rows = apply_reconciliation(
        {
            "order_id": "order-000001",
            "order_status": "filled",
            "reconciliation_status": "unreconciled",
        },
        reconciliation_status="reconciled",
        context=ReconciliationContext(),
    )

    assert row["order_status"] == "filled"
    assert row["reconciliation_status"] == "reconciled"
    assert evidence_rows == ()


def test_evidence_is_required_for_daily_note_originated_updates() -> None:
    with pytest.raises(ContractError):
        apply_reconciliation(
            {
                "order_id": "order-000001",
                "order_status": "cancelled",
                "reconciliation_status": "unreconciled",
            },
            reconciliation_status="unreconciled",
            context=ReconciliationContext(from_daily_note=True),
        )


def test_evidence_replaced_requires_evidence_refs() -> None:
    row, evidence_rows = apply_reconciliation(
        {
            "order_id": "order-000001",
            "order_status": "filled",
            "reconciliation_status": "unreconciled",
        },
        reconciliation_status="evidence_replaced",
        context=ReconciliationContext(has_difference=True),
        evidence_rows=(
            {
                "reference_path": "evidence/orders/order-000001.png",
                "parent": {
                    "parent_type": "order",
                    "parent_id": "order-000001",
                },
            },
        ),
    )

    assert row["reconciliation_status"] == "evidence_replaced"
    assert evidence_rows[0]["parent"]["parent_type"] == "order"
