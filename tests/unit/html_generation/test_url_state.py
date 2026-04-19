from __future__ import annotations

from stock_analysis_ai.html_generation.url_state import build_screen_url, normalize_query_state


def test_missing_query_uses_defaults() -> None:
    assert normalize_query_state("proposal_list", None) == {
        "series": "ai_official",
        "status": "all",
        "sort": "priority",
    }


def test_unknown_query_is_ignored() -> None:
    assert normalize_query_state("orders", {"status": "filled", "accordion": "open"}) == {
        "series": "all",
        "reconciliation": "all",
        "sort": "updated_desc",
        "status": "filled",
    }


def test_url_keeps_path_query_hash_separate() -> None:
    url = build_screen_url(
        "proposal_list",
        query={"series": "real", "status": "active", "scroll": "200"},
        anchor="proposal-P-001",
    )
    assert url == "proposal_list/index.html?series=real&status=active&sort=priority#proposal-P-001"
