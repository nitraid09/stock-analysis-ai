"""Stable key reservation derived from the SQLite master snapshot."""

from __future__ import annotations

from dataclasses import dataclass

from stock_analysis_ai.html_generation.exceptions import ContractError

from .contracts import ALL_KEY_NAMES, MasterStorageSnapshot, scan_reserved_key_counters

KEY_PREFIXES: dict[str, str] = {
    "proposal_id": "proposal",
    "order_id": "order",
    "position_cycle_id": "position-cycle",
    "snapshot_id": "snapshot",
    "review_id": "review",
    "us_virtual_watch_id": "us-virtual-watch",
    "us_pilot_id": "us-pilot",
}


@dataclass
class StableKeyFactory:
    """Mutable stable key reservation state derived from persisted stable keys."""

    counters: dict[str, int]

    @classmethod
    def from_snapshot(cls, snapshot: MasterStorageSnapshot) -> "StableKeyFactory":
        return cls(counters=scan_reserved_key_counters(snapshot))

    def reserve(self, key_name: str) -> str:
        if key_name not in ALL_KEY_NAMES:
            raise ContractError(f"Unsupported key reservation: {key_name}")
        next_value = int(self.counters.get(key_name, 0)) + 1
        self.counters[key_name] = next_value
        prefix = KEY_PREFIXES[key_name]
        return f"{prefix}-{next_value:06d}"

    def reserve_many(self, key_name: str, count: int) -> tuple[str, ...]:
        if count <= 0:
            raise ContractError("count must be greater than zero.")
        return tuple(self.reserve(key_name) for _ in range(count))
