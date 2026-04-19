from __future__ import annotations

import json

from stock_analysis_ai.master_storage import MasterStorageRepository
from stock_analysis_ai.night_update.orchestrator import NightUpdateRequest, execute_night_update


def _proposal_payload(*, list_text: str = "active", detail_text: str = "detail") -> dict:
    return {
        "screens": {
            "top": {
                "summary_cards": [{"label": "本日要確認", "value": "1件"}],
                "sections": [{"id": "summary", "title": "上段全幅サマリ", "text": "summary"}],
            },
            "proposal_list": {
                "toolbar": [{"label": "評価系列", "value": "AI正式評価"}],
                "sections": [{"id": "active", "title": "提案一覧", "text": list_text}],
            },
            "proposal_detail": [
                {
                    "proposal_id": "proposal-000001",
                    "sections": [{"id": "summary", "title": "提案サマリ", "text": detail_text}],
                }
            ],
        }
    }


def _review_payload(*, reviews_text: str = "review", month_text: str = "month") -> dict:
    return {
        "screens": {
            "reviews": {
                "sections": [{"id": "reviews", "title": "振り返り一覧", "text": reviews_text}],
            },
            "monthly_review": [
                {
                    "month": "2026-04",
                    "sections": [{"id": "summary", "title": "月次", "text": month_text}],
                }
            ],
        }
    }


def _us_pilot_payload(*, pilot_text: str = "pilot") -> dict:
    return {
        "screens": {
            "us_pilot_performance": {
                "sections": [{"id": "pilot_status", "title": "パイロット状況", "text": pilot_text}],
            }
        }
    }


def test_generation_failure_does_not_roll_back_master_or_dirty_latest(tmp_path) -> None:
    success = execute_night_update(
        NightUpdateRequest(
            generation_id="gen-success",
            publish_mode="publish",
            html_payload=_proposal_payload(),
            display_condition={"series": "ai_official"},
            table_updates={
                "proposal_header": [{"proposal_id": "proposal-000001"}],
            },
        ),
        project_root=tmp_path,
    )
    assert success.publish_result is not None
    latest_detail = tmp_path / "generated_html" / "latest" / "proposal_detail" / "proposal-000001.html"
    previous_latest = latest_detail.read_text(encoding="utf-8")

    failed = execute_night_update(
        NightUpdateRequest(
            generation_id="gen-failed",
            publish_mode="publish",
            html_payload={"screens": {"top": {"sections": []}, "proposal_detail": []}},
            display_condition={"series": "ai_official"},
            table_updates={
                "proposal_header": [{"proposal_id": "proposal-000002"}],
            },
        ),
        project_root=tmp_path,
    )

    assert failed.master_update_status == "success"
    assert failed.publish_result is not None
    assert failed.publish_result.status == "failed"
    assert latest_detail.read_text(encoding="utf-8") == previous_latest
    repository = MasterStorageRepository(tmp_path)
    proposal_ids = {row["proposal_id"] for row in repository.load_snapshot().tables["proposal_header"]}
    assert proposal_ids == {"proposal-000001", "proposal-000002"}


def test_archive_failure_is_recorded_separately_from_latest_publish(tmp_path) -> None:
    execute_night_update(
        NightUpdateRequest(
            generation_id="gen-review-first",
            publish_mode="publish",
            html_payload=_review_payload(),
            display_condition={"series": "ai_official"},
            table_updates={
                "review_header": [
                    {
                        "review_id": "review-000001",
                        "primary_subject": {"subject_type": "period", "subject_id": "2026-04"},
                    }
                ],
            },
            archive_month="2026-04",
        ),
        project_root=tmp_path,
    )

    second = execute_night_update(
        NightUpdateRequest(
            generation_id="gen-review-second",
            publish_mode="publish",
            html_payload=_review_payload(reviews_text="review-updated", month_text="month-updated"),
            display_condition={"series": "ai_official"},
            table_updates={
                "review_header": [
                    {
                        "review_id": "review-000002",
                        "primary_subject": {"subject_type": "period", "subject_id": "2026-04"},
                    }
                ],
            },
            archive_month="2026-04",
        ),
        project_root=tmp_path,
    )

    assert second.publish_result is not None
    assert second.publish_result.published is True
    assert second.publish_result.archived is False
    latest_month = tmp_path / "generated_html" / "latest" / "monthly_review" / "2026-04.html"
    assert "month-updated" in latest_month.read_text(encoding="utf-8")
    log_lines = (tmp_path / "logs" / "night_update_operations.jsonl").read_text(encoding="utf-8").splitlines()
    last_log = json.loads(log_lines[-1])
    assert last_log["publish_status"] == "published"
    assert last_log["archive_status"] == "failed"


def test_merged_publish_keeps_unrelated_latest_screens(tmp_path) -> None:
    execute_night_update(
        NightUpdateRequest(
            generation_id="gen-proposal",
            publish_mode="publish",
            html_payload=_proposal_payload(list_text="proposal-phase"),
            display_condition={"series": "ai_official"},
            table_updates={
                "proposal_header": [{"proposal_id": "proposal-000001"}],
            },
        ),
        project_root=tmp_path,
    )
    execute_night_update(
        NightUpdateRequest(
            generation_id="gen-review",
            publish_mode="publish",
            html_payload=_review_payload(reviews_text="review-phase", month_text="month-phase"),
            display_condition={"series": "ai_official"},
            table_updates={
                "review_header": [
                    {
                        "review_id": "review-000001",
                        "primary_subject": {"subject_type": "period", "subject_id": "2026-04"},
                    }
                ],
            },
        ),
        project_root=tmp_path,
    )

    proposal_list = tmp_path / "generated_html" / "latest" / "proposal_list" / "index.html"
    reviews = tmp_path / "generated_html" / "latest" / "reviews" / "index.html"
    assert proposal_list.exists()
    assert reviews.exists()
    assert "proposal-phase" in proposal_list.read_text(encoding="utf-8")
    assert "review-phase" in reviews.read_text(encoding="utf-8")


def test_non_standard_evidence_parent_is_rejected_before_generation(tmp_path) -> None:
    result = execute_night_update(
        NightUpdateRequest(
            generation_id="gen-invalid-evidence",
            publish_mode="publish",
            html_payload=_proposal_payload(),
            display_condition={"series": "ai_official"},
            table_updates={
                "order_header": [
                    {
                        "order_id": "order-000001",
                        "order_status": "filled",
                        "reconciliation_status": "reconciled",
                    }
                ],
                "position_cycle_registry": [{"position_cycle_id": "position-cycle-000001"}],
                "evidence_ref": [
                    {
                        "parent": {
                            "parent_type": "position_cycle",
                            "parent_id": "position-cycle-000001",
                        },
                        "reference_path": "evidence/orders/position-cycle-000001.png",
                    }
                ],
            },
        ),
        project_root=tmp_path,
    )

    assert result.master_update_status == "failed"
    assert result.publish_result is None
    assert result.failure_reason is not None
    assert "Unsupported evidence parent type" in result.failure_reason


def test_us_pilot_generation_runs_only_when_us_pilot_rows_change(tmp_path) -> None:
    result = execute_night_update(
        NightUpdateRequest(
            generation_id="gen-us-pilot",
            publish_mode="publish",
            html_payload=_us_pilot_payload(),
            display_condition={"series": "ai_official"},
            table_updates={
                "us_pilot_header": [{"us_pilot_id": "us-pilot-000001"}],
            },
        ),
        project_root=tmp_path,
    )

    assert result.master_update_status == "success"
    assert result.change_set is not None
    assert result.change_set.changed_record_units == ("us_pilot",)
    pilot_page = tmp_path / "generated_html" / "latest" / "us_pilot_performance" / "index.html"
    assert pilot_page.exists()
