"""Contracts shared by HTML generation modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Literal, Mapping, Sequence

from .exceptions import ContractError

PublishMode = Literal["publish", "stage_only"]
GenerationStatus = Literal["success", "failed", "staged"]


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
    change_set: Sequence[str]
    publish_mode: PublishMode = "publish"
    generated_at: datetime = field(default_factory=utc_now)
    acceptance_passed: bool = True
    archive_month: str | None = None
    additional_screens: Sequence[str] = ()
    display_condition: Mapping[str, Any] | None = None
    evaluation_series: Sequence[str] = ()

    def __post_init__(self) -> None:
        if not self.generation_id.strip():
            raise ContractError("generation_id must not be empty.")
        if self.publish_mode not in {"publish", "stage_only"}:
            raise ContractError(f"Unsupported publish mode: {self.publish_mode}")
        object.__setattr__(self, "generated_at", ensure_aware_datetime(self.generated_at))
        if self.archive_month is not None:
            parts = self.archive_month.split("-")
            if len(parts) != 2 or len(parts[0]) != 4 or len(parts[1]) != 2:
                raise ContractError("archive_month must use YYYY-MM format.")
        if self.display_condition is not None and not isinstance(self.display_condition, Mapping):
            raise ContractError("display_condition must be a mapping when provided.")

    @property
    def metadata(self) -> GenerationMetadata:
        return GenerationMetadata(self.generation_id, self.generated_at)


@dataclass(frozen=True)
class PublishResult:
    """Outcome of a staging and publish operation."""

    generation_id: str
    status: GenerationStatus
    accepted: bool
    published: bool
    archived: bool
    rendered_files: tuple[str, ...]
    generation_root: str
    latest_root: str
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation_id": self.generation_id,
            "status": self.status,
            "accepted": self.accepted,
            "published": self.published,
            "archived": self.archived,
            "rendered_files": list(self.rendered_files),
            "generation_root": self.generation_root,
            "latest_root": self.latest_root,
            "errors": list(self.errors),
        }
