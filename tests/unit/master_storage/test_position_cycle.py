from __future__ import annotations

from stock_analysis_ai.master_storage.contracts import MasterStorageSnapshot
from stock_analysis_ai.master_storage.key_factory import StableKeyFactory
from stock_analysis_ai.master_storage.position_cycle import FillEvent, assign_position_cycles


def test_position_cycle_is_reused_until_full_exit_then_reissued() -> None:
    key_factory = StableKeyFactory.from_snapshot(MasterStorageSnapshot.empty())
    result = assign_position_cycles(
        [
            FillEvent(order_id="order-000001", security_code="7203", signed_quantity=100),
            FillEvent(order_id="order-000002", security_code="7203", signed_quantity=50),
            FillEvent(order_id="order-000003", security_code="7203", signed_quantity=-150),
            FillEvent(order_id="order-000004", security_code="7203", signed_quantity=100),
        ],
        (),
        key_factory,
    )

    first_cycle = result.assignments["order-000001"]
    assert first_cycle is not None
    assert result.assignments["order-000002"] == first_cycle
    assert result.assignments["order-000003"] == first_cycle
    assert result.assignments["order-000004"] != first_cycle
    assert len(result.registry_rows) == 2
