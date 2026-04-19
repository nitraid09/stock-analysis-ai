"""Shared HTML rendering helpers."""

from __future__ import annotations

from html import escape
from typing import Any, Iterable, Mapping

from ..anchor_helper import build_anchor
from ..contracts import RenderInput, RenderedPage
from ..screen_registry import get_screen_definition
from ..state_labels import get_state_label


BASE_CSS = """
body { margin: 0; font-family: "Segoe UI", sans-serif; background: #f5f4ef; color: #1f2328; }
.shell { max-width: 1280px; margin: 0 auto; padding: 0 24px 48px; }
.page-header { position: sticky; top: 0; z-index: 20; background: rgba(245, 244, 239, 0.97); backdrop-filter: blur(6px); border-bottom: 1px solid #d8d0bf; padding: 20px 0 12px; }
.page-header h1 { margin: 0 0 6px; font-size: 32px; }
.meta { font-size: 13px; color: #4e5964; display: flex; gap: 16px; flex-wrap: wrap; }
.toolbar { position: sticky; top: 92px; z-index: 10; background: #fffdf7; border: 1px solid #d8d0bf; border-radius: 12px; padding: 12px 16px; margin: 20px 0; }
.summary-grid, .field-grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
.card, .record-card, section { background: #fff; border: 1px solid #ddd5c3; border-radius: 14px; padding: 16px; box-shadow: 0 6px 20px rgba(31, 35, 40, 0.05); }
.record-card { margin-top: 12px; }
.record-card h3, section h2 { margin-top: 0; }
.field { display: flex; flex-direction: column; gap: 4px; }
.label { font-size: 12px; color: #5b6470; text-transform: uppercase; letter-spacing: 0.04em; }
.value { font-size: 16px; }
.state-pill { display: inline-flex; align-items: center; border-radius: 999px; padding: 4px 10px; background: #ece7da; font-size: 12px; margin-top: 6px; }
.anchor-list { display: flex; gap: 10px; flex-wrap: wrap; margin: 18px 0; padding: 0; list-style: none; }
.anchor-list a, .links a { color: #0d5c63; text-decoration: none; }
.text-block { white-space: pre-wrap; line-height: 1.6; }
.list { margin: 0; padding-left: 20px; }
.links { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 12px; }
"""


def _render_field(field: Mapping[str, Any]) -> str:
    label = escape(str(field.get("label", "")))
    value = escape(str(field.get("value", "")))
    state_html = ""
    state = field.get("state")
    if state:
        descriptor = get_state_label(str(state))
        state_html = f'<span class="state-pill" title="{escape(descriptor.meaning)}">{escape(descriptor.label)}</span>'
    return f'<div class="field"><span class="label">{label}</span><span class="value">{value}</span>{state_html}</div>'


def _render_fields(fields: Iterable[Mapping[str, Any]]) -> str:
    html = "".join(_render_field(field) for field in fields)
    return f'<div class="field-grid">{html}</div>' if html else ""


def _render_items(items: Iterable[Any]) -> str:
    rendered = "".join(f"<li>{escape(str(item))}</li>" for item in items)
    return f'<ul class="list">{rendered}</ul>' if rendered else ""


def _render_links(links: Iterable[Mapping[str, Any]]) -> str:
    rendered_links: list[str] = []
    for link in links:
        label = escape(str(link.get("label", "link")))
        href = link.get("href")
        if not href and link.get("anchor_kind") and link.get("anchor_key"):
            href = f'#{build_anchor(str(link["anchor_kind"]), str(link["anchor_key"]))}'
        if not href:
            continue
        rendered_links.append(f'<a href="{escape(str(href), quote=True)}">{label}</a>')
    return f'<div class="links">{"".join(rendered_links)}</div>' if rendered_links else ""


def _render_record(record: Mapping[str, Any]) -> str:
    anchor_html = ""
    if record.get("anchor_kind") and record.get("anchor_key"):
        anchor_id = build_anchor(str(record["anchor_kind"]), str(record["anchor_key"]))
        anchor_html = f' id="{escape(anchor_id, quote=True)}"'
    heading = escape(str(record.get("title", "")))
    body = ""
    if "fields" in record:
        body += _render_fields(record.get("fields", []))
    if "items" in record:
        body += _render_items(record.get("items", []))
    if "text" in record:
        body += f'<div class="text-block">{escape(str(record.get("text", "")))}</div>'
    if "links" in record:
        body += _render_links(record.get("links", []))
    return f'<article class="record-card"{anchor_html}><h3>{heading}</h3>{body}</article>'


def _render_records(records: Iterable[Mapping[str, Any]]) -> str:
    return "".join(_render_record(record) for record in records)


def _render_section(section: Mapping[str, Any]) -> str:
    section_id = escape(str(section.get("id", "section")), quote=True)
    title = escape(str(section.get("title", "")))
    html_parts = [f'<section id="section-{section_id}"><h2>{title}</h2>']
    if "summary_cards" in section:
        cards = "".join(f'<div class="card">{_render_field(card)}</div>' for card in section.get("summary_cards", []))
        if cards:
            html_parts.append(f'<div class="summary-grid">{cards}</div>')
    if "fields" in section:
        html_parts.append(_render_fields(section.get("fields", [])))
    if "items" in section:
        html_parts.append(_render_items(section.get("items", [])))
    if "text" in section:
        html_parts.append(f'<div class="text-block">{escape(str(section.get("text", "")))}</div>')
    if "records" in section:
        html_parts.append(_render_records(section.get("records", [])))
    if "links" in section:
        html_parts.append(_render_links(section.get("links", [])))
    html_parts.append("</section>")
    return "".join(html_parts)


def _sort_sections(render_input: RenderInput) -> list[Mapping[str, Any]]:
    sections = list(render_input.page_data.get("sections", []))
    definition = get_screen_definition(render_input.screen_id)
    rank = {block_id: index for index, block_id in enumerate(definition.block_order)}
    return sorted(
        sections,
        key=lambda section: (
            rank.get(str(section.get("id", "")), len(rank)),
            str(section.get("title", "")),
        ),
    )


def render_document(render_input: RenderInput) -> RenderedPage:
    title = escape(render_input.title)
    metadata = render_input.metadata
    toolbar_html = ""
    toolbar = render_input.page_data.get("toolbar", [])
    if toolbar:
        toolbar_html = f'<div class="toolbar">{_render_fields(toolbar)}</div>'
    anchors = render_input.shared_data.get("anchor_index", [])
    anchor_html = ""
    if anchors:
        anchor_links = "".join(
            f'<li><a href="#{escape(str(anchor.get("id", "")), quote=True)}">{escape(str(anchor.get("label", "")))}</a></li>'
            for anchor in anchors
        )
        anchor_html = f'<ul class="anchor-list">{anchor_links}</ul>'
    summary_cards = render_input.page_data.get("summary_cards", [])
    summary_html = ""
    if summary_cards:
        cards = "".join(f'<div class="card">{_render_field(card)}</div>' for card in summary_cards)
        summary_html = f'<div class="summary-grid">{cards}</div>'
    sections_html = "".join(_render_section(section) for section in _sort_sections(render_input))
    page_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>{BASE_CSS}</style>
</head>
<body>
  <div class="shell">
    <header class="page-header">
      <h1>{title}</h1>
      <div class="meta">
        <span>screen_id: {escape(render_input.screen_id)}</span>
        <span>generation_id: {escape(metadata.generation_id)}</span>
        <span>generated_at: {escape(metadata.iso_generated_at())}</span>
      </div>
    </header>
    {toolbar_html}
    {anchor_html}
    {summary_html}
    {sections_html}
  </div>
</body>
</html>
"""
    return RenderedPage(
        screen_id=render_input.screen_id,
        title=render_input.title,
        relative_output_path=render_input.relative_output_path,
        html=page_html,
        natural_key=render_input.natural_key,
    )
