from __future__ import annotations

from stock_analysis_ai.master_storage.change_set import resolve_change_set
from stock_analysis_ai.night_update.generation_bridge import (
    GenerationBridgeInput,
    invoke_generation_bridge,
)


def test_bridge_passes_minimum_contract_into_html_publish_pipeline(monkeypatch, tmp_path) -> None:
    captured = {}

    def fake_execute_publish(request, output_root=None):
        captured["request"] = request
        captured["output_root"] = output_root

        class Result:
            status = "success"
            published = True
            archived = False
            errors = ()

        return Result()

    monkeypatch.setattr(
        "stock_analysis_ai.night_update.generation_bridge.execute_publish",
        fake_execute_publish,
    )

    change_set = resolve_change_set(
        generation_id="gen-bridge",
        publish_mode="publish",
        table_changes={
            "proposal_header": [{"proposal_id": "proposal-000001"}],
        },
        changed_evaluation_series=("ai_official",),
    )
    result = invoke_generation_bridge(
        GenerationBridgeInput(
            generation_id="gen-bridge",
            publish_mode="publish",
            change_set=change_set,
            payload={
                "screens": {
                    "top": {"sections": []},
                    "proposal_list": {"sections": []},
                    "proposal_detail": [{"proposal_id": "proposal-000001", "sections": []}],
                }
            },
            display_condition={"series": "ai_official"},
            evaluation_series=("ai_official",),
        ),
        output_root=tmp_path,
    )

    assert result.status == "success"
    assert captured["request"].generation_id == "gen-bridge"
    assert tuple(change.record_unit for change in captured["request"].change_set) == ("proposal",)
    assert captured["request"].publish_mode == "publish"
    assert captured["request"].display_condition == {"series": "ai_official"}
    assert captured["request"].evaluation_series == ("ai_official",)
    assert "night_update_bridge" not in captured["request"].payload.get("shared", {})
