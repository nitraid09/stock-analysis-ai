"""Position cycle assignment for filled orders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Sequence

from stock_analysis_ai.html_generation.exceptions import ContractError

from .contracts import ensure_aware_datetime
from .key_factory import StableKeyFactory


def _to_decimal(value: Any, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:  # pragma: no cover - defensive
        raise ContractError(f"{field_name} must be numeric.") from exc


@dataclass(frozen=True)
class FillEvent:
    """Minimal fill event for cycle assignment."""

    order_id: str
    security_code: str
    signed_quantity: Decimal
    executed_at: datetime | None = None
    fill_status: str = "filled"

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "FillEvent":
        order_id = str(payload.get("order_id", "")).strip()
        security_code = str(payload.get("security_code", "")).strip()
        if not order_id:
            raise ContractError("FillEvent requires order_id.")
        if not security_code:
            raise ContractError("FillEvent requires security_code.")
        executed_at_raw = payload.get("executed_at")
        return cls(
            order_id=order_id,
            security_code=security_code,
            signed_quantity=_to_decimal(payload.get("signed_quantity"), "signed_quantity"),
            executed_at=ensure_aware_datetime(executed_at_raw) if executed_at_raw else None,
            fill_status=str(payload.get("fill_status", "filled")),
        )


@dataclass(frozen=True)
class PositionCycleAssignmentResult:
    """Assignments and registry rows produced by fill processing."""

    assignments: dict[str, str | None]
    registry_rows: tuple[dict[str, Any], ...]


def assign_position_cycles(
    fill_events: Sequence[FillEvent],
    existing_registry_rows: Sequence[Mapping[str, Any]],
    key_factory: StableKeyFactory,
) -> PositionCycleAssignmentResult:
    registry_by_id = {str(row["position_cycle_id"]): dict(row) for row in existing_registry_rows}
    open_cycle_by_security: dict[str, dict[str, Any]] = {}
    for row in registry_by_id.values():
        if row.get("status") == "open":
            security_code = str(row.get("security_code", "")).strip()
            if not security_code:
                raise ContractError("Open position_cycle_registry rows must include security_code.")
            if security_code in open_cycle_by_security:
                raise ContractError(f"Multiple open position cycles exist for {security_code}.")
            open_cycle_by_security[security_code] = row

    assignments: dict[str, str | None] = {}
    sorted_events = sorted(
        fill_events,
        key=lambda event: (
            event.executed_at or datetime.max.replace(tzinfo=timezone.utc),
            event.order_id,
        ),
    )
    for event in sorted_events:
        if event.fill_status != "filled":
            assignments[event.order_id] = None
            continue
        security_code = event.security_code
        current_cycle = open_cycle_by_security.get(security_code)
        delta = event.signed_quantity
        if current_cycle is None:
            if delta <= 0:
                assignments[event.order_id] = None
                continue
            position_cycle_id = key_factory.reserve("position_cycle_id")
            current_cycle = {
                "position_cycle_id": position_cycle_id,
                "security_code": security_code,
                "entry_order_id": event.order_id,
                "status": "open",
                "remaining_quantity": str(delta),
                "opened_by_order_id": event.order_id,
                "closed_by_order_id": None,
            }
            registry_by_id[position_cycle_id] = current_cycle
            open_cycle_by_security[security_code] = current_cycle
            assignments[event.order_id] = position_cycle_id
            continue

        position_cycle_id = str(current_cycle["position_cycle_id"])
        quantity_before = _to_decimal(current_cycle.get("remaining_quantity", "0"), "remaining_quantity")
        quantity_after = quantity_before + delta
        if quantity_after < 0:
            raise ContractError(
                f"position_cycle_id {position_cycle_id} would become negative for {security_code}."
            )
        current_cycle["remaining_quantity"] = str(quantity_after)
        current_cycle["last_order_id"] = event.order_id
        assignments[event.order_id] = position_cycle_id
        if quantity_after == 0:
            current_cycle["status"] = "closed"
            current_cycle["closed_by_order_id"] = event.order_id
            open_cycle_by_security.pop(security_code, None)

    return PositionCycleAssignmentResult(
        assignments=assignments,
        registry_rows=tuple(registry_by_id.values()),
    )
