"""Filesystem path helpers for HTML generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HtmlOutputPaths:
    """Resolved filesystem locations for staging and publish targets."""

    project_root: Path

    @property
    def generated_html_root(self) -> Path:
        return self.project_root / "generated_html"

    @property
    def generations_root(self) -> Path:
        return self.generated_html_root / "generations"

    @property
    def latest_root(self) -> Path:
        return self.generated_html_root / "latest"

    @property
    def archive_monthly_root(self) -> Path:
        return self.project_root / "archive" / "monthly"

    def generation_root(self, generation_id: str) -> Path:
        return self.generations_root / generation_id

    def generation_public_root(self, generation_id: str) -> Path:
        return self.generation_root(generation_id) / "public"


def discover_project_root() -> Path:
    """Return the repository root from the package location."""

    return Path(__file__).resolve().parents[3]
