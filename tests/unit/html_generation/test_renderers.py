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


def test_renderer_supports_all_required_stable_key_anchor_prefixes() -> None:
    metadata = GenerationMetadata("gen-003")
    render_input = RenderInput(
        screen_id="orders",
        title="注文・約定履歴",
        relative_output_path=build_screen_output_path("orders"),
        page_data={
            "sections": [
                {
                    "id": "orders",
                    "title": "注文一覧",
                    "records": [
                        {"title": "注文", "anchor_kind": "order", "anchor_key": "O-001", "text": "order"},
                        {
                            "title": "ポジションサイクル",
                            "anchor_kind": "position_cycle",
                            "anchor_key": "PC-001",
                            "text": "cycle",
                        },
                        {"title": "振り返り", "anchor_kind": "review", "anchor_key": "R-001", "text": "review"},
                        {"title": "スナップショット", "anchor_kind": "snapshot", "anchor_key": "S-001", "text": "snapshot"},
                        {"title": "米国仮想", "anchor_kind": "us_virtual", "anchor_key": "UV-001", "text": "us virtual"},
                        {"title": "米国パイロット", "anchor_kind": "us_pilot", "anchor_key": "UP-001", "text": "us pilot"},
                    ],
                }
            ]
        },
        shared_data={},
        metadata=metadata,
    )

    html = render_many([render_input])[0].html
    assert 'id="order-O-001"' in html
    assert 'id="position-cycle-PC-001"' in html
    assert 'id="review-R-001"' in html
    assert 'id="snapshot-S-001"' in html
    assert 'id="us-virtual-UV-001"' in html
    assert 'id="us-pilot-UP-001"' in html
