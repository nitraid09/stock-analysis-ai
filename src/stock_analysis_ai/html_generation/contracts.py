"""Contracts shared by HTML generation modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Literal, Mapping, Sequence

from .exceptions import ContractError

PublishMode = Literal["publish", "stage_only"]
GenerationStatus = Literal[
    "published",
    "published_with_archive_failure",
    "publish_failed",
    "render_failed",
    "staged",
]
StageResult = Literal["succeeded", "failed"]
StepResult = Literal["succeeded", "failed", "skipped"]
LatestAction = Literal["unchanged", "published", "preserved", "restored"]

RECORD_UNITS: tuple[str, ...] = (
    "proposal",
    "order",
    "holding_snapshot",
    "review",
    "us_virtual",
    "us_pilot",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware_datetime(value: datetime | str | None) -> datetime:
    if value is None:
        return utc_now()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def ensure_archive_target_period(value: str | None) -> str | None:
    if value is None:
        return None
    parts = value.split("-")
    if len(parts) != 2 or len(parts[0]) != 4 or len(parts[1]) != 2:
        raise ContractError("archive_target_period must use YYYY-MM format.")
    return value


@dataclass(frozen=True)
class ScreenDefinition:
    """Registry definition for a public HTML screen."""

    screen_id: str
    title: str
    route_prefix: str
    block_order: tuple[str, ...]
    default_query: Mapping[str, str] = field(default_factory=dict)
    allowed_query_keys: tuple[str, ...] = ()
    natural_key_name: str | None = None

    @property
    def is_multi_file(self) -> bool:
        return self.natural_key_name is not None


@dataclass(frozen=True)
class RecordUnitChange:
    """Final record-unit change passed from post-update orchestration."""

    record_unit: str
    conditional_flags: Mapping[str, bool] = field(default_factory=dict)
    parent_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.record_unit not in RECORD_UNITS:
            raise ContractError(f"Unsupported record unit: {self.record_unit}")
        if not isinstance(self.conditional_flags, Mapping):
            raise ContractError("conditional_flags must be a mapping.")
        normalized_flags = {
            str(key): bool(value)
            for key, value in self.conditional_flags.items()
        }
        object.__setattr__(self, "conditional_flags", normalized_flags)
        normalized_parent_keys = tuple(
            key for key in (str(value).strip() for value in self.parent_keys) if key
        )
        object.__setattr__(self, "parent_keys", normalized_parent_keys)

    @classmethod
    def from_raw(cls, raw_change: str | Mapping[str, Any]) -> "RecordUnitChange":
        if isinstance(raw_change, str):
            return cls(record_unit=raw_change)
        if not isinstance(raw_change, Mapping):
            raise ContractError("change_set entries must be strings or mappings.")
        record_unit = raw_change.get("record_unit") or raw_change.get("unit")
        if not isinstance(record_unit, str) or not record_unit.strip():
            raise ContractError("record-unit change entries require record_unit.")
        raw_flags = raw_change.get("conditional_flags", raw_change.get("flags", {}))
        if raw_flags is None:
            raw_flags = {}
        if not isinstance(raw_flags, Mapping):
            raise ContractError("record-unit change flags must be a mapping.")
        raw_parent_keys = raw_change.get("parent_keys", ())
        if raw_parent_keys is None:
            raw_parent_keys = ()
        if not isinstance(raw_parent_keys, Sequence) or isinstance(raw_parent_keys, (str, bytes)):
            raise ContractError("parent_keys must be a sequence when provided.")
        return cls(
            record_unit=record_unit,
            conditional_flags=raw_flags,
            parent_keys=tuple(str(value) for value in raw_parent_keys),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_unit": self.record_unit,
            "conditional_flags": dict(self.conditional_flags),
            "parent_keys": list(self.parent_keys),
        }


def normalize_change_set(change_set: Sequence[str | Mapping[str, Any]]) -> tuple[RecordUnitChange, ...]:
    if not change_set:
        raise ContractError("change_set must not be empty.")
    return tuple(RecordUnitChange.from_raw(raw_change) for raw_change in change_set)


@dataclass(frozen=True)
class GenerationMetadata:
    """Metadata embedded into generated pages and manifests."""

    generation_id: str
    generated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.generation_id.strip():
            raise ContractError("generation_id must not be empty.")
        object.__setattr__(self, "generated_at", ensure_aware_datetime(self.generated_at))

    def iso_generated_at(self) -> str:
        return self.generated_at.isoformat()


@dataclass(frozen=True)
class RenderInput:
    """Structured display payload passed into the render layer."""

    screen_id: str
    title: str
    relative_output_path: PurePosixPath
    page_data: Mapping[str, Any]
    shared_data: Mapping[str, Any]
    metadata: GenerationMetadata
    natural_key: str | None = None

    def __post_init__(self) -> None:
        if self.relative_output_path.is_absolute():
            raise ContractError("relative_output_path must be relative.")
        if ".." in self.relative_output_path.parts:
            raise ContractError("relative_output_path must not contain parent traversal.")
        if self.relative_output_path.suffix != ".html":
            raise ContractError("relative_output_path must target an .html file.")
        if self.natural_key is not None and not self.natural_key.strip():
            raise ContractError("natural_key must not be blank when provided.")


@dataclass(frozen=True)
class RenderedPage:
    """HTML produced by the render layer."""

    screen_id: str
    title: str
    relative_output_path: PurePosixPath
    html: str
    natural_key: str | None = None

    def __post_init__(self) -> None:
        if not self.html.strip():
            raise ContractError("Rendered HTML must not be empty.")
        if self.relative_output_path.suffix != ".html":
            raise ContractError("Rendered output must end with .html.")


@dataclass(frozen=True)
class PublishRequest:
    """Input contract for staging and publish orchestration."""

    generation_id: str
    payload: Mapping[str, Any]
    change_set: Sequence[str | Mapping[str, Any]]
    publish_mode: PublishMode = "publish"
    generated_at: datetime = field(default_factory=utc_now)
    acceptance_passed: bool = True
    archive_target_period: str | None = None
    archive_month: str | None = None
    additional_screens: Sequence[str] = ()
    default_display_context: Mapping[str, Any] | None = None
    display_condition: Mapping[str, Any] | None = None
    evaluation_series: Sequence[str] = ()

    def __post_init__(self) -> None:
        if not self.generation_id.strip():
            raise ContractError("generation_id must not be empty.")
        if self.publish_mode not in {"publish", "stage_only"}:
            raise ContractError(f"Unsupported publish mode: {self.publish_mode}")
        object.__setattr__(self, "generated_at", ensure_aware_datetime(self.generated_at))
        archive_target_period = self.archive_target_period or self.archive_month
        object.__setattr__(
            self,
            "archive_target_period",
            ensure_archive_target_period(archive_target_period),
        )
        object.__setattr__(self, "archive_month", self.archive_target_period)
        normalized_context = self.default_display_context
        if normalized_context is None:
            normalized_context = self.display_condition
        if normalized_context is not None and not isinstance(normalized_context, Mapping):
            raise ContractError("default_display_context must be a mapping when provided.")
        object.__setattr__(self, "default_display_context", normalized_context)
        object.__setattr__(self, "display_condition", normalized_context)
        if not self.default_display_context and not self.evaluation_series:
            raise ContractError(
                "Either default_display_context or evaluation_series must be supplied."
            )
        object.__setattr__(self, "change_set", normalize_change_set(self.change_set))

    @property
    def metadata(self) -> GenerationMetadata:
        return GenerationMetadata(self.generation_id, self.generated_at)


@dataclass(frozen=True)
class GenerationStatusRecord:
    """Structured generation status kept separately from operation logs."""

    generation_id: str
    accepted: bool
    staging_result: StageResult
    publish_result: StepResult
    archive_result: StepResult
    latest_action: LatestAction
    affected_screens: tuple[str, ...]
    rendered_files: tuple[str, ...]
    render_failures: tuple[str, ...] = ()
    publish_failures: tuple[str, ...] = ()
    archive_failures: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation_id": self.generation_id,
            "accepted": self.accepted,
            "staging_result": self.staging_result,
            "publish_result": self.publish_result,
            "archive_result": self.archive_result,
            "latest_action": self.latest_action,
            "affected_screens": list(self.affected_screens),
            "rendered_files": list(self.rendered_files),
            "render_failures": list(self.render_failures),
            "publish_failures": list(self.publish_failures),
            "archive_failures": list(self.archive_failures),
        }


@dataclass(frozen=True)
class OperationLogRecord:
    """Operational audit log kept separately from generation status."""

    generation_id: str
    step: str
    outcome: str
    failure_type: str | None
    target: str
    latest_affected: bool
    latest_action: LatestAction
    archive_only_failure: bool
    retry_required: bool
    message: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "created_at", ensure_aware_datetime(self.created_at))

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation_id": self.generation_id,
            "step": self.step,
            "outcome": self.outcome,
            "failure_type": self.failure_type,
            "target": self.target,
            "latest_affected": self.latest_affected,
            "latest_action": self.latest_action,
            "archive_only_failure": self.archive_only_failure,
            "retry_required": self.retry_required,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class PublishResult:
    """Outcome of a staging and publish operation."""

    generation_id: str
    status: GenerationStatus
    accepted: bool
    published: bool
    archived: bool
    staging_result: StageResult
    publish_result: StepResult
    archive_result: StepResult
    latest_action: LatestAction
    rendered_files: tuple[str, ...]
    generation_root: str
    latest_root: str
    status_path: str
    operation_log_path: str
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation_id": self.generation_id,
            "status": self.status,
            "accepted": self.accepted,
            "published": self.published,
            "archived": self.archived,
            "staging_result": self.staging_result,
            "publish_result": self.publish_result,
            "archive_result": self.archive_result,
            "latest_action": self.latest_action,
            "rendered_files": list(self.rendered_files),
            "generation_root": self.generation_root,
            "latest_root": self.latest_root,
            "status_path": self.status_path,
            "operation_log_path": self.operation_log_path,
            "errors": list(self.errors),
        }
