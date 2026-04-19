from __future__ import annotations

from stock_analysis_ai.master_storage.change_set import resolve_change_set


def test_change_set_is_resolved_from_record_units_not_screens() -> None:
    change_set = resolve_change_set(
        generation_id="gen-001",
        publish_mode="publish",
        table_changes={
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
                    "signed_quantity": "100",
                }
            ],
            "evidence_ref": [
                {
                    "reference_path": "evidence/orders/order-000001.png",
                    "parent": {
                        "parent_type": "order",
                        "parent_id": "order-000001",
                    },
                }
            ],
        },
        changed_evaluation_series=("ai_official",),
    )

    assert change_set.changed_record_units == ("order",)
    assert change_set.changed_parent_keys["order"] == ("order-000001",)
    assert change_set.changed_evaluation_series == ("ai_official",)
