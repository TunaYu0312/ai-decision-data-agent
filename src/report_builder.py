from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import AnalysisResult


def build_html_report(
    analysis_result: AnalysisResult,
    project_root: Path | None = None,
    output_dir: Path | None = None,
    template_name: str = "html_report_base.html",
) -> Path:
    root = project_root or Path(__file__).resolve().parents[1]
    output = output_dir or root / "outputs" / "html_reports"
    output.mkdir(parents=True, exist_ok=True)
    env = Environment(
        loader=FileSystemLoader(root / "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template(template_name)
    tables = {
        name: df.to_html(index=False, classes="data-table", border=0)
        for name, df in analysis_result.appendix_tables.items()
        if not df.empty
    }
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output / f"{analysis_result.skill_id}_{timestamp}.html"
    html = template.render(result=analysis_result, tables=tables)
    path.write_text(html, encoding="utf-8")
    return path


def build_markdown_report(analysis_result: AnalysisResult, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{analysis_result.skill_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    lines = [
        f"# {analysis_result.skill_name}",
        "",
        "## 1. Executive Summary",
        analysis_result.executive_summary,
        "",
        "## 2. Data Availability Check",
        analysis_result.data_availability_check,
        "",
        "## 3. Key Metrics",
    ]
    lines.extend([f"- {metric.name}: {metric.value}" for metric in analysis_result.key_metrics])
    sections = [
        ("## 4. Key Findings", analysis_result.key_findings),
        ("## 5. Root Cause / Driver Analysis", analysis_result.driver_analysis),
        ("## 6. Decision Options", analysis_result.decision_options),
    ]
    for title, items in sections:
        lines.extend(["", title])
        lines.extend([f"- {item}" for item in items])
    lines.extend(["", "## 7. Recommended Decision", analysis_result.recommended_decision])
    lines.extend(["", "## 8. Action Plan"])
    lines.extend([f"- {item['owner']} | {item['priority']} | {item['timeline']} | {item['action_item']} | {item['kpi']}" for item in analysis_result.action_plan])
    lines.extend(["", "## 9. KPI Tracking"])
    lines.extend([f"- {item}" for item in analysis_result.kpi_tracking])
    lines.extend(["", "## 10. Risk & Assumptions"])
    lines.extend([f"- {item}" for item in analysis_result.risks_assumptions])
    lines.extend(["", "## 11. Review Plan", analysis_result.review_plan])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
