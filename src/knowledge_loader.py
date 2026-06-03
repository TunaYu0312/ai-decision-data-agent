from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class KnowledgeBase:
    project_root: Path
    business_terms: str
    metric_catalog: dict
    sheet_schema_catalog: dict
    skill_sop: dict
    field_aliases: dict
    skills: dict

    @classmethod
    def load_default(cls, project_root: Path | None = None) -> "KnowledgeBase":
        root = project_root or Path(__file__).resolve().parents[1]
        kb_root = root / "knowledge_base"
        skills_root = root / "skills"
        return cls(
            project_root=root,
            business_terms=(kb_root / "glossary" / "business_terms.md").read_text(encoding="utf-8"),
            metric_catalog=_load_yaml(kb_root / "metrics" / "metric_catalog.yaml"),
            sheet_schema_catalog=_load_yaml(kb_root / "schema" / "sheet_schema_catalog.yaml"),
            skill_sop=_load_yaml(kb_root / "skills" / "skill_sop.yaml"),
            field_aliases=_load_yaml(kb_root / "field_alias" / "field_alias.yaml"),
            skills=_load_skills(skills_root),
        )


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _load_skills(path: Path) -> dict:
    skills: dict = {}
    for skill_file in sorted(path.glob("*.yaml")):
        item = _load_yaml(skill_file)
        skills[item["skill_id"]] = item
    return skills
