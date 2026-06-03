from __future__ import annotations

from pathlib import Path


def ensure_output_dirs(project_root: Path) -> None:
    (project_root / "outputs" / "markdown").mkdir(parents=True, exist_ok=True)
    (project_root / "outputs" / "html_reports").mkdir(parents=True, exist_ok=True)
