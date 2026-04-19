"""Stable-key anchor helpers."""

from __future__ import annotations

from .exceptions import ContractError

ANCHOR_PREFIXES = {
    "proposal": "proposal-",
    "order": "order-",
    "position_cycle": "position-cycle-",
    "review": "review-",
    "snapshot": "snapshot-",
    "us_virtual": "us-virtual-",
    "us_pilot": "us-pilot-",
}


def build_anchor(anchor_kind: str, stable_key: str) -> str:
    if not stable_key.strip():
        raise ContractError("stable_key must not be empty.")
    try:
        prefix = ANCHOR_PREFIXES[anchor_kind]
    except KeyError as exc:
        raise ContractError(f"Unsupported anchor kind: {anchor_kind}") from exc
    return f"{prefix}{stable_key}"
