"""Night update formalization orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from stock_analysis_ai.html_generation.contracts import PublishMode, PublishResult
from stock_analysis_ai.html_generation.exceptions import ContractError
from stock_analysis_ai.master_storage import MasterStorageRepository
from stock_analysis_ai.master_storage.contracts import MasterStorageSnapshot
from stock_analysis_ai.master_storage.change_set import ChangeSet, resolve_change_set
from stock_analysis_ai.master_storage.key_factory import StableKeyFactory
from stock_analysis_ai.master_storage.position_cycle import FillEvent, assign_position_cycles
from stock_analysis_ai.master_storage.reconciliation import (
    ReconciliationContext,
    apply_reconciliation,
    summarize_reconciliation,
)

from .generation_bridge import GenerationBridgeInput, invoke_generation_bridge
from .operation_log import OperationLogEntry, OperationLogRepository


@dataclass(frozen=True)
class NightOrderUpdate:
    """Order update payload that preserves status/reconciliation separation."""

    order_header: Mapping[str, Any]
    fills: Sequence[Mapping[str, Any]] = ()
    reconciliation_context: ReconciliationContext = field(default_factory=ReconciliationContext)
    evidence_refs: Sequence[Mapping[str, Any]] = ()


@dataclass(frozen=True)
class NightUpdateRequest:
    """Minimum orchestration request for master update and HTML generation."""

    generation_id: str
    publish_mode: PublishMode
    html_payload: Mapping[str, Any]
    display_condition: Mapping[str, Any] | None = None
    evaluation_series: Sequence[str] = ()
    order_updates: Sequence[NightOrderUpdate] = ()
    table_updates: Mapping[str, Sequence[Mapping[str, Any]]] = field(default_factory=dict)
    additional_record_units: Sequence[str] = ()
    archive_month: str | None = None
    acceptance_passed: bool = True

    def __post_init__(self) -> None:
        if not self.generation_id.strip():
            raise ContractError("generation_id must not be empty.")


@dataclass(frozen=True)
class NightUpdateResult:
    """End result of the night-update formalization run."""

    change_set: ChangeSet | None
    publish_result: PublishResult | None
    master_update_status: str
    reconciliation_status_summary: Mapping[str, int]
    log_path: str
    failure_reason: str | None = None


def _merge_table_changes(
    destination: dict[str, list[dict[str, Any]]],
    source: Mapping[str, Sequence[Mapping[str, Any]]],
) -> None:
    for table_name, rows in source.items():
        if not rows:
            continue
        destination.setdefault(table_name, [])
        destination[table_name].extend(dict(row) for row in rows)


def _process_order_updates(
    request: NightUpdateRequest,
    snapshot: MasterStorageSnapshot,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int], StableKeyFactory]:
    key_factory = StableKeyFactory.from_snapshot(snapshot)
    existing_registry_rows = snapshot.tables["position_cycle_registry"]
    processed_headers: list[dict[str, Any]] = []
    processed_fills: list[dict[str, Any]] = []
    processed_evidence: list[dict[str, Any]] = []
    fill_events: list[FillEvent] = []

    for update in request.order_updates:
        order_header = dict(update.order_header)
        order_id = str(order_header.get("order_id", "")).strip()
        if not order_id:
            raise ContractError("order_header requires order_id.")
        reconciliation_status = str(order_header.get("reconciliation_status", "")).strip()
        updated_order, normalized_evidence = apply_reconciliation(
            order_header,
            reconciliation_status=reconciliation_status,
            context=update.reconciliation_context,
            evidence_rows=update.evidence_refs,
        )
        processed_headers.append(updated_order)
        processed_evidence.extend(dict(row) for row in normalized_evidence)
        for fill_row in update.fills:
            normalized_fill = dict(fill_row)
            normalized_fill["order_id"] = order_id
            processed_fills.append(normalized_fill)
            fill_events.append(FillEvent.from_mapping(normalized_fill))

    cycle_result = assign_position_cycles(fill_events, existing_registry_rows, key_factory)
    assignment_by_order_id = cycle_result.assignments
    for header in processed_headers:
        assigned_cycle_id = assignment_by_order_id.get(str(header["order_id"]))
        if assigned_cycle_id is not None:
            header["position_cycle_id"] = assigned_cycle_id
    for fill_row in processed_fills:
        assigned_cycle_id = assignment_by_order_id.get(str(fill_row["order_id"]))
        if assigned_cycle_id is not None:
            fill_row["position_cycle_id"] = assigned_cycle_id

    return (
        {
            "order_header": processed_headers,
            "order_fill": processed_fills,
            "position_cycle_registry": list(cycle_result.registry_rows),
            "evidence_ref": processed_evidence,
        },
        summarize_reconciliation(processed_headers),
        key_factory,
    )


def _derive_publish_status(result: PublishResult | None, publish_mode: PublishMode) -> tuple[str, str, str]:
    if result is None:
        return ("not_started", "not_started", "not_attempted")

    if publish_mode == "stage_only":
        return ("not_requested", "not_requested", "not_attempted")

    restore_status_map = {
        "preserved": "preserved",
        "restored": "restored",
        "published": "published",
        "unchanged": "not_needed",
    }
    restore_status = restore_status_map[result.latest_action]

    if result.status == "published":
        archive_status = "archived" if result.archived else "not_requested"
        return ("published", archive_status, restore_status)
    if result.status == "published_with_archive_failure":
        return ("published", "failed", restore_status)
    if result.status == "publish_failed":
        return ("publish_failed", "not_attempted", restore_status)
    if result.status == "render_failed":
        return ("render_failed", "not_attempted", restore_status)
    if result.status == "staged":
        return ("not_attempted", "not_attempted", restore_status)

    raise ContractError(f"Unsupported publish result status: {result.status}")


def execute_night_update(
    request: NightUpdateRequest,
    *,
    project_root: Path,
) -> NightUpdateResult:
    repository = MasterStorageRepository(project_root)
    log_repository = OperationLogRepository(project_root)
    table_changes: dict[str, list[dict[str, Any]]] = {}
    reconciliation_summary: dict[str, int] = {}
    master_update_status = "failed"
    publish_result: PublishResult | None = None
    failure_reason: str | None = None
    change_set: ChangeSet | None = None

    try:
        with repository.transaction() as transaction:
            current_snapshot = transaction.load_snapshot()
            if request.order_updates:
                order_changes, reconciliation_summary, _ = _process_order_updates(request, current_snapshot)
                _merge_table_changes(table_changes, order_changes)
            _merge_table_changes(table_changes, request.table_updates)

            updated_snapshot = repository.apply_table_changes(current_snapshot, table_changes)
            transaction.replace_snapshot(updated_snapshot)
            master_update_status = "success"

        change_set = resolve_change_set(
            generation_id=request.generation_id,
            publish_mode=request.publish_mode,
            table_changes=table_changes,
            changed_evaluation_series=request.evaluation_series,
            monthly_archive_target=request.archive_month,
            additional_record_units=request.additional_record_units,
        )
        bridge_input = GenerationBridgeInput(
            generation_id=request.generation_id,
            publish_mode=request.publish_mode,
            change_set=change_set,
            payload=request.html_payload,
            display_condition=request.display_condition,
            evaluation_series=request.evaluation_series,
            acceptance_passed=request.acceptance_passed,
            archive_month=request.archive_month,
        )
        publish_result = invoke_generation_bridge(bridge_input, output_root=project_root)
    except Exception as exc:
        failure_reason = str(exc)
    publish_status, archive_status, restore_status = _derive_publish_status(
        publish_result,
        request.publish_mode,
    )
    generation_status = publish_result.status if publish_result is not None else "not_started"
    entry = OperationLogEntry(
        generation_id=request.generation_id,
        master_update_status=master_update_status,
        reconciliation_status_summary=reconciliation_summary,
        generation_status=generation_status,
        publish_status=publish_status,
        archive_status=archive_status,
        restore_status=restore_status,
        failure_reason=failure_reason or (
            publish_result.errors[-1] if publish_result and publish_result.errors else None
        ),
    )
    log_path = log_repository.append(entry)
    return NightUpdateResult(
        change_set=change_set,
        publish_result=publish_result,
        master_update_status=master_update_status,
        reconciliation_status_summary=reconciliation_summary,
        log_path=str(log_path),
        failure_reason=entry.failure_reason,
    )
