from __future__ import annotations

from stock_analysis_ai.html_generation.contracts import RecordUnitChange
from stock_analysis_ai.html_generation.screen_registry import (
    build_screen_output_path,
    list_screen_ids,
    resolve_affected_screens,
)


def test_required_screens_are_registered() -> None:
    screen_ids = list_screen_ids()
    assert screen_ids == (
        "top",
        "market_overview",
        "proposal_list",
        "proposal_detail",
        "orders",
        "holdings",
        "performance",
        "monthly_review",
        "reviews",
        "us_watch",
        "us_virtual_performance",
        "us_pilot_performance",
        "excluded_trades",
    )


def test_natural_key_screens_render_individual_paths() -> None:
    assert build_screen_output_path("proposal_detail", "P-001").as_posix() == "proposal_detail/P-001.html"
    assert build_screen_output_path("monthly_review", "2026-04").as_posix() == "monthly_review/2026-04.html"


def test_regeneration_groups_are_combined_as_publish_unit() -> None:
    assert resolve_affected_screens(
        (
            RecordUnitChange("proposal"),
            RecordUnitChange("order"),
        )
    ) == (
        "top",
        "proposal_list",
        "proposal_detail",
        "orders",
    )


def test_conditional_screens_follow_decision_memo_contract() -> None:
    assert resolve_affected_screens(
        (
            RecordUnitChange("proposal", {"market_context_changed": True}),
            RecordUnitChange("order", {"excluded_trade_state_changed": True}),
            RecordUnitChange("holding_snapshot", {"monthly_metrics_changed": True}),
            RecordUnitChange(
                "review",
                {
                    "monthly_review_changed": True,
                    "market_context_changed": True,
                    "top_summary_changed": True,
                },
            ),
            RecordUnitChange("us_pilot", {"top_summary_changed": True}),
        )
    ) == (
        "top",
        "proposal_list",
        "proposal_detail",
        "market_overview",
        "orders",
        "excluded_trades",
        "holdings",
        "performance",
        "monthly_review",
        "reviews",
        "us_pilot_performance",
    )
