"""Publish orchestration for staged generations, latest, and monthly archive."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from .contracts import (
    GenerationStatusRecord,
    LatestAction,
    OperationLogRecord,
    PublishRequest,
    PublishResult,
    RenderedPage,
)
from .exceptions import PublishError, PublishSwapError
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


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _write_rendered_pages(public_root: Path, pages: Iterable[RenderedPage]) -> None:
    for page in pages:
        target = public_root / Path(*page.relative_output_path.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page.html, encoding="utf-8")


def _write_status(path: Path, status_record: GenerationStatusRecord) -> None:
    _write_json(path, status_record.to_dict())


def _append_operation_log(path: Path, record: OperationLogRecord) -> None:
    _append_jsonl(path, record.to_dict())


def _build_result(
    request: PublishRequest,
    generation_root: Path,
    latest_root: Path,
    *,
    status: str,
    status_record: GenerationStatusRecord,
    operation_log_path: Path,
) -> PublishResult:
    errors = (
        list(status_record.render_failures)
        + list(status_record.publish_failures)
        + list(status_record.archive_failures)
    )
    return PublishResult(
        generation_id=request.generation_id,
        status=status,
        accepted=status_record.accepted,
        published=status_record.publish_result == "succeeded",
        archived=status_record.archive_result == "succeeded",
        staging_result=status_record.staging_result,
        publish_result=status_record.publish_result,
        archive_result=status_record.archive_result,
        latest_action=status_record.latest_action,
        rendered_files=status_record.rendered_files,
        generation_root=str(generation_root),
        latest_root=str(latest_root),
        status_path=str(generation_root / "status.json"),
        operation_log_path=str(operation_log_path),
        errors=tuple(errors),
    )


def _replace_directory_contents(target: Path, source: Path) -> None:
    source = source.resolve()
    _ensure_within(source.parent, source)
    target.parent.mkdir(parents=True, exist_ok=True)
    swap_token = uuid4().hex
    staging_target = target.parent / f".{target.name}.incoming-{swap_token}"
    backup_target = target.parent / f".{target.name}.backup-{swap_token}"
    latest_restored = False

    try:
        shutil.copytree(source, staging_target)
        if target.exists():
            target.replace(backup_target)
        try:
            staging_target.replace(target)
        except Exception as exc:
            if backup_target.exists() and not target.exists():
                backup_target.replace(target)
                latest_restored = True
            raise PublishSwapError(
                f"Failed to promote latest publish: {exc}",
                latest_restored=latest_restored,
            ) from exc
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

    route_prefixes = tuple(
        dict.fromkeys(get_screen_definition(screen_id).route_prefix for screen_id in affected_screens)
    )
    for route_prefix in route_prefixes:
        target_root = staging_root / route_prefix
        if target_root.exists():
            shutil.rmtree(target_root, ignore_errors=True)

    for route_prefix in route_prefixes:
        source_root = public_root / route_prefix
        if not source_root.exists():
            raise PublishError(f"Missing rendered subtree for affected screen root: {route_prefix}")
        shutil.copytree(source_root, staging_root / route_prefix)


def _archive_generation(paths: HtmlOutputPaths, archive_target_period: str, source: Path) -> None:
    archive_target = paths.archive_monthly_root / archive_target_period
    if archive_target.exists():
        raise PublishError(f"Archive target already exists: {archive_target}")
    archive_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, archive_target)


def _validate_acceptance(
    request: PublishRequest,
    affected_screens: tuple[str, ...],
    rendered_pages: list[RenderedPage],
) -> tuple[bool, list[str]]:
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


def _status_from_failed_publish(
    request: PublishRequest,
    generation_root: Path,
    latest_root: Path,
    operation_log_path: Path,
    *,
    accepted: bool,
    affected_screens: tuple[str, ...],
    rendered_files: tuple[str, ...],
    latest_action: LatestAction,
    errors: tuple[str, ...],
) -> PublishResult:
    status_record = GenerationStatusRecord(
        generation_id=request.generation_id,
        accepted=accepted,
        staging_result="succeeded",
        publish_result="failed",
        archive_result="skipped",
        latest_action=latest_action,
        affected_screens=affected_screens,
        rendered_files=rendered_files,
        publish_failures=errors,
    )
    _write_status(generation_root / "status.json", status_record)
    _append_operation_log(
        operation_log_path,
        OperationLogRecord(
            generation_id=request.generation_id,
            step="publish",
            outcome="failed",
            failure_type="latest_publish_failure",
            target="latest",
            latest_affected=False,
            latest_action=latest_action,
            archive_only_failure=False,
            retry_required=True,
            message=errors[-1],
        ),
    )
    return _build_result(
        request,
        generation_root,
        latest_root,
        status="publish_failed",
        status_record=status_record,
        operation_log_path=operation_log_path,
    )


def execute_publish(request: PublishRequest, output_root: Path | None = None) -> PublishResult:
    project_root = output_root or discover_project_root()
    paths = HtmlOutputPaths(project_root=project_root)
    affected_screens = resolve_affected_screens(request.change_set, request.additional_screens)
    generation_root = paths.generation_root(request.generation_id)
    public_root = paths.generation_public_root(request.generation_id)
    operation_log_path = paths.operation_log_path(request.generation_id)
    latest_exists_before = paths.latest_root.exists()

    if generation_root.exists():
        raise PublishError(f"Generation root already exists: {generation_root}")
    generation_root.mkdir(parents=True, exist_ok=False)

    manifest = {
        "generation_id": request.generation_id,
        "generated_at": request.metadata.iso_generated_at(),
        "publish_mode": request.publish_mode,
        "final_record_unit_change_set": [change.to_dict() for change in request.change_set],
        "default_display_context": dict(request.default_display_context or {}),
        "evaluation_series": list(request.evaluation_series),
        "affected_screens": list(affected_screens),
        "archive_target_period": request.archive_target_period,
    }
    _write_json(generation_root / "manifest.json", manifest)

    try:
        render_inputs = build_render_inputs(request.payload, request.metadata, affected_screens)
        rendered_pages = render_many(render_inputs)
        _write_rendered_pages(public_root, rendered_pages)
    except Exception as exc:
        latest_action: LatestAction = "preserved" if latest_exists_before else "unchanged"
        status_record = GenerationStatusRecord(
            generation_id=request.generation_id,
            accepted=False,
            staging_result="failed",
            publish_result="skipped",
            archive_result="skipped",
            latest_action=latest_action,
            affected_screens=affected_screens,
            rendered_files=(),
            render_failures=(str(exc),),
        )
        _write_status(generation_root / "status.json", status_record)
        _append_operation_log(
            operation_log_path,
            OperationLogRecord(
                generation_id=request.generation_id,
                step="staging",
                outcome="failed",
                failure_type="render_failure",
                target="render",
                latest_affected=False,
                latest_action=latest_action,
                archive_only_failure=False,
                retry_required=True,
                message=str(exc),
            ),
        )
        return _build_result(
            request,
            generation_root,
            paths.latest_root,
            status="render_failed",
            status_record=status_record,
            operation_log_path=operation_log_path,
        )

    accepted, acceptance_errors = _validate_acceptance(request, affected_screens, rendered_pages)
    rendered_files = tuple(page.relative_output_path.as_posix() for page in rendered_pages)
    initial_latest_action: LatestAction = "preserved" if latest_exists_before else "unchanged"
    staged_status = GenerationStatusRecord(
        generation_id=request.generation_id,
        accepted=accepted,
        staging_result="succeeded",
        publish_result="skipped",
        archive_result="skipped",
        latest_action=initial_latest_action,
        affected_screens=affected_screens,
        rendered_files=rendered_files,
        publish_failures=tuple(acceptance_errors),
    )
    _write_status(generation_root / "status.json", staged_status)
    _append_operation_log(
        operation_log_path,
        OperationLogRecord(
            generation_id=request.generation_id,
            step="staging",
            outcome="succeeded",
            failure_type=None,
            target=",".join(affected_screens),
            latest_affected=False,
            latest_action=initial_latest_action,
            archive_only_failure=False,
            retry_required=False,
            message="staging completed and latest is still unchanged",
        ),
    )

    if request.publish_mode != "publish" or not accepted:
        if request.publish_mode == "publish" and not accepted:
            _append_operation_log(
                operation_log_path,
                OperationLogRecord(
                    generation_id=request.generation_id,
                    step="publish",
                    outcome="skipped",
                    failure_type="publish_precondition_failed",
                    target="latest",
                    latest_affected=False,
                    latest_action=initial_latest_action,
                    archive_only_failure=False,
                    retry_required=True,
                    message="publish preconditions were not satisfied",
                ),
            )
        return _build_result(
            request,
            generation_root,
            paths.latest_root,
            status="staged",
            status_record=staged_status,
            operation_log_path=operation_log_path,
        )

    _append_operation_log(
        operation_log_path,
        OperationLogRecord(
            generation_id=request.generation_id,
            step="publish",
            outcome="started",
            failure_type=None,
            target="latest",
            latest_affected=True,
            latest_action="unchanged",
            archive_only_failure=False,
            retry_required=False,
            message="publish preconditions satisfied and latest merge is starting",
        ),
    )

    try:
        merged_latest_root = generation_root / ".latest-merged"
        try:
            paths.latest_root.parent.mkdir(parents=True, exist_ok=True)
            _prepare_latest_publish_tree(paths.latest_root, public_root, affected_screens, merged_latest_root)
            _replace_directory_contents(paths.latest_root, merged_latest_root)
        finally:
            if merged_latest_root.exists():
                shutil.rmtree(merged_latest_root, ignore_errors=True)
    except PublishSwapError as exc:
        latest_action = "restored" if exc.latest_restored else ("preserved" if latest_exists_before else "unchanged")
        return _status_from_failed_publish(
            request,
            generation_root,
            paths.latest_root,
            operation_log_path,
            accepted=accepted,
            affected_screens=affected_screens,
            rendered_files=rendered_files,
            latest_action=latest_action,
            errors=(str(exc),),
        )
    except Exception as exc:
        latest_action = "preserved" if latest_exists_before else "unchanged"
        return _status_from_failed_publish(
            request,
            generation_root,
            paths.latest_root,
            operation_log_path,
            accepted=accepted,
            affected_screens=affected_screens,
            rendered_files=rendered_files,
            latest_action=latest_action,
            errors=(str(exc),),
        )

    _append_operation_log(
        operation_log_path,
        OperationLogRecord(
            generation_id=request.generation_id,
            step="publish",
            outcome="succeeded",
            failure_type=None,
            target="latest",
            latest_affected=True,
            latest_action="published",
            archive_only_failure=False,
            retry_required=False,
            message="latest merged publish completed",
        ),
    )

    if request.archive_target_period:
        try:
            _archive_generation(paths, request.archive_target_period, paths.latest_root)
        except Exception as exc:
            status_record = GenerationStatusRecord(
                generation_id=request.generation_id,
                accepted=True,
                staging_result="succeeded",
                publish_result="succeeded",
                archive_result="failed",
                latest_action="published",
                affected_screens=affected_screens,
                rendered_files=rendered_files,
                archive_failures=(str(exc),),
            )
            _write_status(generation_root / "status.json", status_record)
            _append_operation_log(
                operation_log_path,
                OperationLogRecord(
                    generation_id=request.generation_id,
                    step="archive",
                    outcome="failed",
                    failure_type="archive_failure",
                    target=request.archive_target_period,
                    latest_affected=False,
                    latest_action="published",
                    archive_only_failure=True,
                    retry_required=True,
                    message=str(exc),
                ),
            )
            return _build_result(
                request,
                generation_root,
                paths.latest_root,
                status="published_with_archive_failure",
                status_record=status_record,
                operation_log_path=operation_log_path,
            )
        _append_operation_log(
            operation_log_path,
            OperationLogRecord(
                generation_id=request.generation_id,
                step="archive",
                outcome="succeeded",
                failure_type=None,
                target=request.archive_target_period,
                latest_affected=False,
                latest_action="published",
                archive_only_failure=False,
                retry_required=False,
                message="archive export completed from successful latest publish",
            ),
        )
        archive_result = "succeeded"
    else:
        archive_result = "skipped"

    status_record = GenerationStatusRecord(
        generation_id=request.generation_id,
        accepted=True,
        staging_result="succeeded",
        publish_result="succeeded",
        archive_result=archive_result,
        latest_action="published",
        affected_screens=affected_screens,
        rendered_files=rendered_files,
    )
    _write_status(generation_root / "status.json", status_record)
    return _build_result(
        request,
        generation_root,
        paths.latest_root,
        status="published",
        status_record=status_record,
        operation_log_path=operation_log_path,
    )
