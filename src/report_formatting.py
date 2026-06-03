from __future__ import annotations

import html
import re


def _format_inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
    return escaped


def _render_markdown_table(lines: list[str]) -> str | None:
    if len(lines) < 2:
        return None
    header = [cell.strip() for cell in lines[0].strip().strip("|").split("|")]
    divider = [cell.strip() for cell in lines[1].strip().strip("|").split("|")]
    if not header or not all(re.fullmatch(r":?-{3,}:?", cell) for cell in divider):
        return None

    rows = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < len(header):
            cells.extend([""] * (len(header) - len(cells)))
        rows.append(cells[: len(header)])

    head_html = "".join(f"<th>{_format_inline(cell)}</th>" for cell in header)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{_format_inline(cell)}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return f"<div class=\"table-scroll\"><table><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table></div>"


def markdown_to_html(markdown_text: str) -> str:
    """Render a small, safe Markdown subset used by query reports."""
    lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    table_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            blocks.append("<p>" + "<br>".join(_format_inline(line) for line in paragraph) + "</p>")
            paragraph = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            blocks.append("<ul>" + "".join(f"<li>{item}</li>" for item in list_items) + "</ul>")
            list_items = []

    def flush_table() -> None:
        nonlocal table_lines
        if table_lines:
            rendered = _render_markdown_table(table_lines)
            if rendered:
                blocks.append(rendered)
            else:
                for item in table_lines:
                    paragraph.append(item)
            table_lines = []

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            flush_table()
            flush_list()
            flush_paragraph()
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            flush_paragraph()
            flush_list()
            table_lines.append(stripped)
            continue

        flush_table()
        heading_match = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if heading_match:
            flush_list()
            flush_paragraph()
            level = min(len(heading_match.group(1)) + 1, 4)
            blocks.append(f"<h{level}>{_format_inline(heading_match.group(2))}</h{level}>")
            continue

        list_match = re.match(r"^([-*]|\d+[.)])\s+(.+)$", stripped)
        if list_match:
            flush_paragraph()
            list_items.append(_format_inline(list_match.group(2)))
            continue

        flush_list()
        paragraph.append(stripped)

    flush_table()
    flush_list()
    flush_paragraph()
    return "\n".join(blocks)


def first_meaningful_line(markdown_text: str) -> str:
    for raw_line in markdown_text.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^([-*]|\d+[.)])\s+", "", line)
        return re.sub(r"\*\*(.+?)\*\*", r"\1", line)
    return "请查看下方分析正文。"
