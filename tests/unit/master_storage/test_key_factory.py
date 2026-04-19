from __future__ import annotations

from stock_analysis_ai.master_storage.contracts import MasterStorageSnapshot
from stock_analysis_ai.master_storage.key_factory import StableKeyFactory


def test_stable_key_factory_reserves_required_and_optional_key_spaces() -> None:
    factory = StableKeyFactory.from_snapshot(MasterStorageSnapshot.empty())

    assert factory.reserve("proposal_id") == "proposal-000001"
    assert factory.reserve("order_id") == "order-000001"
    assert factory.reserve("position_cycle_id") == "position-cycle-000001"
    assert factory.reserve("snapshot_id") == "snapshot-000001"
    assert factory.reserve("review_id") == "review-000001"
    assert factory.reserve("evidence_ref_id") == "evidence-ref-000001"
    assert factory.reserve("us_virtual_watch_id") == "us-virtual-watch-000001"
    assert factory.reserve("us_pilot_id") == "us-pilot-000001"
