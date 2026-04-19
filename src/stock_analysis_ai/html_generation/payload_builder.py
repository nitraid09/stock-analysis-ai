"""Build render inputs from display payloads without touching storage details."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Iterable, Mapping

from .contracts import GenerationMetadata, RenderInput
from .exceptions import PayloadContractError
from .screen_registry import build_screen_output_path, get_screen_definition


def _ensure_mapping(value: Any, message: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PayloadContractError(message)
    return value


def _build_single_screen_input(
    screen_id: str,
    screen_payload: Mapping[str, Any],
    shared_data: Mapping[str, Any],
    metadata: GenerationMetadata,
) -> RenderInput:
    definition = get_screen_definition(screen_id)
    return RenderInput(
        screen_id=screen_id,
        title=str(screen_payload.get("title", definition.title)),
        relative_output_path=build_screen_output_path(screen_id),
        page_data=screen_payload,
        shared_data=shared_data,
        metadata=metadata,
    )


def _build_multi_screen_inputs(
    screen_id: str,
    screen_payload: Any,
    shared_data: Mapping[str, Any],
    metadata: GenerationMetadata,
) -> list[RenderInput]:
    definition = get_screen_definition(screen_id)
    if not isinstance(screen_payload, list):
        raise PayloadContractError(f"{screen_id} payload must be a list of items.")
    render_inputs: list[RenderInput] = []
    for item in screen_payload:
        item_mapping = _ensure_mapping(item, f"{screen_id} item must be a mapping.")
        natural_key_name = definition.natural_key_name
        assert natural_key_name is not None
        natural_key = item_mapping.get(natural_key_name) or item_mapping.get("key")
        if not natural_key:
            raise PayloadContractError(f"{screen_id} item requires {natural_key_name}.")
        render_inputs.append(
            RenderInput(
                screen_id=screen_id,
                title=str(item_mapping.get("title", definition.title)),
                relative_output_path=build_screen_output_path(screen_id, str(natural_key)),
                page_data=item_mapping,
                shared_data=shared_data,
                metadata=metadata,
                natural_key=str(natural_key),
            )
        )
    return render_inputs


def build_render_inputs(
    payload: Mapping[str, Any],
    metadata: GenerationMetadata,
    screen_ids: Iterable[str],
) -> list[RenderInput]:
    payload_mapping = _ensure_mapping(payload, "payload must be a mapping.")
    screens = _ensure_mapping(payload_mapping.get("screens", {}), "payload.screens must be a mapping.")
    shared_data = _ensure_mapping(payload_mapping.get("shared", {}), "payload.shared must be a mapping.")
    ordered_inputs: "OrderedDict[str, RenderInput]" = OrderedDict()
    multi_inputs: list[RenderInput] = []

    for screen_id in screen_ids:
        definition = get_screen_definition(screen_id)
        if screen_id not in screens:
            raise PayloadContractError(f"Missing payload for required screen: {screen_id}")
        screen_payload = screens[screen_id]
        if definition.is_multi_file:
            multi_inputs.extend(_build_multi_screen_inputs(screen_id, screen_payload, shared_data, metadata))
            continue
        ordered_inputs[screen_id] = _build_single_screen_input(screen_id, _ensure_mapping(screen_payload, f"{screen_id} payload must be a mapping."), shared_data, metadata)

    return list(ordered_inputs.values()) + multi_inputs
