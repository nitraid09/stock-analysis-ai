"""Operational logging for night update formalization."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from stock_analysis_ai.master_storage.contracts import ensure_aware_datetime, utc_now


@dataclass(frozen=True)
class OperationLogEntry:
    """Minimal operation log payload required by the night-update flow."""

    generation_id: str
    master_update_status: str
    reconciliation_status_summary: Mapping[str, int]
    generation_status: str
    publish_status: str
    archive_status: str
    restore_status: str
    failure_reason: str | None = None
    occurred_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "occurred_at", ensure_aware_datetime(self.occurred_at))

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation_id": self.generation_id,
            "occurred_at": self.occurred_at.isoformat(),
            "master_update_status": self.master_update_status,
            "reconciliation_status_summary": dict(self.reconciliation_status_summary),
            "generation_status": self.generation_status,
            "publish_status": self.publish_status,
            "archive_status": self.archive_status,
            "restore_status": self.restore_status,
            "failure_reason": self.failure_reason,
        }


class OperationLogRepository:
    """Append-only JSONL operation log."""

    def __init__(self, project_root: Path) -> None:
        self.log_path = Path(project_root) / "logs" / "night_update_operations.jsonl"

    def append(self, entry: OperationLogEntry) -> Path:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        return self.log_path
