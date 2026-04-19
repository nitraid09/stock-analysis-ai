"""Display labels for empty and error-like states."""

from __future__ import annotations

from dataclasses import dataclass

from .exceptions import ContractError


@dataclass(frozen=True)
class StateLabel:
    code: str
    label: str
    meaning: str


_ALIASES = {
    "empty": "empty",
    "none": "none",
    "not_applicable": "not_applicable",
    "unrecorded": "unrecorded",
    "未記録": "unrecorded",
    "excluded": "excluded",
    "評価対象外": "excluded",
    "unavailable": "unavailable",
    "参照不能": "unavailable",
    "regeneration_failed": "regeneration_failed",
    "再生成失敗": "regeneration_failed",
    "error": "error",
    "error_state": "error",
    "エラー状態": "error",
}

_STATE_LABELS = {
    "empty": StateLabel("empty", "empty", "当該条件で抽出した結果が0件"),
    "none": StateLabel("none", "none", "現在その対象自体が存在しない"),
    "not_applicable": StateLabel("not_applicable", "not_applicable", "当該系列、列、画面には適用対象外"),
    "unrecorded": StateLabel("unrecorded", "未記録", "本来記録対象となり得るが、まだ正式記録が存在しない"),
    "excluded": StateLabel("excluded", "評価対象外", "記録済みだが評価系列集計へ算入しない"),
    "unavailable": StateLabel("unavailable", "参照不能", "関連リンクまたは証跡参照が現在辿れない"),
    "regeneration_failed": StateLabel("regeneration_failed", "再生成失敗", "正本更新後の最新反映が未完了"),
    "error": StateLabel("error", "エラー状態", "入力契約不整合等により画面生成要件を満たしていない"),
}


def normalize_state_code(raw_code: str) -> str:
    try:
        return _ALIASES[raw_code]
    except KeyError as exc:
        raise ContractError(f"Unknown state code: {raw_code}") from exc


def get_state_label(raw_code: str) -> StateLabel:
    return _STATE_LABELS[normalize_state_code(raw_code)]


def list_state_labels() -> tuple[StateLabel, ...]:
    return tuple(_STATE_LABELS.values())
