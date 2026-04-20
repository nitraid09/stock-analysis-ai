"""Registry and record-unit-to-screen resolution for public HTML screens."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import PurePosixPath
from typing import Iterable
from urllib.parse import quote

from .contracts import RecordUnitChange, ScreenDefinition
from .exceptions import ContractError

DEFAULT_QUERY_KEYS = ("series", "scope", "status", "sort", "period", "snapshot", "reconciliation")

SCREEN_REGISTRY: "OrderedDict[str, ScreenDefinition]" = OrderedDict(
    (
        (
            "top",
            ScreenDefinition(
                screen_id="top",
                title="トップ画面",
                route_prefix="top",
                block_order=(
                    "summary",
                    "incidents",
                    "today_items",
                    "active_proposals",
                    "pending_orders",
                    "holding_alerts",
                    "pass_proposals",
                    "news",
                    "market_panel",
                ),
                default_query={"series": "ai_official", "scope": "all"},
                allowed_query_keys=("series", "scope"),
            ),
        ),
        (
            "market_overview",
            ScreenDefinition(
                screen_id="market_overview",
                title="市場概況詳細",
                route_prefix="market_overview",
                block_order=("japan_market", "us_market", "analysis", "notes", "links"),
                default_query={"scope": "all"},
                allowed_query_keys=("scope", "series"),
            ),
        ),
        (
            "proposal_list",
            ScreenDefinition(
                screen_id="proposal_list",
                title="提案一覧",
                route_prefix="proposal_list",
                block_order=("toolbar", "summary", "active", "inactive", "pass"),
                default_query={"series": "ai_official", "status": "all", "sort": "priority"},
                allowed_query_keys=("series", "status", "sort", "period", "scope"),
            ),
        ),
        (
            "proposal_detail",
            ScreenDefinition(
                screen_id="proposal_detail",
                title="提案詳細",
                route_prefix="proposal_detail",
                block_order=(
                    "summary",
                    "conditions",
                    "facts",
                    "analysis",
                    "assumptions",
                    "premises",
                    "invalidations",
                    "watchpoints",
                    "diff_reason",
                    "links",
                ),
                natural_key_name="proposal_id",
            ),
        ),
        (
            "orders",
            ScreenDefinition(
                screen_id="orders",
                title="注文・約定履歴",
                route_prefix="orders",
                block_order=("toolbar", "status_summary", "orders", "fills"),
                default_query={"series": "all", "reconciliation": "all", "sort": "updated_desc"},
                allowed_query_keys=("series", "status", "reconciliation", "sort", "period", "scope"),
            ),
        ),
        (
            "holdings",
            ScreenDefinition(
                screen_id="holdings",
                title="現在保有一覧",
                route_prefix="holdings",
                block_order=("snapshot_info", "positions", "protection", "account_summary"),
                default_query={"series": "real", "snapshot": "latest"},
                allowed_query_keys=("series", "snapshot", "sort", "scope"),
            ),
        ),
        (
            "performance",
            ScreenDefinition(
                screen_id="performance",
                title="期間別成績",
                route_prefix="performance",
                block_order=("series_switch", "period_switch", "summary", "drawdown", "comparison", "excluded"),
                default_query={"series": "real", "period": "month"},
                allowed_query_keys=("series", "period", "scope", "sort"),
            ),
        ),
        (
            "monthly_review",
            ScreenDefinition(
                screen_id="monthly_review",
                title="月次レビュー",
                route_prefix="monthly_review",
                block_order=("summary", "trade_report", "success", "failure", "incidents", "focus", "market"),
                natural_key_name="month",
            ),
        ),
        (
            "reviews",
            ScreenDefinition(
                screen_id="reviews",
                title="振り返り一覧",
                route_prefix="reviews",
                block_order=("toolbar", "reviews", "links"),
                default_query={"series": "ai_official", "sort": "updated_desc"},
                allowed_query_keys=("series", "scope", "sort", "period"),
            ),
        ),
        (
            "us_watch",
            ScreenDefinition(
                screen_id="us_watch",
                title="米国株ウォッチリスト",
                route_prefix="us_watch",
                block_order=("summary", "watchlist", "night_risk"),
                default_query={"scope": "active"},
                allowed_query_keys=("scope", "sort", "status"),
            ),
        ),
        (
            "us_virtual_performance",
            ScreenDefinition(
                screen_id="us_virtual_performance",
                title="米国株仮想売買成績",
                route_prefix="us_virtual_performance",
                block_order=("summary", "trades", "comparison"),
                default_query={"period": "month"},
                allowed_query_keys=("period", "scope", "sort"),
            ),
        ),
        (
            "us_pilot_performance",
            ScreenDefinition(
                screen_id="us_pilot_performance",
                title="米国株実売買パイロット成績",
                route_prefix="us_pilot_performance",
                block_order=("pilot_status", "incidents", "summary", "links"),
                default_query={"period": "month"},
                allowed_query_keys=("period", "scope", "sort"),
            ),
        ),
        (
            "excluded_trades",
            ScreenDefinition(
                screen_id="excluded_trades",
                title="評価対象外売買一覧",
                route_prefix="excluded_trades",
                block_order=("summary", "trades", "reason_summary"),
                default_query={"sort": "updated_desc"},
                allowed_query_keys=("sort", "period", "scope"),
            ),
        ),
    )
)

MANDATORY_SCREEN_GROUPS: dict[str, tuple[str, ...]] = {
    "proposal": ("top", "proposal_list", "proposal_detail"),
    "order": ("top", "orders"),
    "holding_snapshot": ("top", "holdings", "performance"),
    "review": ("reviews",),
    "us_virtual": ("us_watch", "us_virtual_performance"),
    "us_pilot": ("us_pilot_performance",),
}

CONDITIONAL_SCREEN_GROUPS: dict[str, dict[str, tuple[str, ...]]] = {
    "proposal": {
        "market_context_changed": ("market_overview",),
    },
    "order": {
        "excluded_trade_state_changed": ("excluded_trades",),
    },
    "holding_snapshot": {
        "monthly_metrics_changed": ("monthly_review",),
    },
    "review": {
        "monthly_review_changed": ("monthly_review",),
        "market_context_changed": ("market_overview",),
        "top_summary_changed": ("top",),
    },
    "us_pilot": {
        "top_summary_changed": ("top",),
    },
}


def get_screen_definition(screen_id: str) -> ScreenDefinition:
    try:
        return SCREEN_REGISTRY[screen_id]
    except KeyError as exc:
        raise ContractError(f"Unknown screen_id: {screen_id}") from exc


def list_screen_ids() -> tuple[str, ...]:
    return tuple(SCREEN_REGISTRY.keys())


def build_screen_output_path(screen_id: str, natural_key: str | None = None) -> PurePosixPath:
    definition = get_screen_definition(screen_id)
    if definition.is_multi_file:
        if not natural_key:
            raise ContractError(f"{screen_id} requires {definition.natural_key_name}.")
        safe_key = quote(natural_key, safe="-_.~")
        return PurePosixPath(definition.route_prefix) / f"{safe_key}.html"
    if natural_key is not None:
        raise ContractError(f"{screen_id} does not accept a natural key.")
    return PurePosixPath(definition.route_prefix) / "index.html"


def _resolve_change_entry_screens(change: RecordUnitChange) -> tuple[str, ...]:
    if change.record_unit not in MANDATORY_SCREEN_GROUPS:
        raise ContractError(f"Unknown record unit: {change.record_unit}")
    ordered: OrderedDict[str, None] = OrderedDict()
    for screen_id in MANDATORY_SCREEN_GROUPS[change.record_unit]:
        ordered[screen_id] = None
    conditional_map = CONDITIONAL_SCREEN_GROUPS.get(change.record_unit, {})
    unknown_flags = [
        flag_name
        for flag_name, enabled in change.conditional_flags.items()
        if enabled and flag_name not in conditional_map
    ]
    if unknown_flags:
        raise ContractError(
            f"Unsupported conditional flags for {change.record_unit}: {', '.join(unknown_flags)}"
        )
    for flag_name, enabled in change.conditional_flags.items():
        if not enabled:
            continue
        for screen_id in conditional_map.get(flag_name, ()):
            ordered[screen_id] = None
    return tuple(ordered.keys())


def resolve_affected_screens(
    change_set: Iterable[RecordUnitChange],
    additional_screen_ids: Iterable[str] = (),
) -> tuple[str, ...]:
    ordered: OrderedDict[str, None] = OrderedDict()
    for change in change_set:
        for screen_id in _resolve_change_entry_screens(change):
            ordered[screen_id] = None
    for screen_id in additional_screen_ids:
        get_screen_definition(screen_id)
        ordered[screen_id] = None
    return tuple(ordered.keys())
