"""Reconciliation status handling and evidence requirements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from stock_analysis_ai.html_generation.exceptions import ContractError

from .contracts import EvidenceParent, RECONCILIATION_STATUSES


@dataclass(frozen=True)
class ReconciliationContext:
    """Context used to determine whether evidence references are mandatory."""

    from_daily_note: bool = False
    has_difference: bool = False
    cancelled_or_expired: bool = False
    correction_order: bool = False
    excluded_trade: bool = False
    incident: bool = False


def requires_evidence(context: ReconciliationContext) -> bool:
    return any(
        (
            context.from_daily_note,
            context.has_difference,
            context.cancelled_or_expired,
            context.correction_order,
            context.excluded_trade,
            context.incident,
        )
    )


def _normalize_evidence_rows(evidence_rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    normalized: list[dict[str, Any]] = []
    for row in evidence_rows:
        parent = row.get("parent")
        if not isinstance(parent, Mapping):
            raise ContractError("evidence_ref rows must provide parent.")
        normalized.append(
            {
                **dict(row),
                "parent": EvidenceParent.from_mapping(parent).to_dict(),
            }
        )
    return tuple(normalized)


def apply_reconciliation(
    order_row: Mapping[str, Any],
    *,
    reconciliation_status: str,
    context: ReconciliationContext,
    evidence_rows: Sequence[Mapping[str, Any]] = (),
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    if reconciliation_status not in RECONCILIATION_STATUSES:
        raise ContractError(f"Unsupported reconciliation_status: {reconciliation_status}")
    if not order_row.get("order_status"):
        raise ContractError("order_status must be present independently from reconciliation_status.")
    normalized_evidence = _normalize_evidence_rows(evidence_rows)
    if reconciliation_status == "evidence_replaced" and not normalized_evidence:
        raise ContractError("evidence_replaced requires at least one evidence_ref row.")
    if requires_evidence(context) and not normalized_evidence:
        raise ContractError("Evidence references are required for the given reconciliation context.")
    updated_row = dict(order_row)
    updated_row["reconciliation_status"] = reconciliation_status
    return updated_row, normalized_evidence


def summarize_reconciliation(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    summary = {status: 0 for status in RECONCILIATION_STATUSES}
    for row in rows:
        status = row.get("reconciliation_status")
        if status in summary:
            summary[status] += 1
    return summary
