from __future__ import annotations

from dataclasses import dataclass


@dataclass
class IntentRoute:
    mode: str
    skill_id: str | None
    reason: str


SKILL_KEYWORDS = {
    "distributor_performance_fluctuation": ["经销商", "直销员", "业绩波动", "下降原因", "订单数", "客单价", "ac", "区域业绩"],
    "subscription_insight": ["订阅", "留存", "流失", "ltv", "订阅客户", "新增订阅"],
    "prysm_io_adoption": ["prysm", "工具推广", "激活率", "使用率", "使用深度"],
    "community_operation_evaluation": ["社群", "陪跑", "实验组", "对照组", "did", "参与强度"],
    "product_campaign_evaluation": ["产品", "品类", "活动", "campaign", "套装", "组合", "关联规则", "lift"],
}


def route_question(question: str, available_skill_id: str | None = None) -> IntentRoute:
    text = question.lower()
    best_skill = None
    best_hits = 0
    for skill_id, keywords in SKILL_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword.lower() in text)
        if hits > best_hits:
            best_skill = skill_id
            best_hits = hits
    if best_skill and best_hits >= 1:
        return IntentRoute("professional_skill", best_skill, f"问题命中 {best_hits} 个专业专题关键词。")
    return IntentRoute("generic_query", None, "问题未命中专业专题关键词，使用通用问数。")
