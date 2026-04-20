"""CLI entry point for HTML generation staging and publish."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .contracts import PublishRequest
from .paths import discover_project_root
from .publish_pipeline import execute_publish


def _load_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_json_argument(raw_value: str | None, *, argument_name: str) -> Any:
    if raw_value is None:
        return None
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{argument_name} must be valid JSON.") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate and publish stock-analysis HTML pages.")
    parser.add_argument("--payload", required=True, help="Path to a JSON payload file.")
    parser.add_argument("--generation-id", required=True, help="Generation identifier.")
    parser.add_argument(
        "--publish-mode",
        default="publish",
        choices=("publish", "stage_only"),
        help="publish updates latest on acceptance, stage_only keeps only generation output.",
    )
    parser.add_argument("--output-root", default=str(discover_project_root()), help="Project root that contains generated_html/ and archive/.")
    parser.add_argument("--archive-target-period", default=None, help="Optional YYYY-MM archive target.")
    parser.add_argument(
        "--change-set-json",
        default=None,
        help="Optional JSON array for final record-unit change set. Overrides payload value.",
    )
    parser.add_argument(
        "--default-display-context-json",
        default=None,
        help="Optional JSON object for default display context. Overrides payload value.",
    )
    parser.add_argument(
        "--evaluation-series",
        nargs="*",
        default=None,
        help="Optional evaluation series list. Overrides payload value when supplied.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = _load_payload(Path(args.payload))
    change_set = _load_json_argument(args.change_set_json, argument_name="--change-set-json")
    default_display_context = _load_json_argument(
        args.default_display_context_json,
        argument_name="--default-display-context-json",
    )
    request = PublishRequest(
        generation_id=args.generation_id,
        payload=payload,
        change_set=change_set or payload.get("final_record_unit_change_set", payload.get("change_set", [])),
        publish_mode=args.publish_mode,
        generated_at=payload.get("generated_at"),
        acceptance_passed=bool(payload.get("acceptance_passed", True)),
        archive_target_period=(
            args.archive_target_period
            or payload.get("archive_target_period")
            or payload.get("archive_month")
        ),
        additional_screens=payload.get("extra_screens", []),
        default_display_context=(
            default_display_context
            or payload.get("default_display_context")
            or payload.get("display_condition")
        ),
        evaluation_series=args.evaluation_series or payload.get("evaluation_series", []),
    )
    result = execute_publish(request, Path(args.output_root))
    print(json.dumps(result.to_dict(), ensure_ascii=False))
    if result.status in {"render_failed", "publish_failed"}:
        return 1
    if args.publish_mode == "publish" and not result.published:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
