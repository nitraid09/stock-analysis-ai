"""Publish orchestration for staged generations, latest, and monthly archive."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Iterable

from .contracts import PublishRequest, PublishResult, RenderedPage
from .exceptions import ContractError, PublishError
from .paths import HtmlOutputPaths, discover_project_root
from .payload_builder import build_render_inputs
from .renderers import render_many
from .screen_registry import resolve_affected_screens


def _ensure_within(base: Path, target: Path) -> None:
    base_resolved = base.resolve()
    target_resolved = target.resolve()
    if target_resolved != base_resolved and base_resolved not in target_resolved.parents:
        raise PublishError(f"Refusing to operate outside base directory: {target_resolved}")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_rendered_pages(public_root: Path, pages: Iterable[RenderedPage]) -> None:
    for page in pages:
        target = public_root / Path(*page.relative_output_path.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page.html, encoding="utf-8")


def _replace_directory_contents(target: Path, source: Path) -> None:
    source = source.resolve()
    _ensure_within(source.parent, source)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def _archive_generation(paths: HtmlOutputPaths, archive_month: str, source: Path) -> None:
    archive_target = paths.archive_monthly_root / archive_month
    if archive_target.exists():
        raise PublishError(f"Archive target already exists: {archive_target}")
    archive_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, archive_target)


def _validate_acceptance(request: PublishRequest, affected_screens: tuple[str, ...], rendered_pages: list[RenderedPage]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not request.acceptance_passed:
        errors.append("acceptance gate reported failure")
    rendered_screen_ids = {page.screen_id for page in rendered_pages}
    missing_screens = [screen_id for screen_id in affected_screens if screen_id not in rendered_screen_ids]
    if missing_screens:
        errors.append(f"missing rendered screens: {', '.join(missing_screens)}")
    relative_paths = [page.relative_output_path.as_posix() for page in rendered_pages]
    if len(relative_paths) != len(set(relative_paths)):
        errors.append("duplicate rendered output paths detected")
    return (len(errors) == 0, errors)


def execute_publish(request: PublishRequest, output_root: Path | None = None) -> PublishResult:
    project_root = output_root or discover_project_root()
    paths = HtmlOutputPaths(project_root=project_root)
    affected_screens = resolve_affected_screens(request.change_set, request.additional_screens)
    generation_root = paths.generation_root(request.generation_id)
    public_root = paths.generation_public_root(request.generation_id)
    generation_root.mkdir(parents=True, exist_ok=True)

    manifest = {
        "generation_id": request.generation_id,
        "generated_at": request.metadata.iso_generated_at(),
        "publish_mode": request.publish_mode,
        "change_set": list(request.change_set),
        "affected_screens": list(affected_screens),
        "archive_month": request.archive_month,
    }
    _write_json(generation_root / "manifest.json", manifest)

    try:
        render_inputs = build_render_inputs(request.payload, request.metadata, affected_screens)
        rendered_pages = render_many(render_inputs)
        _write_rendered_pages(public_root, rendered_pages)
    except Exception as exc:
        error_message = str(exc)
        _write_json(
            generation_root / "status.json",
            {"status": "failed", "errors": [error_message], "published": False, "archived": False},
        )
        return PublishResult(
            generation_id=request.generation_id,
            status="failed",
            accepted=False,
            published=False,
            archived=False,
            rendered_files=(),
            generation_root=str(generation_root),
            latest_root=str(paths.latest_root),
            errors=(error_message,),
        )

    accepted, acceptance_errors = _validate_acceptance(request, affected_screens, rendered_pages)
    published = False
    archived = False

    if request.publish_mode == "publish" and accepted:
        paths.latest_root.parent.mkdir(parents=True, exist_ok=True)
        _replace_directory_contents(paths.latest_root, public_root)
        published = True
        if request.archive_month:
            _archive_generation(paths, request.archive_month, public_root)
            archived = True

    status = "success" if published else "staged"
    _write_json(
        generation_root / "status.json",
        {
            "status": status,
            "accepted": accepted,
            "published": published,
            "archived": archived,
            "errors": acceptance_errors,
            "rendered_files": [page.relative_output_path.as_posix() for page in rendered_pages],
        },
    )
    return PublishResult(
        generation_id=request.generation_id,
        status=status,
        accepted=accepted,
        published=published,
        archived=archived,
        rendered_files=tuple(page.relative_output_path.as_posix() for page in rendered_pages),
        generation_root=str(generation_root),
        latest_root=str(paths.latest_root),
        errors=tuple(acceptance_errors),
    )
