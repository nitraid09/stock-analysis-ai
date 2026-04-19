"""Publish orchestration for staged generations, latest, and monthly archive."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from .contracts import PublishRequest, PublishResult, RenderedPage
from .exceptions import PublishError
from .paths import HtmlOutputPaths, discover_project_root
from .payload_builder import build_render_inputs
from .renderers import render_many
from .screen_registry import get_screen_definition, resolve_affected_screens


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


def _write_status(
    generation_root: Path,
    *,
    status: str,
    accepted: bool,
    published: bool,
    archived: bool,
    errors: list[str],
    rendered_files: tuple[str, ...],
) -> None:
    _write_json(
        generation_root / "status.json",
        {
            "status": status,
            "accepted": accepted,
            "published": published,
            "archived": archived,
            "errors": errors,
            "rendered_files": list(rendered_files),
        },
    )


def _build_result(
    request: PublishRequest,
    generation_root: Path,
    latest_root: Path,
    *,
    status: str,
    accepted: bool,
    published: bool,
    archived: bool,
    errors: list[str],
    rendered_files: tuple[str, ...],
) -> PublishResult:
    _write_status(
        generation_root,
        status=status,
        accepted=accepted,
        published=published,
        archived=archived,
        errors=errors,
        rendered_files=rendered_files,
    )
    return PublishResult(
        generation_id=request.generation_id,
        status=status,
        accepted=accepted,
        published=published,
        archived=archived,
        rendered_files=rendered_files,
        generation_root=str(generation_root),
        latest_root=str(latest_root),
        errors=tuple(errors),
    )


def _replace_directory_contents(target: Path, source: Path) -> None:
    source = source.resolve()
    _ensure_within(source.parent, source)
    target.parent.mkdir(parents=True, exist_ok=True)
    swap_token = uuid4().hex
    staging_target = target.parent / f".{target.name}.incoming-{swap_token}"
    backup_target = target.parent / f".{target.name}.backup-{swap_token}"

    try:
        shutil.copytree(source, staging_target)
        if target.exists():
            target.replace(backup_target)
        try:
            staging_target.replace(target)
        except Exception as exc:
            if backup_target.exists() and not target.exists():
                backup_target.replace(target)
            raise PublishError(f"Failed to promote latest publish: {exc}") from exc
        if backup_target.exists():
            shutil.rmtree(backup_target, ignore_errors=True)
    finally:
        if staging_target.exists():
            shutil.rmtree(staging_target, ignore_errors=True)


def _prepare_latest_publish_tree(
    latest_root: Path,
    public_root: Path,
    affected_screens: tuple[str, ...],
    staging_root: Path,
) -> None:
    if staging_root.exists():
        shutil.rmtree(staging_root, ignore_errors=True)
    if latest_root.exists():
        shutil.copytree(latest_root, staging_root)
    else:
        staging_root.mkdir(parents=True, exist_ok=True)

    route_prefixes = tuple(dict.fromkeys(get_screen_definition(screen_id).route_prefix for screen_id in affected_screens))
    for route_prefix in route_prefixes:
        target_root = staging_root / route_prefix
        if target_root.exists():
            shutil.rmtree(target_root, ignore_errors=True)

    for route_prefix in route_prefixes:
        source_root = public_root / route_prefix
        if not source_root.exists():
            raise PublishError(f"Missing rendered subtree for affected screen root: {route_prefix}")
        shutil.copytree(source_root, staging_root / route_prefix)


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
        "display_condition": dict(request.display_condition or {}),
        "evaluation_series": list(request.evaluation_series),
        "affected_screens": list(affected_screens),
        "archive_month": request.archive_month,
    }
    _write_json(generation_root / "manifest.json", manifest)

    try:
        render_inputs = build_render_inputs(request.payload, request.metadata, affected_screens)
        rendered_pages = render_many(render_inputs)
        _write_rendered_pages(public_root, rendered_pages)
    except Exception as exc:
        return _build_result(
            request,
            generation_root,
            paths.latest_root,
            status="failed",
            accepted=False,
            published=False,
            archived=False,
            errors=[str(exc)],
            rendered_files=(),
        )

    accepted, acceptance_errors = _validate_acceptance(request, affected_screens, rendered_pages)
    rendered_files = tuple(page.relative_output_path.as_posix() for page in rendered_pages)
    published = False
    archived = False
    errors = list(acceptance_errors)

    if request.publish_mode != "publish" or not accepted:
        return _build_result(
            request,
            generation_root,
            paths.latest_root,
            status="staged",
            accepted=accepted,
            published=False,
            archived=False,
            errors=errors,
            rendered_files=rendered_files,
        )

    try:
        merged_latest_root = generation_root / ".latest-merged"
        try:
            paths.latest_root.parent.mkdir(parents=True, exist_ok=True)
            _prepare_latest_publish_tree(paths.latest_root, public_root, affected_screens, merged_latest_root)
            _replace_directory_contents(paths.latest_root, merged_latest_root)
            published = True
        finally:
            if merged_latest_root.exists():
                shutil.rmtree(merged_latest_root, ignore_errors=True)
    except Exception as exc:
        errors.append(str(exc))
        return _build_result(
            request,
            generation_root,
            paths.latest_root,
            status="failed",
            accepted=accepted,
            published=False,
            archived=False,
            errors=errors,
            rendered_files=rendered_files,
        )

    if request.archive_month:
        try:
            _archive_generation(paths, request.archive_month, public_root)
            archived = True
        except Exception as exc:
            errors.append(str(exc))
            return _build_result(
                request,
                generation_root,
                paths.latest_root,
                status="failed",
                accepted=accepted,
                published=True,
                archived=False,
                errors=errors,
                rendered_files=rendered_files,
            )

    return _build_result(
        request,
        generation_root,
        paths.latest_root,
        status="success",
        accepted=accepted,
        published=published,
        archived=archived,
        errors=errors,
        rendered_files=rendered_files,
    )
