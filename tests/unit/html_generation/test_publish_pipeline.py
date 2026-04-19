from __future__ import annotations

import json
import shutil
from pathlib import Path

from stock_analysis_ai.html_generation.contracts import PublishRequest
from stock_analysis_ai.html_generation.publish_pipeline import execute_publish


def _base_payload(
    *,
    proposal_ids: tuple[str, ...] = ("P-001",),
    proposal_list_text: str = "active",
    proposal_detail_text: str = "detail",
) -> dict:
    return {
        "change_set": ["proposal"],
        "acceptance_passed": True,
        "shared": {
            "anchor_index": [
                {"id": f"proposal-{proposal_id}", "label": proposal_id} for proposal_id in proposal_ids
            ]
        },
        "screens": {
            "top": {
                "summary_cards": [{"label": "本日要確認", "value": "1件"}],
                "sections": [{"id": "summary", "title": "上段全幅サマリ", "text": "summary"}],
            },
            "proposal_list": {
                "toolbar": [{"label": "評価系列", "value": "AI正式評価"}],
                "sections": [{"id": "active", "title": "アクティブな新規買い提案", "text": proposal_list_text}],
            },
            "proposal_detail": [
                {
                    "proposal_id": proposal_id,
                    "sections": [{"id": "summary", "title": "提案サマリ", "text": f"{proposal_detail_text}-{proposal_id}"}],
                }
                for proposal_id in proposal_ids
            ],
        },
    }


def _review_payload(*, reviews_text: str = "review", month_text: str = "month") -> dict:
    return {
        "change_set": ["review"],
        "shared": {},
        "screens": {
            "reviews": {"sections": [{"id": "reviews", "title": "振り返り一覧", "text": reviews_text}]},
            "monthly_review": [{"month": "2026-04", "sections": [{"id": "summary", "title": "月次数値部", "text": month_text}]}],
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
    result = execute_publish(
        PublishRequest(generation_id="gen-review", payload=_review_payload(), change_set=("review",), archive_month="2026-04"),
        tmp_path,
    )

    assert result.archived is True
    assert (tmp_path / "archive" / "monthly" / "2026-04" / "monthly_review" / "2026-04.html").exists()


def test_latest_publish_failure_preserves_previous_latest(tmp_path: Path, monkeypatch) -> None:
    first_result = execute_publish(
        PublishRequest(generation_id="gen-first", payload=_base_payload(), change_set=("proposal",)),
        tmp_path,
    )
    assert first_result.published is True

    latest_detail = tmp_path / "generated_html" / "latest" / "proposal_detail" / "P-001.html"
    original_html = latest_detail.read_text(encoding="utf-8")

    failing_payload = _base_payload(proposal_detail_text="replacement")
    original_replace = Path.replace

    def failing_replace(self: Path, target, *args, **kwargs):
        target_path = Path(target)
        if self.name.startswith(".latest.incoming-") and target_path.name == "latest":
            raise OSError("simulated latest publish swap failure")
        return original_replace(self, target, *args, **kwargs)

    monkeypatch.setattr(Path, "replace", failing_replace)

    result = execute_publish(
        PublishRequest(generation_id="gen-second", payload=failing_payload, change_set=("proposal",)),
        tmp_path,
    )

    assert result.status == "failed"
    assert result.accepted is True
    assert result.published is False
    assert result.archived is False
    assert "simulated latest publish swap failure" in result.errors[-1]
    assert latest_detail.exists()
    assert latest_detail.read_text(encoding="utf-8") == original_html

    status_payload = json.loads((tmp_path / "generated_html" / "generations" / "gen-second" / "status.json").read_text(encoding="utf-8"))
    assert status_payload["status"] == "failed"
    assert status_payload["accepted"] is True
    assert status_payload["published"] is False
    assert status_payload["archived"] is False
    assert "simulated latest publish swap failure" in status_payload["errors"][-1]
    assert "proposal_detail/P-001.html" in status_payload["rendered_files"]
    assert not any(path.name.startswith(".latest.backup-") for path in (tmp_path / "generated_html").iterdir())
    assert not any(path.name.startswith(".latest.incoming-") for path in (tmp_path / "generated_html").iterdir())


def test_partial_publish_keeps_unrelated_latest_pages(tmp_path: Path) -> None:
    first_result = execute_publish(
        PublishRequest(generation_id="gen-proposal", payload=_base_payload(proposal_list_text="proposal phase"), change_set=("proposal",)),
        tmp_path,
    )
    second_result = execute_publish(
        PublishRequest(generation_id="gen-review", payload=_review_payload(reviews_text="review updated", month_text="month updated"), change_set=("review",)),
        tmp_path,
    )

    proposal_list = tmp_path / "generated_html" / "latest" / "proposal_list" / "index.html"
    reviews_page = tmp_path / "generated_html" / "latest" / "reviews" / "index.html"
    monthly_review = tmp_path / "generated_html" / "latest" / "monthly_review" / "2026-04.html"

    assert first_result.status == "success"
    assert second_result.status == "success"
    assert proposal_list.exists()
    assert "proposal phase" in proposal_list.read_text(encoding="utf-8")
    assert reviews_page.exists()
    assert "review updated" in reviews_page.read_text(encoding="utf-8")
    assert monthly_review.exists()
    assert "month updated" in monthly_review.read_text(encoding="utf-8")


def test_partial_publish_replaces_affected_screen_subtree_without_stale_files(tmp_path: Path) -> None:
    first_result = execute_publish(
        PublishRequest(
            generation_id="gen-first",
            payload=_base_payload(proposal_ids=("P-001", "P-002"), proposal_detail_text="initial"),
            change_set=("proposal",),
        ),
        tmp_path,
    )
    second_result = execute_publish(
        PublishRequest(
            generation_id="gen-second",
            payload=_base_payload(proposal_ids=("P-001",), proposal_detail_text="replacement"),
            change_set=("proposal",),
        ),
        tmp_path,
    )

    proposal_detail_root = tmp_path / "generated_html" / "latest" / "proposal_detail"
    retained_page = proposal_detail_root / "P-001.html"
    stale_page = proposal_detail_root / "P-002.html"

    assert first_result.status == "success"
    assert second_result.status == "success"
    assert retained_page.exists()
    assert "replacement-P-001" in retained_page.read_text(encoding="utf-8")
    assert not stale_page.exists()


def test_archive_collision_records_failure_but_keeps_latest(tmp_path: Path) -> None:
    first_result = execute_publish(
        PublishRequest(generation_id="gen-archive-first", payload=_review_payload(), change_set=("review",), archive_month="2026-04"),
        tmp_path,
    )
    assert first_result.published is True
    assert first_result.archived is True

    latest_monthly = tmp_path / "generated_html" / "latest" / "monthly_review" / "2026-04.html"
    latest_before_collision = latest_monthly.read_text(encoding="utf-8")

    result = execute_publish(
        PublishRequest(
            generation_id="gen-archive-second",
            payload=_review_payload(reviews_text="review updated", month_text="month updated"),
            change_set=("review",),
            archive_month="2026-04",
        ),
        tmp_path,
    )

    assert result.status == "failed"
    assert result.accepted is True
    assert result.published is True
    assert result.archived is False
    assert any("Archive target already exists" in error for error in result.errors)
    assert latest_monthly.exists()
    assert "month updated" in latest_monthly.read_text(encoding="utf-8")
    assert latest_monthly.read_text(encoding="utf-8") != latest_before_collision

    status_payload = json.loads((tmp_path / "generated_html" / "generations" / "gen-archive-second" / "status.json").read_text(encoding="utf-8"))
    assert status_payload["status"] == "failed"
    assert status_payload["accepted"] is True
    assert status_payload["published"] is True
    assert status_payload["archived"] is False
    assert any("Archive target already exists" in error for error in status_payload["errors"])


def test_stage_only_does_not_update_existing_latest(tmp_path: Path) -> None:
    execute_publish(
        PublishRequest(generation_id="gen-published", payload=_base_payload(), change_set=("proposal",)),
        tmp_path,
    )

    latest_detail = tmp_path / "generated_html" / "latest" / "proposal_detail" / "P-001.html"
    published_html = latest_detail.read_text(encoding="utf-8")

    stage_only_payload = _base_payload()
    stage_only_payload["screens"]["proposal_detail"][0]["sections"][0]["text"] = "stage-only change"
    result = execute_publish(
        PublishRequest(
            generation_id="gen-stage-only",
            payload=stage_only_payload,
            change_set=("proposal",),
            publish_mode="stage_only",
        ),
        tmp_path,
    )

    assert result.status == "staged"
    assert result.accepted is True
    assert result.published is False
    assert result.archived is False
    assert latest_detail.read_text(encoding="utf-8") == published_html
