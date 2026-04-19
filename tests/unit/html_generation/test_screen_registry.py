from __future__ import annotations

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
    assert resolve_affected_screens(("proposal", "order")) == (
        "top",
        "proposal_list",
        "proposal_detail",
        "orders",
        "excluded_trades",
    )
