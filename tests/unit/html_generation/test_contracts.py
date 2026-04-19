from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath

import pytest

from stock_analysis_ai.html_generation.contracts import GenerationMetadata, PublishRequest, RenderInput
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
        PublishRequest(generation_id="gen-001", payload={}, change_set=("proposal",), archive_month="202604")
