from __future__ import annotations

import json
from pathlib import Path

from stock_analysis_ai.html_generation.contracts import PublishRequest
from stock_analysis_ai.html_generation.publish_pipeline import execute_publish


def _base_payload() -> dict:
    return {
        "change_set": ["proposal"],
        "acceptance_passed": True,
        "shared": {
            "anchor_index": [
                {"id": "proposal-P-001", "label": "P-001"},
            ]
        },
        "screens": {
            "top": {
                "summary_cards": [{"label": "本日要確認", "value": "1件"}],
                "sections": [{"id": "summary", "title": "上段全幅サマリ", "text": "summary"}],
            },
            "proposal_list": {
                "toolbar": [{"label": "評価系列", "value": "AI正式評価"}],
                "sections": [{"id": "active", "title": "アクティブな新規買い提案", "text": "active"}],
            },
            "proposal_detail": [
                {
                    "proposal_id": "P-001",
                    "sections": [{"id": "summary", "title": "提案サマリ", "text": "detail"}],
                }
            ],
        },
    }


def test_successful_generation_publishes_latest(tmp_path: Path) -> None:
    result = execute_publish(
        PublishRequest(generation_id="gen-success", payload=_base_payload(), change_set=("proposal",)),
        tmp_path,
    )

    assert result.published is True
    assert (tmp_path / "generated_html" / "latest" / "top" / "index.html").exists()
    assert (tmp_path / "generated_html" / "latest" / "proposal_detail" / "P-001.html").exists()


def test_failed_generation_does_not_dirty_latest(tmp_path: Path) -> None:
    success_request = PublishRequest(generation_id="gen-ok", payload=_base_payload(), change_set=("proposal",))
    execute_publish(success_request, tmp_path)

    failed_payload = _base_payload()
    del failed_payload["screens"]["proposal_list"]
    result = execute_publish(
        PublishRequest(generation_id="gen-fail", payload=failed_payload, change_set=("proposal",)),
        tmp_path,
    )

    assert result.status == "failed"
    latest_path = tmp_path / "generated_html" / "latest" / "proposal_list" / "index.html"
    assert latest_path.exists()
    status_payload = json.loads((tmp_path / "generated_html" / "generations" / "gen-fail" / "status.json").read_text(encoding="utf-8"))
    assert status_payload["status"] == "failed"


def test_publish_unit_requires_complete_affected_screens(tmp_path: Path) -> None:
    payload = _base_payload()
    payload["acceptance_passed"] = False
    result = execute_publish(
        PublishRequest(generation_id="gen-staged", payload=payload, change_set=("proposal",), acceptance_passed=False),
        tmp_path,
    )

    assert result.published is False
    assert result.status == "staged"
    assert not (tmp_path / "generated_html" / "latest").exists()


def test_monthly_archive_copies_only_successful_generation(tmp_path: Path) -> None:
    payload = {
        "change_set": ["review"],
        "shared": {},
        "screens": {
            "reviews": {"sections": [{"id": "reviews", "title": "振り返り一覧", "text": "review"}]},
            "monthly_review": [{"month": "2026-04", "sections": [{"id": "summary", "title": "月次数値部", "text": "month"}]}],
        },
    }
    result = execute_publish(
        PublishRequest(generation_id="gen-review", payload=payload, change_set=("review",), archive_month="2026-04"),
        tmp_path,
    )

    assert result.archived is True
    assert (tmp_path / "archive" / "monthly" / "2026-04" / "monthly_review" / "2026-04.html").exists()
