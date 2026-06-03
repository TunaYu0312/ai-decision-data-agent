from __future__ import annotations

from dataclasses import dataclass

from .models import FieldMappingResult, WorkbookContext


@dataclass
class SheetRole:
    uploaded_sheet: str
    role: str
    score: float
    matched_fields: list[str]
    missing_required_fields: list[str]


@dataclass
class SkillSelection:
    skill_id: str
    score: float
    matched_roles: list[str]
    missing_roles: list[str]
    reason: str


SHEET_NAME_HINTS = {
    "distributor_monthly": ["distributor_monthly", "monthly", "月度", "业绩", "经销商", "直销员"],
    "sales_order": ["sales_order", "order", "订单", "流水", "销售明细"],
    "product_master": ["product_master", "product", "sku", "产品", "商品"],
    "subscription_monthly": ["subscription_monthly", "订阅月度", "订阅汇总"],
    "subscription_customer": ["subscription_customer", "订阅客户", "订阅顾客"],
    "prysm_usage": ["prysm_usage", "prysm", "工具", "使用"],
    "community_project": ["community_project", "社群项目", "项目"],
    "community_participant": ["community_participant", "参与者", "陪跑名单"],
    "product_sales": ["product_sales", "产品销售", "品类销售"],
    "campaign_master": ["campaign_master", "活动主数据", "活动资料"],
    "campaign_sales": ["campaign_sales", "活动销售", "活动订单"],
}


def _role_score(sheet_name: str, mapped_fields: set[str], role: str, schema: dict) -> tuple[float, list[str], list[str]]:
    fields = schema.get("fields", {})
    required = {field for field, config in fields.items() if config.get("required")}
    optional = set(fields) - required
    required_matches = sorted(required & mapped_fields)
    optional_matches = sorted(optional & mapped_fields)
    missing_required = sorted(required - mapped_fields)
    if not fields:
        return 0.0, [], []

    required_score = len(required_matches) / max(len(required), 1)
    optional_score = len(optional_matches) / max(len(optional), 1) if optional else 0
    hint_score = 0.0
    lower_name = sheet_name.lower()
    for hint in SHEET_NAME_HINTS.get(role, []):
        if hint.lower() in lower_name:
            hint_score = 0.15
            break
    score = min(1.0, required_score * 0.72 + optional_score * 0.18 + hint_score)
    return round(score, 4), required_matches + optional_matches, missing_required


def infer_sheet_roles(
    context: WorkbookContext,
    mappings: dict[str, FieldMappingResult],
    sheet_schema_catalog: dict,
) -> dict[str, SheetRole]:
    """Infer canonical business sheet roles from arbitrary uploaded sheet names."""
    inferred: dict[str, SheetRole] = {}
    claimed_roles: set[str] = set()
    candidates: list[SheetRole] = []

    for sheet_name in context.sheets:
        mapped_fields = mappings.get(sheet_name).standard_fields() if sheet_name in mappings else set()
        for role, schema in sheet_schema_catalog.items():
            score, matched, missing = _role_score(sheet_name, mapped_fields, role, schema)
            if score >= 0.35:
                candidates.append(SheetRole(sheet_name, role, score, matched, missing))

    for candidate in sorted(candidates, key=lambda item: item.score, reverse=True):
        if candidate.uploaded_sheet in inferred or candidate.role in claimed_roles:
            continue
        inferred[candidate.uploaded_sheet] = candidate
        claimed_roles.add(candidate.role)
    return inferred


def auto_select_skill(
    roles: dict[str, SheetRole],
    mappings: dict[str, FieldMappingResult],
    skills: dict,
    sheet_schema_catalog: dict,
) -> SkillSelection:
    role_scores = {role.role: role.score for role in roles.values()}
    selections: list[SkillSelection] = []

    for skill_id, skill in skills.items():
        if skill_id == "generic_data_analysis":
            continue
        required_roles = list(skill.get("required_sheets", []))
        optional_roles = list(skill.get("optional_sheets", []))
        matched_required = [role for role in required_roles if role in role_scores]
        missing_required = [role for role in required_roles if role not in role_scores]
        matched_optional = [role for role in optional_roles if role in role_scores]
        required_coverage = len(matched_required) / max(len(required_roles), 1)
        quality = sum(role_scores.get(role, 0) for role in matched_required) / max(len(required_roles), 1)
        optional_bonus = min(0.1, len(matched_optional) * 0.03)
        score = round(required_coverage * 0.65 + quality * 0.3 + optional_bonus, 4)
        reason = f"匹配到 {len(matched_required)}/{len(required_roles)} 个必需数据角色。"
        selections.append(SkillSelection(skill_id, score, matched_required + matched_optional, missing_required, reason))

    selections.sort(key=lambda item: item.score, reverse=True)
    if not selections or selections[0].score < 0.45 or not selections[0].matched_roles:
        return SkillSelection(
            "generic_data_analysis",
            1.0,
            [],
            [],
            "未匹配到五个专业专题所需的数据结构，自动切换为通用数据分析。",
        )
    return selections[0]


def prepare_context_for_skill(
    context: WorkbookContext,
    mappings: dict[str, FieldMappingResult],
    roles: dict[str, SheetRole],
    skill_id: str,
) -> tuple[WorkbookContext, dict[str, FieldMappingResult]]:
    """Return a context whose sheet names use canonical roles expected by skill runners."""
    role_by_uploaded = {sheet: role.role for sheet, role in roles.items()}
    canonical_sheets = {}
    canonical_mappings = {}
    for uploaded_sheet, df in context.sheets.items():
        canonical_name = role_by_uploaded.get(uploaded_sheet, uploaded_sheet)
        canonical_sheets[canonical_name] = df
        if uploaded_sheet in mappings:
            mapping = mappings[uploaded_sheet]
            mapping.sheet_name = canonical_name
            canonical_mappings[canonical_name] = mapping
    return (
        WorkbookContext(
            file_name=context.file_name,
            file_type=context.file_type,
            sheets=canonical_sheets,
            source_path=context.source_path,
        ),
        canonical_mappings,
    )
