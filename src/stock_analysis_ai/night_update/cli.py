"""CLI entry point for night-update formalization."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from stock_analysis_ai.html_generation.paths import discover_project_root
from stock_analysis_ai.master_storage.reconciliation import ReconciliationContext

from .orchestrator import NightOrderUpdate, NightUpdateRequest, execute_night_update


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the night-update formalization flow.")
    parser.add_argument("--request", required=True, help="Path to night-update request JSON.")
    parser.add_argument("--generation-id", required=True, help="Generation identifier.")
    parser.add_argument(
        "--publish-mode",
        default="publish",
        choices=("publish", "stage_only"),
        help="publish updates latest on acceptance, stage_only keeps generation output only.",
    )
    parser.add_argument("--output-root", default=str(discover_project_root()), help="Project root.")
    return parser


def _build_order_updates(payload: dict[str, Any]) -> tuple[NightOrderUpdate, ...]:
    updates: list[NightOrderUpdate] = []
    for raw_update in payload.get("order_updates", []):
        context = raw_update.get("reconciliation_context", {})
        updates.append(
            NightOrderUpdate(
                order_header=raw_update.get("order_header", {}),
                fills=tuple(raw_update.get("fills", [])),
                reconciliation_context=ReconciliationContext(**context),
                evidence_refs=tuple(raw_update.get("evidence_refs", [])),
            )
        )
    return tuple(updates)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = _load_json(Path(args.request))
    request = NightUpdateRequest(
        generation_id=args.generation_id,
        publish_mode=args.publish_mode,
        html_payload=payload["html_payload"],
        display_condition=payload.get("display_condition"),
        evaluation_series=tuple(payload.get("evaluation_series", [])),
        order_updates=_build_order_updates(payload),
        table_updates=payload.get("table_updates", {}),
        additional_record_units=tuple(payload.get("additional_record_units", [])),
        archive_month=payload.get("archive_month"),
        acceptance_passed=bool(payload.get("acceptance_passed", True)),
    )
    result = execute_night_update(request, project_root=Path(args.output_root))
    output = {
        "generation_id": args.generation_id,
        "master_update_status": result.master_update_status,
        "changed_record_units": list(result.change_set.changed_record_units) if result.change_set else [],
        "changed_parent_keys": (
            {
                key: list(values) for key, values in result.change_set.changed_parent_keys.items()
            }
            if result.change_set
            else {}
        ),
        "generation_status": result.publish_result.status if result.publish_result else "not_started",
        "publish_status": result.publish_result.published if result.publish_result else False,
        "archive_status": result.publish_result.archived if result.publish_result else False,
        "log_path": result.log_path,
        "failure_reason": result.failure_reason,
    }
    print(json.dumps(output, ensure_ascii=False))
    if result.failure_reason:
        return 1
    if args.publish_mode == "publish" and result.publish_result and not result.publish_result.published:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
