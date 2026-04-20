"""HTML regeneration foundation for the stock analysis AI project."""

from .contracts import (
    GenerationMetadata,
    GenerationStatusRecord,
    OperationLogRecord,
    PublishRequest,
    PublishResult,
    RecordUnitChange,
    RenderInput,
    RenderedPage,
)

__all__ = [
    "GenerationMetadata",
    "GenerationStatusRecord",
    "OperationLogRecord",
    "PublishRequest",
    "PublishResult",
    "RecordUnitChange",
    "RenderInput",
    "RenderedPage",
]
