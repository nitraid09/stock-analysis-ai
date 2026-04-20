"""URL state helpers that keep path, query, and hash responsibilities separate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlencode

from .exceptions import ContractError
from .screen_registry import build_screen_output_path, get_screen_definition


@dataclass(frozen=True)
class UrlState:
    """A resolved public URL with separated path, query, and hash state."""

    path: str
    query: Mapping[str, str]
    anchor: str | None = None

    def __post_init__(self) -> None:
        if "?" in self.path or "#" in self.path:
            raise ContractError("path must not contain query or hash fragments.")
        if self.anchor and self.anchor.startswith("#"):
            raise ContractError("anchor must not include a leading '#'.")
        if self.anchor and any(token in self.anchor for token in ("?", "#", "/")):
            raise ContractError("anchor must only represent an in-page stable-key fragment.")

    def as_url(self) -> str:
        query_string = urlencode([(key, value) for key, value in self.query.items() if value != ""])
        suffix = f"?{query_string}" if query_string else ""
        hash_part = f"#{self.anchor}" if self.anchor else ""
        return f"{self.path}{suffix}{hash_part}"


def normalize_query_state(
    screen_id: str,
    raw_query: Mapping[str, object] | None,
) -> dict[str, str]:
    definition = get_screen_definition(screen_id)
    normalized = dict(definition.default_query)
    if not raw_query:
        return normalized
    for key, value in raw_query.items():
        if key not in definition.allowed_query_keys:
            continue
        if value is None:
            continue
        normalized[key] = str(value)
    return normalized


def build_screen_url(
    screen_id: str,
    *,
    natural_key: str | None = None,
    query: Mapping[str, object] | None = None,
    anchor: str | None = None,
) -> str:
    path = build_screen_output_path(screen_id, natural_key).as_posix()
    state = UrlState(path=path, query=normalize_query_state(screen_id, query), anchor=anchor)
    return state.as_url()
