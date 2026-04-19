"""Change-set resolution from master storage mutations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from stock_analysis_ai.html_generation.contracts import PublishMode
from stock_analysis_ai.html_generation.exceptions import ContractError

RECORD_UNITS: tuple[str, ...] = (
    "proposal",
    "order",
    "holding_snapshot",
    "review",
    "us_virtual",
    "us_pilot",
)

TABLE_TO_RECORD_UNIT: dict[str, str] = {
    "proposal_header": "proposal",
    "proposal_target": "proposal",
    "order_header": "order",
    "order_fill": "order",
    "holding_snapshot_header": "holding_snapshot",
    "holding_snapshot_position": "holding_snapshot",
    "review_header": "review",
    "position_cycle_registry": "order",
    "us_virtual_watch_header": "us_virtual",
    "us_pilot_header": "us_pilot",
}

PARENT_KEY_FIELDS: dict[str, tuple[str, ...]] = {
    "proposal": ("proposal_id",),
    "order": ("order_id", "position_cycle_id", "proposal_id"),
    "holding_snapshot": ("snapshot_id",),
    "review": ("review_id",),
    "us_virtual": ("us_virtual_watch_id",),
    "us_pilot": ("us_pilot_id",),
}

EVIDENCE_PARENT_UNIT: dict[str, str] = {
    "proposal": "proposal",
    "order": "order",
    "holding_snapshot": "holding_snapshot",
    "review": "review",
    "position_cycle": "order",
    "us_virtual_watch": "us_virtual",
    "us_pilot": "us_pilot",
}


@dataclass(frozen=True)
class ChangeSet:
    """Resolved record-unit change set passed into the HTML bridge."""

    generation_id: str
    publish_mode: PublishMode
    changed_record_units: tuple[str, ...]
    changed_parent_keys: dict[str, tuple[str, ...]]
    changed_evaluation_series: tuple[str, ...]
    monthly_archive_target: str | None = None

    def __post_init__(self) -> None:
        if not self.generation_id.strip():
            raise ContractError("generation_id must not be empty.")
        if not self.changed_record_units:
            raise ContractError("changed_record_units must not be empty.")
        for record_unit in self.changed_record_units:
            if record_unit not in RECORD_UNITS:
                raise ContractError(f"Unsupported record unit: {record_unit}")

    def to_html_change_tokens(self) -> tuple[str, ...]:
        return self.changed_record_units


def _append_parent_keys(
    record_unit: str,
    row: Mapping[str, Any],
    accumulator: dict[str, list[str]],
) -> None:
    for field_name in PARENT_KEY_FIELDS.get(record_unit, ()):
        value = row.get(field_name)
        if isinstance(value, str) and value.strip() and value not in accumulator[record_unit]:
            accumulator[record_unit].append(value)


def _resolve_evidence_record_unit(row: Mapping[str, Any]) -> tuple[str, str]:
    parent = row.get("parent")
    if not isinstance(parent, Mapping):
        raise ContractError("evidence_ref rows must provide parent.")
    parent_type = parent.get("parent_type")
    parent_id = parent.get("parent_id")
    if parent_type not in EVIDENCE_PARENT_UNIT:
        raise ContractError(f"Unsupported evidence parent type: {parent_type}")
    if not isinstance(parent_id, str) or not parent_id.strip():
        raise ContractError("evidence_ref parent_id must not be empty.")
    return EVIDENCE_PARENT_UNIT[parent_type], parent_id


def resolve_change_set(
    *,
    generation_id: str,
    publish_mode: PublishMode,
    table_changes: Mapping[str, Sequence[Mapping[str, Any]]],
    changed_evaluation_series: Sequence[str] = (),
    monthly_archive_target: str | None = None,
    additional_record_units: Sequence[str] = (),
) -> ChangeSet:
    ordered_units: list[str] = []
    parent_keys: dict[str, list[str]] = {record_unit: [] for record_unit in RECORD_UNITS}

    def add_record_unit(record_unit: str) -> None:
        if record_unit not in RECORD_UNITS:
            raise ContractError(f"Unsupported record unit: {record_unit}")
        if record_unit not in ordered_units:
            ordered_units.append(record_unit)

    for table_name, rows in table_changes.items():
        if not rows:
            continue
        if table_name == "evidence_ref":
            for row in rows:
                record_unit, parent_id = _resolve_evidence_record_unit(row)
                add_record_unit(record_unit)
                if parent_id not in parent_keys[record_unit]:
                    parent_keys[record_unit].append(parent_id)
            continue
        if table_name not in TABLE_TO_RECORD_UNIT:
            raise ContractError(f"Unsupported table change: {table_name}")
        record_unit = TABLE_TO_RECORD_UNIT[table_name]
        add_record_unit(record_unit)
        for row in rows:
            _append_parent_keys(record_unit, row, parent_keys)

    for record_unit in additional_record_units:
        add_record_unit(record_unit)

    return ChangeSet(
        generation_id=generation_id,
        publish_mode=publish_mode,
        changed_record_units=tuple(ordered_units),
        changed_parent_keys={
            record_unit: tuple(parent_keys[record_unit])
            for record_unit in ordered_units
        },
        changed_evaluation_series=tuple(changed_evaluation_series),
        monthly_archive_target=monthly_archive_target,
    )
