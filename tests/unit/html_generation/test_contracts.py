from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath

import pytest

from stock_analysis_ai.html_generation.contracts import (
    GenerationMetadata,
    PublishRequest,
    RecordUnitChange,
    RenderInput,
)
from stock_analysis_ai.html_generation.exceptions import ContractError


def test_render_input_requires_relative_html_path() -> None:
    metadata = GenerationMetadata("gen-001")
    with pytest.raises(ContractError):
        RenderInput(
            screen_id="top",
            title="トップ画面",
            relative_output_path=PurePosixPath("/absolute/index.html"),
            page_data={},
            shared_data={},
            metadata=metadata,
        )


def test_generation_metadata_normalizes_naive_datetime() -> None:
    metadata = GenerationMetadata("gen-001", datetime(2026, 4, 19, 0, 0, 0))
    assert metadata.generated_at.tzinfo is not None


def test_publish_request_validates_archive_month() -> None:
    with pytest.raises(ContractError):
        PublishRequest(
            generation_id="gen-001",
            payload={},
            change_set=("proposal",),
            archive_target_period="202604",
            default_display_context={"series": "ai_official"},
        )


def test_publish_request_requires_display_context_or_evaluation_series() -> None:
    with pytest.raises(ContractError):
        PublishRequest(generation_id="gen-001", payload={}, change_set=("proposal",))


def test_publish_request_normalizes_structured_change_set() -> None:
    request = PublishRequest(
        generation_id="gen-001",
        payload={},
        change_set=(
            {
                "record_unit": "review",
                "conditional_flags": {
                    "monthly_review_changed": True,
                    "market_context_changed": False,
                },
                "parent_keys": ["R-001"],
            },
        ),
        default_display_context={"series": "ai_official"},
    )

    assert request.change_set == (
        RecordUnitChange(
            record_unit="review",
            conditional_flags={
                "monthly_review_changed": True,
                "market_context_changed": False,
            },
            parent_keys=("R-001",),
        ),
    )
