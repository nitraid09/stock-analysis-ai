from __future__ import annotations

from stock_analysis_ai.html_generation.state_labels import get_state_label, list_state_labels


def test_state_labels_do_not_collapse_to_same_display() -> None:
    labels = [state.label for state in list_state_labels()]
    assert len(labels) == len(set(labels))


def test_japanese_aliases_map_to_distinct_states() -> None:
    assert get_state_label("未記録").code == "unrecorded"
    assert get_state_label("評価対象外").code == "excluded"
    assert get_state_label("参照不能").code == "unavailable"
    assert get_state_label("再生成失敗").code == "regeneration_failed"


def test_empty_none_and_not_applicable_have_distinct_display_labels() -> None:
    assert get_state_label("empty").label == "抽出結果なし"
    assert get_state_label("none").label == "対象なし"
    assert get_state_label("not_applicable").label == "適用対象外"
