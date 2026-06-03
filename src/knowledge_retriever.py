from __future__ import annotations

from .knowledge_loader import KnowledgeBase


def get_metric_definition(metric_key: str, kb: KnowledgeBase) -> dict:
    return kb.metric_catalog.get(metric_key, {})


def get_skill_context(skill_id: str, kb: KnowledgeBase) -> dict:
    return kb.skills.get(skill_id, {})
