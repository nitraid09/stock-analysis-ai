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
    parser.add_argument("--archive-month", default=None, help="Optional YYYY-MM archive target.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = _load_payload(Path(args.payload))
    request = PublishRequest(
        generation_id=args.generation_id,
        payload=payload,
        change_set=payload.get("change_set", []),
        publish_mode=args.publish_mode,
        generated_at=payload.get("generated_at"),
        acceptance_passed=bool(payload.get("acceptance_passed", True)),
        archive_month=args.archive_month or payload.get("archive_month"),
        additional_screens=payload.get("extra_screens", []),
    )
    result = execute_publish(request, Path(args.output_root))
    print(json.dumps(result.to_dict(), ensure_ascii=False))
    if result.status == "failed":
        return 1
    if args.publish_mode == "publish" and not result.published:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
