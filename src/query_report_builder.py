from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .query_engine import QueryAnswer
from .report_formatting import first_meaningful_line, markdown_to_html


def build_query_html_report(answer: QueryAnswer, project_root: Path | None = None, output_dir: Path | None = None) -> Path:
    root = project_root or Path(__file__).resolve().parents[1]
    output = output_dir or root / "outputs" / "html_reports"
    output.mkdir(parents=True, exist_ok=True)
    env = Environment(
        loader=FileSystemLoader(root / "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("query_report.html")
    tables = [
        {
            "title": f"结果表 {index}",
            "shape": f"{len(table)} 行 x {len(table.columns)} 列",
            "html": table.to_html(index=False, border=0, classes="data-table"),
        }
        for index, table in enumerate(answer.tables, start=1)
        if not table.empty
    ]
    coverage = []
    if answer.tables:
        first_table = answer.tables[0]
        if {"sheet", "rows", "columns"}.issubset(first_table.columns):
            total_rows = int(first_table["rows"].sum())
            total_columns = int(first_table["columns"].sum())
            coverage = [
                {"label": "Sheets", "value": str(len(first_table)), "note": "已读取的数据表"},
                {"label": "Rows", "value": f"{total_rows:,}", "note": "合计记录数"},
                {"label": "Fields", "value": f"{total_columns:,}", "note": "合计字段数"},
            ]
    path = output / f"query_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.html"
    html = template.render(
        question=answer.question,
        answer_html=markdown_to_html(answer.answer),
        headline=first_meaningful_line(answer.answer),
        evidence=answer.evidence,
        limitations=answer.limitations,
        charts=answer.charts,
        tables=tables,
        coverage=coverage,
        provider=answer.llm_provider if answer.llm_used else "本地规则",
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    path.write_text(html, encoding="utf-8")
    return path
