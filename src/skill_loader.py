from __future__ import annotations

from pathlib import Path

from .knowledge_loader import KnowledgeBase


def load_skills(project_root: Path | None = None) -> dict:
    return KnowledgeBase.load_default(project_root).skills
