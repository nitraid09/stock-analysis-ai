from __future__ import annotations

from stock_analysis_ai.html_generation.contracts import GenerationMetadata, RenderInput
from stock_analysis_ai.html_generation.renderers import render_many
from stock_analysis_ai.html_generation.screen_registry import build_screen_output_path


def test_renderer_embeds_generation_metadata_and_anchor() -> None:
    metadata = GenerationMetadata("gen-001")
    render_input = RenderInput(
        screen_id="proposal_detail",
        title="提案詳細",
        relative_output_path=build_screen_output_path("proposal_detail", "P-001"),
        page_data={
            "sections": [
                {
                    "id": "summary",
                    "title": "提案サマリ",
                    "records": [
                        {
                            "title": "提案ID P-001",
                            "anchor_kind": "proposal",
                            "anchor_key": "P-001",
                            "fields": [{"label": "提案状態", "value": "見送り", "state": "unrecorded"}],
                        }
                    ],
                }
            ]
        },
        shared_data={"anchor_index": [{"id": "proposal-P-001", "label": "P-001"}]},
        metadata=metadata,
        natural_key="P-001",
    )

    html = render_many([render_input])[0].html
    assert "generation_id: gen-001" in html
    assert "generated_at:" in html
    assert 'id="proposal-P-001"' in html
    assert "未記録" in html


def test_renderer_keeps_non_active_and_zero_new_entry_records_visible() -> None:
    metadata = GenerationMetadata("gen-002")
    render_input = RenderInput(
        screen_id="proposal_list",
        title="提案一覧",
        relative_output_path=build_screen_output_path("proposal_list"),
        page_data={
            "sections": [
                {"id": "inactive", "title": "非アクティブ提案", "items": ["候補外", "無効化対象"]},
                {"id": "pass", "title": "見送り提案", "items": ["見送り提案", "新規建てゼロ提案"]},
            ]
        },
        shared_data={},
        metadata=metadata,
    )

    html = render_many([render_input])[0].html
    assert "候補外" in html
    assert "無効化対象" in html
    assert "見送り提案" in html
    assert "新規建てゼロ提案" in html
