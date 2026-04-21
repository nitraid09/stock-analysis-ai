from __future__ import annotations

import json
from pathlib import Path

from stock_analysis_ai.night_update.cli import main


def test_cli_runs_night_update_with_explicit_generation_and_publish_mode(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "html_payload": {
                    "screens": {
                        "reviews": {
                            "sections": [{"id": "reviews", "title": "振り返り一覧", "text": "review"}],
                        },
                        "monthly_review": [
                            {
                                "month": "2026-04",
                                "sections": [{"id": "summary", "title": "月次", "text": "month"}],
                            }
                        ],
                    }
                },
                "evaluation_series": ["ai_official"],
                "table_updates": {
                    "review_header": [
                        {
                            "review_id": "review-000001",
                            "primary_subject": {"subject_type": "period", "subject_id": "2026-04"},
                        }
                    ]
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--request",
            str(request_path),
            "--generation-id",
            "gen-cli",
            "--publish-mode",
            "publish",
            "--output-root",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "master" / "storage" / "master_storage.sqlite3").exists()
    assert (tmp_path / "generated_html" / "latest" / "reviews" / "index.html").exists()
