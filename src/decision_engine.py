from __future__ import annotations

from typing import Any


def build_action_plan(theme: str, priority: str = "High") -> list[dict[str, Any]]:
    return [
        {
            "owner": "销售运营",
            "priority": priority,
            "timeline": "7天内",
            "action_item": f"确认{theme}的重点对象名单，并完成一轮业务复盘。",
            "kpi": "重点对象触达率、问题确认率",
        },
        {
            "owner": "区域负责人",
            "priority": priority,
            "timeline": "14天内",
            "action_item": f"执行{theme}的辅导或推广动作，并跟踪过程指标。",
            "kpi": "参与率、订单数、销售额",
        },
        {
            "owner": "数据团队",
            "priority": "Medium",
            "timeline": "下个经营周期",
            "action_item": "复盘行动前后指标变化，判断是否形成可复制机制。",
            "kpi": "销售额变化、AC变化、留存或活跃变化",
        },
    ]


def build_decision_output(skill_id: str, metrics: dict, findings: list[str]) -> dict:
    if skill_id == "generic_data_analysis":
        return {
            "options": ["先做数据质量修复", "围绕关键字段做分组对比", "补充业务口径后进入专题分析"],
            "recommended": "当前数据不匹配五个专业专题，建议先使用通用分析理解字段、质量、分布和异常，再决定是否需要补充业务字段。",
            "actions": [
                {
                    "owner": "数据团队",
                    "priority": "High",
                    "timeline": "当天",
                    "action_item": "确认每个 Sheet 的业务含义、主键字段、时间字段和核心指标字段。",
                    "kpi": "字段解释完整率、缺失字段数量",
                },
                {
                    "owner": "业务负责人",
                    "priority": "Medium",
                    "timeline": "3天内",
                    "action_item": "基于通用画像选择需要深入追问的业务问题。",
                    "kpi": "确认的问题清单、优先级",
                },
                {
                    "owner": "数据团队",
                    "priority": "Medium",
                    "timeline": "7天内",
                    "action_item": "如需进入五个专业专题，补齐对应 Sheet 或字段。",
                    "kpi": "专业 Skill 可运行率",
                },
            ],
            "kpis": ["行数", "字段数", "缺失率", "数值字段分布", "分类字段 Top 值"],
        }
    if skill_id == "distributor_performance_fluctuation":
        return {
            "options": ["优先修复订单数下滑", "优化产品结构与客单价", "聚焦头部经销商专项辅导"],
            "recommended": "优先处理销售额贡献最大的下滑来源，再复制逆势增长经销商的打法。",
            "actions": build_action_plan("经销商业绩波动"),
            "kpis": ["销售额", "订单数", "AC", "活跃经销商人数", "产品结构占比"],
        }
    if skill_id == "subscription_insight":
        return {
            "options": ["扩大高留存产品订阅", "补强低转化区域培训", "建立流失预警机制"],
            "recommended": "优先推动留存较健康且 LTV 更高的订阅产品和经销商团队。",
            "actions": build_action_plan("订阅增长"),
            "kpis": ["新增订阅数", "有效订阅数", "流失率", "订阅收入", "订阅LTV"],
        }
    if skill_id == "prysm_io_adoption":
        return {
            "options": ["补齐激活培训", "跟进激活后沉默用户", "复制高活跃区域打法"],
            "recommended": "先把激活后7天使用跟进做实，再扩大高潜经销商推广。",
            "actions": build_action_plan("Prysm IO推广"),
            "kpis": ["激活率", "活跃使用率", "使用次数", "活跃天数", "销售额变化"],
        }
    if skill_id == "community_operation_evaluation":
        return {
            "options": ["扩大下一期", "仅保留高参与度机制", "暂停扩大并复盘内容"],
            "recommended": "是否扩大取决于 DID 净增量和样本匹配质量，不能只看实验组前后增长。",
            "actions": build_action_plan("社群陪跑"),
            "kpis": ["DID净增量", "参与率", "任务完成率", "实验组销售变化", "对照组销售变化"],
        }
    return {
        "options": ["加大产品推广", "优化活动机制", "设计高 lift 产品组合"],
        "recommended": "优先推广销售增长且没有明显蚕食风险的产品组合。",
        "actions": build_action_plan("产品及活动评估"),
        "kpis": ["产品销售额", "品类占比", "活动提升", "毛利", "support/confidence/lift"],
    }
