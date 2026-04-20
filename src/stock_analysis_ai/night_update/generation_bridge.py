"""Bridge from orchestration into the existing HTML publish contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from stock_analysis_ai.html_generation.contracts import PublishMode, PublishRequest, PublishResult
from stock_analysis_ai.html_generation.exceptions import ContractError
from stock_analysis_ai.html_generation.publish_pipeline import execute_publish

from stock_analysis_ai.master_storage.change_set import ChangeSet


@dataclass(frozen=True)
class GenerationBridgeInput:
    """Minimal upstream bridge contract for the HTML generation pipeline."""

    generation_id: str
    publish_mode: PublishMode
    change_set: ChangeSet
    payload: Mapping[str, Any]
    display_condition: Mapping[str, Any] | None = None
    evaluation_series: Sequence[str] = ()
    acceptance_passed: bool = True
    archive_month: str | None = None

    def __post_init__(self) -> None:
        if not self.generation_id.strip():
            raise ContractError("generation_id must not be empty.")
        if self.change_set.generation_id != self.generation_id:
            raise ContractError("change_set.generation_id must match bridge generation_id.")
        if self.display_condition is None and not self.evaluation_series:
            raise ContractError(
                "Either display_condition or evaluation_series must be supplied to the bridge."
            )


def invoke_generation_bridge(
    bridge_input: GenerationBridgeInput,
    *,
    output_root: Path | None = None,
) -> PublishResult:
    request = PublishRequest(
        generation_id=bridge_input.generation_id,
        payload=dict(bridge_input.payload),
        change_set=bridge_input.change_set.to_html_change_tokens(),
        publish_mode=bridge_input.publish_mode,
        acceptance_passed=bridge_input.acceptance_passed,
        archive_target_period=bridge_input.archive_month,
        default_display_context=bridge_input.display_condition,
        evaluation_series=bridge_input.evaluation_series,
    )
    return execute_publish(request, output_root=output_root)
