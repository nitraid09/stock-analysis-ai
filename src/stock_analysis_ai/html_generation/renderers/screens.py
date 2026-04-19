"""Screen renderer entry points."""

from __future__ import annotations

from typing import Iterable

from ..contracts import RenderInput, RenderedPage
from .common import render_document


def render_many(render_inputs: Iterable[RenderInput]) -> list[RenderedPage]:
    return [render_document(render_input) for render_input in render_inputs]
