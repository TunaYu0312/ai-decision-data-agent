from __future__ import annotations

from itertools import combinations
from typing import Callable

import pandas as pd

from .decision_engine import build_decision_output
from .field_mapper import validate_skill_inputs
from .knowledge_loader import KnowledgeBase
from .models import AnalysisResult, FieldMappingResult, MetricValue, WorkbookContext
from .visualization_builder import bar_chart, funnel_chart, pie_chart, scatter_chart, trend_chart


def _mapped_sheet(context: WorkbookContext, mappings: dict[str, FieldMappingResult], sheet: str) -> pd.DataFrame:
    if sheet not in context.sheets:
        return pd.DataFrame()
    df = context.sheets[sheet].copy()
    if sheet in mappings:
        df = df.rename(columns=mappings[sheet].rename_map())
    return df


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[col], errors="coerce").fillna(0)


def _safe_div(numerator: float, denominator: float) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 0.0


def _has_columns(df: pd.DataFrame, columns: list[str]) -> bool:
    return not df.empty and all(column in df.columns for column in columns)


def _latest_previous(df: pd.DataFrame, period_col: str = "month") -> tuple[str | None, str | None]:
    if period_col not in df:
        return None, None
    periods = sorted(df[period_col].dropna().astype(str).unique().tolist())
    if not periods:
        return None, None
    if len(periods) == 1:
        return periods[-1], None
    return periods[-1], periods[-2]


def _availability(validation) -> str:
    if validation.can_run_full_analysis:
        base = "本次上传数据满足该 Skill 的必需 Sheet 与必填字段，可执行完整分析。"
    else:
        base = "当前数据无法完整执行该 Skill，只能做有限分析。"
    details = []
    if validation.missing_required_sheets:
        details.append("缺少 Sheet: " + ", ".join(validation.missing_required_sheets))
    if validation.missing_required_fields:
        field_msg = "; ".join(f"{sheet}: {', '.join(fields)}" for sheet, fields in validation.missing_required_fields.items())
        details.append("缺少字段: " + field_msg)
    if validation.warnings:
        details.extend(validation.warnings)
    return base + (" " + " ".join(details) if details else "")


def _make_result(
    skill_id: str,
    kb: KnowledgeBase,
    question: str,
    validation,
    summary: str,
    metrics: list[MetricValue],
    findings: list[str],
    drivers: list[str],
    charts: list[dict[str, str]],
    appendix_tables: dict[str, pd.DataFrame] | None = None,
) -> AnalysisResult:
    decision = build_decision_output(skill_id, {metric.key: metric.value for metric in metrics}, findings)
    return AnalysisResult(
        skill_id=skill_id,
        skill_name=kb.skills[skill_id]["name"],
        business_question=question,
        executive_summary=summary,
        data_availability_check=_availability(validation),
        key_metrics=metrics,
        key_findings=findings,
        driver_analysis=drivers,
        decision_options=decision["options"],
        recommended_decision=decision["recommended"],
        action_plan=decision["actions"],
        kpi_tracking=decision["kpis"],
        risks_assumptions=["上传数据默认已脱敏；样本周期、缺失字段和字段映射质量会影响结论可靠性。"],
        review_plan="建议在下一个经营周期结束后复盘同口径 KPI，并比较行动对象与未行动对象的变化差异。",
        charts=charts,
        appendix_tables=appendix_tables or {},
    )


def _run_distributor(context, mappings, question, kb, validation) -> AnalysisResult:
    monthly = _mapped_sheet(context, mappings, "distributor_monthly")
    orders = _mapped_sheet(context, mappings, "sales_order")
    latest, previous = _latest_previous(monthly)
    total_sales = float(_num(monthly, "sales_amount").sum())
    total_orders = float(_num(monthly, "order_count").sum())
    ac = _safe_div(total_sales, total_orders)
    latest_sales = float(_num(monthly[monthly["month"].astype(str) == latest], "sales_amount").sum()) if latest else total_sales
    previous_sales = float(_num(monthly[monthly["month"].astype(str) == previous], "sales_amount").sum()) if previous else 0
    sales_change = latest_sales - previous_sales if previous else 0
    sales_change_rate = _safe_div(sales_change, previous_sales)

    trend = monthly.groupby("month", as_index=False).agg({"sales_amount": "sum", "order_count": "sum"})
    trend["ac"] = trend.apply(lambda row: _safe_div(row["sales_amount"], row["order_count"]), axis=1)
    region_rank = monthly.groupby("region", as_index=False)["sales_amount"].sum().sort_values("sales_amount", ascending=False)
    distributor_rank = monthly.groupby("distributor_id", as_index=False)["sales_amount"].sum().sort_values("sales_amount", ascending=False)
    product_mix = orders.groupby("product_category", as_index=False)["sales_amount"].sum().sort_values("sales_amount", ascending=False) if "product_category" in orders else pd.DataFrame()

    direction = "下降" if sales_change < 0 else "增长"
    findings = [
        f"{latest or '当前周期'}销售额较上一周期{direction}{abs(sales_change):,.0f}，变化率为{sales_change_rate:.1%}。",
        f"累计订单数为{total_orders:,.0f}，整体 AC 为{ac:,.2f}。",
        f"销售贡献最高区域为{region_rank.iloc[0]['region'] if not region_rank.empty else '未知'}。",
    ]
    drivers = [
        "先拆解销售额 = 订单数 x AC，再检查活跃经销商和产品结构。",
        "若销售额下降同时订单数下降，应优先排查触达、活动参与和经销商活跃度。",
        "若 AC 同步下降，应检查高价值产品占比和促销结构。"
    ]
    charts = [
        trend_chart(trend, "month", "sales_amount", "销售额趋势"),
        trend_chart(trend, "month", "order_count", "订单数趋势"),
        bar_chart(region_rank.head(10), "region", "sales_amount", "区域销售贡献排行"),
        bar_chart(distributor_rank.head(10), "distributor_id", "sales_amount", "经销商销售贡献 Top 10"),
        pie_chart(product_mix.head(8), "product_category", "sales_amount", "产品结构") if not product_mix.empty else {"title": "产品结构", "html": "<p>缺少产品品类字段。</p>"},
    ]
    metrics = [
        MetricValue("sales_amount", "销售额", round(total_sales, 2)),
        MetricValue("order_count", "订单数", int(total_orders)),
        MetricValue("ac", "AC", ac),
        MetricValue("sales_change_rate", "最近周期销售额变化率", f"{sales_change_rate:.1%}"),
    ]
    summary = f"本次分析显示，{latest or '当前周期'}销售额{direction}，核心需要从订单数、AC、区域贡献和产品结构四个层面定位。销售额合计为{total_sales:,.0f}，整体 AC 为{ac:,.2f}。建议优先处理贡献最大的下滑来源，并同步提炼逆势增长经销商打法。"
    return _make_result("distributor_performance_fluctuation", kb, question, validation, summary, metrics, findings, drivers, charts, {"经销商排行": distributor_rank})


def _run_subscription(context, mappings, question, kb, validation) -> AnalysisResult:
    monthly = _mapped_sheet(context, mappings, "subscription_monthly")
    customer = _mapped_sheet(context, mappings, "subscription_customer")
    new_count = float(_num(monthly, "new_subscriber_count").sum())
    active_count = float(_num(monthly, "active_subscriber_count").max() if "active_subscriber_count" in monthly else 0)
    churned = float(_num(monthly, "churned_subscriber_count").sum())
    retained = float(_num(monthly, "retained_subscriber_count").sum())
    retention = _safe_div(retained, retained + churned)
    revenue = float(_num(monthly, "subscription_revenue").sum())
    ltv = float(_num(customer, "total_subscription_revenue").mean()) if "total_subscription_revenue" in customer else 0
    region_rank = monthly.groupby("region", as_index=False)["new_subscriber_count"].sum().sort_values("new_subscriber_count", ascending=False)
    product_mix = customer.groupby("product_category", as_index=False)["customer_id_hash"].nunique().rename(columns={"customer_id_hash": "subscriber_count"}).sort_values("subscriber_count", ascending=False) if "product_category" in customer else pd.DataFrame()
    trend = monthly.groupby("month", as_index=False).agg({"new_subscriber_count": "sum", "active_subscriber_count": "sum"})
    metrics = [
        MetricValue("new_subscriber_count", "新增订阅数", int(new_count)),
        MetricValue("active_subscriber_count", "有效订阅数", int(active_count)),
        MetricValue("subscription_retention_rate", "估算留存率", f"{retention:.1%}"),
        MetricValue("subscription_ltv", "订阅客户平均LTV", round(ltv, 2)),
    ]
    findings = [
        f"新增订阅数为{new_count:,.0f}，有效订阅峰值为{active_count:,.0f}。",
        f"基于留存和流失字段估算，订阅留存率为{retention:.1%}。",
        f"订阅收入合计为{revenue:,.0f}，平均订阅 LTV 为{ltv:,.2f}。",
    ]
    drivers = ["订阅增长应同时看新增、留存和 LTV，不能只看新增。", "若新增高但留存低，应优先优化客户预期管理和跟进机制。"]
    charts = [
        trend_chart(trend, "month", "new_subscriber_count", "新增订阅趋势"),
        trend_chart(trend, "month", "active_subscriber_count", "有效订阅趋势"),
        bar_chart(region_rank.head(10), "region", "new_subscriber_count", "区域订阅新增排行"),
        pie_chart(product_mix.head(8), "product_category", "subscriber_count", "订阅产品结构") if not product_mix.empty else {"title": "订阅产品结构", "html": "<p>缺少产品品类字段。</p>"},
    ]
    summary = f"订阅业务本期新增{new_count:,.0f}人，有效订阅规模约{active_count:,.0f}人，估算留存率{retention:.1%}。增长机会应优先放在留存健康、LTV更高且经销商执行能力强的区域和产品。"
    return _make_result("subscription_insight", kb, question, validation, summary, metrics, findings, drivers, charts, {"区域订阅排行": region_rank})


def _run_prysm(context, mappings, question, kb, validation) -> AnalysisResult:
    usage = _mapped_sheet(context, mappings, "prysm_usage")
    monthly = _mapped_sheet(context, mappings, "distributor_monthly")
    eligible = float(_num(usage, "eligible_flag").sum()) if "eligible_flag" in usage else float(usage["distributor_id"].nunique())
    activated = float(_num(usage, "activated_flag").sum())
    active_users = float(usage.loc[_num(usage, "usage_count") > 0, "distributor_id"].nunique())
    activation_rate = _safe_div(activated, eligible)
    active_rate = _safe_div(active_users, activated)
    depth = float(_num(usage, "usage_count").mean())
    merged = usage.groupby("distributor_id", as_index=False)["usage_count"].sum()
    sales = monthly.groupby("distributor_id", as_index=False)["sales_amount"].sum() if "sales_amount" in monthly else pd.DataFrame()
    scatter = merged.merge(sales, on="distributor_id", how="left") if not sales.empty else merged
    region = usage.groupby("region", as_index=False).agg({"activated_flag": "sum", "usage_count": "sum"}).sort_values("usage_count", ascending=False)
    metrics = [
        MetricValue("prysm_activation_rate", "Prysm IO激活率", f"{activation_rate:.1%}"),
        MetricValue("prysm_active_usage_rate", "Prysm IO活跃使用率", f"{active_rate:.1%}"),
        MetricValue("prysm_usage_depth", "平均使用次数", round(depth, 2)),
    ]
    findings = [f"激活率为{activation_rate:.1%}，激活后活跃使用率为{active_rate:.1%}。", f"平均使用次数为{depth:.2f}。"]
    drivers = ["需要区分未激活、激活后沉默和高频使用三类对象。", "使用深度与业绩的关系只能作为相关性线索，不能直接声称因果。"]
    charts = [
        funnel_chart(["可推广对象", "已激活", "活跃使用"], [eligible, activated, active_users], "Prysm IO 激活漏斗"),
        bar_chart(region.head(10), "region", "usage_count", "区域使用表现排行"),
        scatter_chart(scatter, "usage_count", "sales_amount", "使用深度 vs 业绩") if "sales_amount" in scatter else {"title": "使用深度 vs 业绩", "html": "<p>缺少业绩字段。</p>"},
    ]
    summary = f"Prysm IO 当前激活率为{activation_rate:.1%}，激活后活跃使用率为{active_rate:.1%}。下一步应重点处理激活后沉默用户，并验证高使用深度经销商是否具备可复制业务动作。"
    return _make_result("prysm_io_adoption", kb, question, validation, summary, metrics, findings, drivers, charts, {"低活跃经销商": usage[_num(usage, "usage_count") <= 0].head(50)})


def _run_community(context, mappings, question, kb, validation) -> AnalysisResult:
    participants = _mapped_sheet(context, mappings, "community_participant")
    monthly = _mapped_sheet(context, mappings, "distributor_monthly")
    if not _has_columns(participants, ["distributor_id", "treatment_flag"]):
        metrics = [
            MetricValue("participant_count", "参与人数", 0),
            MetricValue("treatment_change", "实验组平均变化", 0),
            MetricValue("control_change", "对照组平均变化", 0),
            MetricValue("did_uplift", "DID净增量", 0),
        ]
        findings = ["缺少参与者经销商ID或实验组字段，无法计算实验组/对照组差异。"]
        drivers = ["可以继续输出项目复盘框架，但不能声称陪跑带来了真实增量。"]
        charts = [{"title": "实验组/对照组前后变化", "html": "<p>缺少参与者关键字段，无法生成对比图。</p>"}]
        summary = "当前数据不足以评估社群陪跑的真实增量。建议补充参与者名单、实验组标识、对照组标识和经销商月度业绩后再运行完整分析。"
        return _make_result("community_operation_evaluation", kb, question, validation, summary, metrics, findings, drivers, charts)
    if not _has_columns(monthly, ["month", "distributor_id", "sales_amount"]):
        participant_count = int((_num(participants, "treatment_flag") > 0).sum())
        metrics = [
            MetricValue("participant_count", "参与人数", participant_count),
            MetricValue("treatment_change", "实验组平均变化", 0),
            MetricValue("control_change", "对照组平均变化", 0),
            MetricValue("did_uplift", "DID净增量", 0),
        ]
        findings = ["缺少经销商月度业绩中的 distributor_id、month 或 sales_amount，无法计算前后变化和 DID。"]
        drivers = [
            "当前只能确认参与者结构，不能判断社群陪跑是否带来真实业绩提升。",
            "需要补充可按 distributor_id 关联的月度业绩表，至少包含陪跑前后两个周期。",
        ]
        charts = [{"title": "实验组/对照组前后变化", "html": "<p>缺少可关联的经销商月度业绩，无法生成 DID 图。</p>"}]
        summary = "当前数据可以识别社群参与名单，但缺少可按经销商关联的月度业绩，因此不能计算前后变化和 DID 净增量。建议先补齐经销商ID、月份和销售额字段。"
        return _make_result("community_operation_evaluation", kb, question, validation, summary, metrics, findings, drivers, charts, {"参与者名单": participants.head(50)})
    latest, previous = _latest_previous(monthly)
    before = monthly[monthly["month"].astype(str) == previous] if previous else monthly.head(0)
    after = monthly[monthly["month"].astype(str) == latest] if latest else monthly
    before_sales = before.groupby("distributor_id", as_index=False)["sales_amount"].sum().rename(columns={"sales_amount": "before_sales"})
    after_sales = after.groupby("distributor_id", as_index=False)["sales_amount"].sum().rename(columns={"sales_amount": "after_sales"})
    base = participants.merge(before_sales, on="distributor_id", how="left").merge(after_sales, on="distributor_id", how="left").fillna(0)
    base["sales_change"] = base["after_sales"] - base["before_sales"]
    treatment_change = float(base.loc[_num(base, "treatment_flag") > 0, "sales_change"].mean() or 0)
    control_flag = "control_group_flag" if "control_group_flag" in base else "treatment_flag"
    control_change = float(base.loc[_num(base, control_flag) <= 0, "sales_change"].mean() or 0)
    did = treatment_change - control_change
    level = base.groupby("participation_level", as_index=False)["sales_change"].mean() if "participation_level" in base else pd.DataFrame()
    metrics = [
        MetricValue("participant_count", "参与人数", int((_num(participants, "treatment_flag") > 0).sum())),
        MetricValue("treatment_change", "实验组平均变化", round(treatment_change, 2)),
        MetricValue("control_change", "对照组平均变化", round(control_change, 2)),
        MetricValue("did_uplift", "DID净增量", round(did, 2)),
    ]
    findings = [f"实验组平均销售变化为{treatment_change:,.2f}，对照组为{control_change:,.2f}，DID净增量为{did:,.2f}。"]
    drivers = ["陪跑效果必须比较实验组和对照组，不能只看参与者前后增长。", "若只有高参与度人群有效，应优化任务机制和参与激励。"]
    charts = [
        bar_chart(pd.DataFrame({"group": ["实验组", "对照组"], "sales_change": [treatment_change, control_change]}), "group", "sales_change", "实验组/对照组前后变化"),
        bar_chart(level, "participation_level", "sales_change", "参与强度分层表现") if not level.empty else {"title": "参与强度分层表现", "html": "<p>缺少参与强度字段。</p>"},
    ]
    summary = f"社群陪跑的 DID 净增量为{did:,.2f}。若样本匹配质量可靠且 DID 为正，可考虑扩大；否则不应仅凭实验组增长判断项目有效。"
    return _make_result("community_operation_evaluation", kb, question, validation, summary, metrics, findings, drivers, charts, {"参与者效果明细": base.head(50)})


def _association_rules(orders: pd.DataFrame) -> pd.DataFrame:
    if orders.empty or "order_id" not in orders or "product_id" not in orders:
        return pd.DataFrame(columns=["product_a", "product_b", "support", "confidence", "lift"])
    baskets = orders.groupby("order_id")["product_id"].apply(lambda items: sorted(set(items.dropna().astype(str))))
    total_orders = max(len(baskets), 1)
    product_orders = {}
    pair_orders = {}
    for basket in baskets:
        for item in basket:
            product_orders[item] = product_orders.get(item, 0) + 1
        for a, b in combinations(basket, 2):
            pair_orders[(a, b)] = pair_orders.get((a, b), 0) + 1
    rows = []
    for (a, b), count in pair_orders.items():
        support = count / total_orders
        confidence = count / product_orders.get(a, 1)
        b_share = product_orders.get(b, 0) / total_orders
        rows.append({"product_a": a, "product_b": b, "support": support, "confidence": confidence, "lift": _safe_div(confidence, b_share)})
    return pd.DataFrame(rows).sort_values(["lift", "confidence"], ascending=False) if rows else pd.DataFrame(columns=["product_a", "product_b", "support", "confidence", "lift"])


def _run_product(context, mappings, question, kb, validation) -> AnalysisResult:
    product_sales = _mapped_sheet(context, mappings, "product_sales")
    orders = _mapped_sheet(context, mappings, "sales_order")
    total_sales = float(_num(product_sales, "sales_amount").sum())
    category = product_sales.groupby("product_category", as_index=False)["sales_amount"].sum().sort_values("sales_amount", ascending=False)
    trend = product_sales.groupby("month", as_index=False)["sales_amount"].sum() if "month" in product_sales else pd.DataFrame()
    region = product_sales.groupby("region", as_index=False)["sales_amount"].sum().sort_values("sales_amount", ascending=False) if "region" in product_sales else pd.DataFrame()
    rules = _association_rules(orders)
    best_lift = float(rules["lift"].max()) if not rules.empty else 0
    metrics = [
        MetricValue("sales_amount", "产品销售额", round(total_sales, 2)),
        MetricValue("category_count", "覆盖品类数", int(category["product_category"].nunique()) if not category.empty else 0),
        MetricValue("best_bundle_lift", "最高组合lift", round(best_lift, 2)),
    ]
    findings = [f"产品销售额合计为{total_sales:,.0f}。", f"最高组合 lift 为{best_lift:.2f}，可作为套装机会线索。"]
    drivers = ["产品增长需要同时判断总销售增量、品类占比和是否蚕食高毛利产品。", "高销量组合不等于高关联价值，lift 更适合识别组合推荐机会。"]
    charts = [
        trend_chart(trend, "month", "sales_amount", "产品销售趋势"),
        pie_chart(category.head(8), "product_category", "sales_amount", "品类占比"),
        bar_chart(region.head(10), "region", "sales_amount", "区域产品表现排行") if not region.empty else {"title": "区域产品表现排行", "html": "<p>缺少区域字段。</p>"},
    ]
    summary = f"产品及活动评估显示，产品销售额合计{total_sales:,.0f}，最高组合 lift 为{best_lift:.2f}。建议优先选择销售增长、毛利健康且具备组合关联价值的产品做推广。"
    return _make_result("product_campaign_evaluation", kb, question, validation, summary, metrics, findings, drivers, charts, {"组合关联规则": rules.head(50)})


def _run_generic(context, mappings, question, kb, validation) -> AnalysisResult:
    sheet_rows = []
    field_rows = []
    charts = []
    appendix_tables = {}
    total_rows = 0
    total_columns = 0

    for sheet_name, original_df in context.sheets.items():
        df = original_df.copy()
        total_rows += int(df.shape[0])
        total_columns += int(df.shape[1])
        missing_rate = float(df.isna().sum().sum()) / max(int(df.shape[0] * df.shape[1]), 1)
        numeric_cols = df.select_dtypes(include="number").columns.astype(str).tolist()
        text_cols = [str(col) for col in df.columns if str(col) not in numeric_cols]
        sheet_rows.append(
            {
                "sheet": sheet_name,
                "rows": int(df.shape[0]),
                "columns": int(df.shape[1]),
                "missing_rate": round(missing_rate, 4),
                "numeric_columns": ", ".join(numeric_cols),
                "text_columns": ", ".join(text_cols[:8]),
            }
        )
        for column in df.columns:
            series = df[column]
            field_rows.append(
                {
                    "sheet": sheet_name,
                    "field": str(column),
                    "dtype": str(series.dtype),
                    "missing_rate": round(float(series.isna().mean()), 4),
                    "unique_count": int(series.nunique(dropna=True)),
                    "sample_values": ", ".join(series.dropna().astype(str).head(3).tolist()),
                }
            )
        if numeric_cols:
            numeric_summary = df[numeric_cols].describe().transpose().reset_index().rename(columns={"index": "field"})
            appendix_tables[f"{sheet_name} 数值字段摘要"] = numeric_summary
        categorical_cols = [col for col in df.columns if str(col) not in numeric_cols]
        if categorical_cols:
            top_col = categorical_cols[0]
            top_values = df[top_col].astype(str).value_counts().head(10).reset_index()
            top_values.columns = [str(top_col), "count"]
            charts.append(bar_chart(top_values, str(top_col), "count", f"{sheet_name} - {top_col} Top 值"))

    sheet_summary = pd.DataFrame(sheet_rows)
    field_summary = pd.DataFrame(field_rows)
    if not sheet_summary.empty:
        charts.insert(0, bar_chart(sheet_summary, "sheet", "rows", "Sheet 行数对比"))

    avg_missing = float(sheet_summary["missing_rate"].mean()) if "missing_rate" in sheet_summary else 0
    numeric_field_count = sum(1 for row in field_rows if row["dtype"].startswith(("int", "float")))
    metrics = [
        MetricValue("sheet_count", "Sheet 数量", len(context.sheets)),
        MetricValue("row_count", "总行数", total_rows),
        MetricValue("column_count", "总字段数", total_columns),
        MetricValue("avg_missing_rate", "平均缺失率", f"{avg_missing:.1%}"),
        MetricValue("numeric_field_count", "数值字段数", numeric_field_count),
    ]
    findings = [
        f"本次上传包含 {len(context.sheets)} 个 Sheet、{total_rows} 行、{total_columns} 个字段。",
        f"平均缺失率约为 {avg_missing:.1%}，可优先检查缺失率较高的字段。",
        "该数据未匹配到五个专业业务专题的必要结构，因此已切换为通用数据分析。",
    ]
    if not field_summary.empty:
        high_missing = field_summary.sort_values("missing_rate", ascending=False).head(3)
        missing_names = [f"{row['sheet']}.{row['field']}({row['missing_rate']:.1%})" for _, row in high_missing.iterrows()]
        findings.append("缺失率最高字段：" + "、".join(missing_names))

    drivers = [
        "通用分析先回答：有哪些表、有哪些字段、哪些字段可作为指标、哪些字段可作为分组维度。",
        "如果要进入专业 Skill，需要补充对应专题的关键字段，例如经销商ID、订单日期、销售额、订阅状态或活动ID。",
        "对品牌、门店、品类、定位这类资料型表，更适合先做描述性统计、分组对比和信息完整性检查。",
    ]
    summary = (
        f"这是一次通用数据分析，而不是五个专业专题分析。数据包含 {len(context.sheets)} 个 Sheet、"
        f"{total_rows} 行、{total_columns} 个字段；系统会输出数据结构、质量、字段分布和后续可追问方向。"
    )
    appendix_tables["Sheet 概览"] = sheet_summary
    appendix_tables["字段画像"] = field_summary
    return _make_result("generic_data_analysis", kb, question, validation, summary, metrics, findings, drivers, charts, appendix_tables)


RUNNERS: dict[str, Callable] = {
    "generic_data_analysis": _run_generic,
    "distributor_performance_fluctuation": _run_distributor,
    "subscription_insight": _run_subscription,
    "prysm_io_adoption": _run_prysm,
    "community_operation_evaluation": _run_community,
    "product_campaign_evaluation": _run_product,
}


def run_skill(
    skill_id: str,
    context: WorkbookContext,
    mappings: dict[str, FieldMappingResult],
    question: str,
    kb: KnowledgeBase,
) -> AnalysisResult:
    if skill_id not in RUNNERS:
        raise ValueError(f"Unsupported skill_id: {skill_id}")
    validation = validate_skill_inputs(skill_id, context, mappings, kb.sheet_schema_catalog, kb.skills)
    result = RUNNERS[skill_id](context, mappings, question, kb, validation)
    if not result.required_sections_complete():
        raise ValueError("Analysis result is missing required decision sections.")
    return result
