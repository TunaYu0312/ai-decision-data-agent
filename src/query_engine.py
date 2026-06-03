from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import re

import pandas as pd
import plotly.express as px

from .models import WorkbookContext
from .visualization_builder import chart_to_html


@dataclass
class QueryAnswer:
    question: str
    answer: str
    evidence: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    tables: list[pd.DataFrame] = field(default_factory=list)
    charts: list[dict[str, str]] = field(default_factory=list)
    llm_used: bool = False
    llm_provider: str | None = None


def _normalize(value: Any) -> str:
    return str(value).strip().lower()


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized = {str(col): _normalize(col) for col in df.columns}
    for col, name in normalized.items():
        if any(_normalize(candidate) in name for candidate in candidates):
            return col
    return None


def _find_columns(df: pd.DataFrame, candidates: list[str]) -> list[str]:
    matches = []
    for col in df.columns:
        name = _normalize(col)
        if any(_normalize(candidate) in name for candidate in candidates):
            matches.append(col)
    return matches


def _to_number(value: Any) -> float | None:
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").strip()
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0))
    if "万" in text:
        number *= 10000
    return number


def _numeric_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.apply(_to_number), errors="coerce")


def _is_numeric_metric_column(col: Any) -> bool:
    name = _normalize(col)
    blocked = [
        "id",
        "code",
        "hash",
        "name",
        "名称",
        "编号",
        "编码",
        "日期",
        "date",
        "month",
        "月份",
        "状态",
        "status",
        "品类",
        "category",
        "类型",
        "type",
    ]
    return not any(token in name for token in blocked)


def _numeric_metric_columns(df: pd.DataFrame) -> list[str]:
    return [
        col
        for col in df.columns
        if _is_numeric_metric_column(col) and _numeric_series(df[col]).notna().sum() >= max(2, len(df) * 0.4)
    ]


def _time_column(df: pd.DataFrame) -> str | None:
    return _find_column(df, ["month", "月份", "月", "date", "日期", "时间", "year", "年度"])


def _best_numeric_column(df: pd.DataFrame, preferred: list[str] | None = None) -> str | None:
    preferred = preferred or ["sales_amount", "销售额", "revenue", "收入", "amount", "金额", "门店数", "数量", "订单数"]
    preferred_col = _find_column(df, preferred)
    if preferred_col and _numeric_series(df[preferred_col]).notna().sum() >= 2:
        return preferred_col
    columns = _numeric_metric_columns(df)
    if columns:
        return columns[0]
    return None


def _build_auto_charts(
    df: pd.DataFrame,
    entity_col: str | None = None,
    category_col: str | None = None,
    preferred_numeric_col: str | None = None,
) -> list[dict[str, str]]:
    charts: list[dict[str, str]] = []
    if df.empty:
        return charts

    numeric_col = preferred_numeric_col if preferred_numeric_col in df.columns else _best_numeric_column(df)
    time_col = _time_column(df)

    if time_col and numeric_col:
        trend = df[[time_col, numeric_col] + ([category_col] if category_col else [])].copy()
        trend["_metric"] = _numeric_series(trend[numeric_col])
        trend = trend.dropna(subset=["_metric"])
        if not trend.empty and trend[time_col].nunique() >= 2:
            group_cols = [time_col]
            color = None
            if category_col and trend[category_col].nunique() <= 8:
                group_cols.append(category_col)
                color = category_col
            trend = trend.groupby(group_cols, as_index=False)["_metric"].sum()
            fig = px.line(
                trend,
                x=time_col,
                y="_metric",
                color=color,
                markers=True,
                title=f"{numeric_col} 趋势",
                labels={"_metric": numeric_col},
            )
            charts.append({"title": f"{numeric_col} 趋势", "html": chart_to_html(fig)})

    if category_col:
        category = df[[category_col] + ([numeric_col] if numeric_col else [])].copy()
        if numeric_col:
            category["_metric"] = _numeric_series(category[numeric_col])
            category = category.dropna(subset=["_metric"]).groupby(category_col, as_index=False)["_metric"].sum()
            category = category.sort_values("_metric", ascending=False).head(10)
            y_value = "_metric"
            y_label = numeric_col
            title = f"{category_col} 贡献排行"
        else:
            category = category[category_col].fillna("未填写").astype(str).value_counts().head(10).reset_index()
            category.columns = [category_col, "记录数"]
            y_value = "记录数"
            y_label = "记录数"
            title = f"{category_col} 分布"
        if not category.empty:
            fig = px.bar(category, x=category_col, y=y_value, title=title, labels={y_value: y_label})
            charts.append({"title": title, "html": chart_to_html(fig)})

    if entity_col and numeric_col:
        ranked = df[[entity_col, numeric_col]].copy()
        ranked["_metric"] = _numeric_series(ranked[numeric_col])
        ranked = ranked.dropna(subset=["_metric"]).groupby(entity_col, as_index=False)["_metric"].sum()
        ranked = ranked.sort_values("_metric", ascending=False).head(10)
        if not ranked.empty:
            fig = px.bar(
                ranked.sort_values("_metric"),
                x="_metric",
                y=entity_col,
                orientation="h",
                title=f"Top 10 {entity_col} - {numeric_col}",
                labels={"_metric": numeric_col},
            )
            charts.append({"title": f"Top 10 {entity_col} - {numeric_col}", "html": chart_to_html(fig)})

    numeric_cols = _numeric_metric_columns(df)
    if len(numeric_cols) >= 2 and entity_col:
        plot_df = df[[entity_col, numeric_cols[0], numeric_cols[1]] + ([category_col] if category_col else [])].copy()
        plot_df["_x"] = _numeric_series(plot_df[numeric_cols[0]])
        plot_df["_y"] = _numeric_series(plot_df[numeric_cols[1]])
        plot_df = plot_df.dropna(subset=["_x", "_y"])
        if len(plot_df) >= 3:
            fig = px.scatter(
                plot_df,
                x="_x",
                y="_y",
                color=category_col if category_col and category_col in plot_df else None,
                hover_name=entity_col,
                title=f"{numeric_cols[0]} vs {numeric_cols[1]}",
                labels={"_x": numeric_cols[0], "_y": numeric_cols[1]},
            )
            charts.append({"title": f"{numeric_cols[0]} vs {numeric_cols[1]}", "html": chart_to_html(fig)})

    return charts[:4]


def _first_non_empty_sheet(context: WorkbookContext) -> tuple[str, pd.DataFrame]:
    for sheet_name, df in context.sheets.items():
        if not df.empty:
            return sheet_name, df.copy()
    return "", pd.DataFrame()


def _truthy_listed(value: Any) -> bool:
    text = str(value).strip().lower()
    return text in {"是", "已上市", "上市", "yes", "y", "true", "1", "listed"} or "上市" in text and "未" not in text and "否" not in text


def _score_health(df: pd.DataFrame) -> QueryAnswer:
    brand_col = _find_column(df, ["品牌名称", "品牌", "中文名称", "name"])
    store_col = _find_column(df, ["门店数", "店数", "门店", "stores"])
    status_col = _find_column(df, ["最新现状", "现状", "状态", "status"])
    strategy_col = _find_column(df, ["当前主要策略", "策略", "下一步的策略", "strategy"])
    challenge_col = _find_column(df, ["面临的挑战", "挑战", "风险", "问题"])
    confidence_col = _find_column(df, ["可信度", "置信度", "confidence"])

    if not brand_col:
        return QueryAnswer(
            question="",
            answer="无法回答“哪些品牌发展健康”，因为表中没有识别到品牌名称字段。",
            limitations=["缺少品牌名称字段。"],
        )

    work = df.copy()
    work["_brand"] = work[brand_col].astype(str)
    work["_score"] = 0.0
    work["_reason"] = ""

    if store_col:
        stores = work[store_col].apply(_to_number)
        stores = pd.to_numeric(stores, errors="coerce")
        max_store = float(stores.max()) if stores.notna().any() else 0
        if max_store:
            work["_score"] += stores.fillna(0) / max_store * 45
            work["_reason"] += "门店规模较大；"

    positive_terms = ["增长", "扩张", "稳定", "领先", "盈利", "恢复", "升级", "高"]
    negative_terms = ["下滑", "收缩", "关闭", "亏损", "放缓", "压力", "挑战", "竞争加剧"]
    for col in [status_col, strategy_col]:
        if col:
            text = work[col].fillna("").astype(str)
            work["_score"] += text.apply(lambda item: 18 if any(term in item for term in positive_terms) else 0)
            work["_reason"] += text.apply(lambda item: "现状/策略有积极信号；" if any(term in item for term in positive_terms) else "")
    if challenge_col:
        text = work[challenge_col].fillna("").astype(str)
        work["_score"] -= text.apply(lambda item: 15 if any(term in item for term in negative_terms) else 0)
        work["_reason"] += text.apply(lambda item: "存在挑战需关注；" if any(term in item for term in negative_terms) else "")
    if confidence_col:
        text = work[confidence_col].fillna("").astype(str)
        work["_score"] += text.apply(lambda item: 12 if "高" in item or item.lower() == "high" else 0)
        work["_reason"] += text.apply(lambda item: "信息可信度高；" if "高" in item or item.lower() == "high" else "")

    result_cols = ["_brand", "_score", "_reason"]
    for col in [store_col, status_col, strategy_col, challenge_col, confidence_col]:
        if col and col not in result_cols:
            result_cols.append(col)
    ranked = (
        work.sort_values("_score", ascending=False)[result_cols]
        .rename(columns={"_brand": "brand", "_score": "health_score", "_reason": "reason"})
        .head(8)
    )
    brands = ranked["brand"].head(5).tolist()
    answer = "基于表内字段的本地评分，发展相对健康的品牌包括：" + "、".join(brands) + "。"
    evidence = ["评分依据包括门店规模、最新现状/策略中的积极信号、挑战描述和可信度。"]
    limitations = ["这是基于上传表内字段的启发式评分，不等同于财务尽调或真实经营健康度结论。"]
    charts = _build_auto_charts(work, entity_col="_brand", category_col=None, preferred_numeric_col="_score")
    return QueryAnswer("", answer, evidence, limitations, [ranked], charts=charts)


def _answer_stock_growth(df: pd.DataFrame) -> QueryAnswer:
    brand_col = _find_column(df, ["品牌名称", "品牌", "中文名称", "name"])
    listed_col = _find_column(df, ["是否上市", "上市", "listed"])
    stock_cols = [
        col
        for col in df.columns
        if any(token in str(col).lower() for token in ["股票", "股价", "涨幅", "增长率", "stock", "share"])
    ]

    if not listed_col:
        return QueryAnswer(
            "",
            "无法判断上市品牌的股票增长情况，因为表中没有识别到“是否上市”字段。",
            limitations=["缺少是否上市字段。"],
        )

    listed = df[df[listed_col].apply(_truthy_listed)].copy()
    display_cols = [col for col in [brand_col, listed_col] if col]
    if stock_cols:
        display_cols.extend(stock_cols)
        sortable = stock_cols[0]
        listed["_stock_value"] = pd.to_numeric(listed[sortable], errors="coerce")
        ranked = listed.sort_values("_stock_value", ascending=False)[display_cols].head(10)
        brands = ranked[brand_col].astype(str).head(5).tolist() if brand_col else []
        return QueryAnswer(
            "",
            "基于表内股票相关字段，表现较顺利的上市品牌包括：" + "、".join(brands) + "。",
            evidence=[f"使用字段 {sortable} 进行排序。"],
            limitations=["未接入实时行情；仅基于上传表内数据判断。"],
            tables=[ranked],
            charts=_build_auto_charts(ranked, entity_col=brand_col, preferred_numeric_col=sortable),
        )

    table = listed[display_cols].head(20) if display_cols else listed.head(20)
    brand_text = "、".join(table[brand_col].astype(str).tolist()) if brand_col and not table.empty else "表内未列出品牌名称"
    return QueryAnswer(
        "",
        f"表内可识别的上市品牌包括：{brand_text}。但无法判断股票增长是否顺利，因为上传数据只有上市状态，没有股价、涨幅或股票增长字段。",
        evidence=["已根据“是否上市”字段筛选上市品牌。"],
        limitations=["缺少股票价格、阶段涨幅、股价增长率或行情日期字段；不能编造股票表现。"],
        tables=[table],
        charts=[],
    )


def _generic_profile_answer(context: WorkbookContext, question: str) -> QueryAnswer:
    sheet_rows = []
    for sheet_name, df in context.sheets.items():
        sheet_rows.append(
            {
                "sheet": sheet_name,
                "rows": int(df.shape[0]),
                "columns": int(df.shape[1]),
                "fields": ", ".join(map(str, df.columns[:12])),
            }
        )
    table = pd.DataFrame(sheet_rows)
    sheet_name, df = _first_non_empty_sheet(context)
    if df.empty:
        return QueryAnswer(question, "上传的数据为空，无法生成洞察报告。", limitations=["没有可分析的数据行。"], tables=[table])

    entity_col = _find_column(df, ["品牌名称", "品牌", "中文名称", "公司", "门店", "产品名称", "name"])
    category_col = _find_column(df, ["品类类别", "品类", "类别", "行业", "category", "type"])
    store_col = _find_column(df, ["门店数", "店数", "门店", "stores"])
    listed_col = _find_column(df, ["是否上市", "上市", "listed"])
    status_col = _find_column(df, ["最新现状", "现状", "状态", "status"])
    strategy_col = _find_column(df, ["当前主要策略", "下一步的策略", "策略", "strategy"])
    challenge_col = _find_column(df, ["面临的挑战", "挑战", "风险", "问题"])
    confidence_col = _find_column(df, ["可信度", "置信度", "confidence"])
    numeric_cols = _numeric_metric_columns(df)

    findings: list[str] = []
    action_items: list[str] = []
    output_tables = [table]

    if entity_col:
        findings.append(f"**分析对象**：主表 `{sheet_name}` 共有 **{len(df)}** 条记录，核心对象字段是 `{entity_col}`。")
    else:
        findings.append(f"**数据范围**：主表 `{sheet_name}` 共有 **{len(df)}** 条记录、**{len(df.columns)}** 个字段。")

    if category_col:
        category_counts = df[category_col].fillna("未填写").astype(str).value_counts().head(8).reset_index()
        category_counts.columns = [category_col, "记录数"]
        output_tables.append(category_counts)
        top_category = category_counts.iloc[0][category_col] if not category_counts.empty else None
        findings.append(f"**结构分布**：`{category_col}` 中占比最高的是 **{top_category}**，说明样本更偏向该类对象。")

    if listed_col:
        listed_count = int(df[listed_col].apply(_truthy_listed).sum())
        findings.append(f"**资本市场状态**：表内可识别上市对象 **{listed_count}** 个，未上市或未明确上市对象 **{len(df) - listed_count}** 个。")

    if store_col and entity_col:
        stores = _numeric_series(df[store_col])
        ranked = df[[entity_col, store_col]].copy()
        ranked["_parsed_store_count"] = stores
        ranked = ranked.sort_values("_parsed_store_count", ascending=False).head(10)
        ranked = ranked.rename(columns={entity_col: "对象", store_col: "门店数"})
        output_tables.append(ranked)
        top_entities = "、".join(ranked["对象"].astype(str).head(5).tolist())
        median_store = stores.dropna().median()
        findings.append(f"**规模领先者**：按 `{store_col}` 解析后的门店规模看，头部对象包括 **{top_entities}**。")
        if pd.notna(median_store):
            findings.append(f"**规模分层**：样本门店数中位数约为 **{median_store:,.0f}**，可把高于中位数的对象作为第一批重点研究样本。")

    signal_terms = {
        "积极信号": ["增长", "扩张", "稳定", "领先", "盈利", "恢复", "升级", "高", "创新", "下沉"],
        "风险信号": ["下滑", "收缩", "关闭", "亏损", "放缓", "压力", "挑战", "竞争", "成本"],
    }
    text_cols = [col for col in [status_col, strategy_col, challenge_col] if col]
    if text_cols:
        signal_rows = []
        for col in text_cols:
            text = df[col].fillna("").astype(str)
            positive = int(text.apply(lambda item: any(term in item for term in signal_terms["积极信号"])).sum())
            risk = int(text.apply(lambda item: any(term in item for term in signal_terms["风险信号"])).sum())
            signal_rows.append({"字段": col, "积极信号记录数": positive, "风险信号记录数": risk})
        signal_table = pd.DataFrame(signal_rows)
        output_tables.append(signal_table)
        findings.append("**文本信号**：现状、策略和挑战字段里同时存在增长/扩张等机会信号，也存在竞争、成本、收缩等风险信号，需要分层判断。")

    if confidence_col:
        high_confidence = int(df[confidence_col].fillna("").astype(str).str.contains("高|high", case=False, regex=True).sum())
        findings.append(f"**信息质量**：`{confidence_col}` 显示高可信记录 **{high_confidence}** 条，其余记录建议在正式决策前复核来源。")

    for col in numeric_cols[:4]:
        values = _numeric_series(df[col]).dropna()
        if values.empty:
            continue
        findings.append(f"**数值字段 `{col}`**：最大值 **{values.max():,.0f}**，中位数 **{values.median():,.0f}**，可用于后续排序和分层。")

    if entity_col and store_col:
        action_items.append("把门店规模靠前、且现状/策略为积极信号的对象列为第一组标杆样本。")
        action_items.append("把门店规模较大但挑战字段风险较多的对象列为风险复核样本，重点看增长质量。")
    if category_col:
        action_items.append(f"按 `{category_col}` 分组补充市场容量、增速、客单价或利润率，避免只用样本数量判断行业机会。")
    action_items.append("如果要输出正式行业报告，下一步需要补充外部行业规模、增速、融资/上市表现或财务指标；当前报告只基于上传表内数据。")

    answer = (
        "## 直接结论\n"
        + "\n".join(f"- {item}" for item in findings[:5])
        + "\n\n## 建议与下一步\n"
        + "\n".join(f"- {item}" for item in action_items)
    )
    evidence = [
        f"主要分析 Sheet：{sheet_name}。",
        "已基于字段名称自动识别对象、品类、门店规模、上市状态、现状、策略、挑战和可信度等可用信息。",
    ]
    limitations = [
        "这是基于上传表内字段的通用洞察，不等同于完整行业研究。",
        "如果问题要求行业规模、实时股价、融资、财务表现或外部市场份额，需要补充外部数据源。",
    ]
    charts = _build_auto_charts(
        df,
        entity_col=entity_col,
        category_col=category_col,
        preferred_numeric_col=store_col or _best_numeric_column(df),
    )
    return QueryAnswer(
        question,
        answer,
        evidence=evidence,
        limitations=limitations,
        tables=output_tables,
        charts=charts,
    )


def query_workbook(context: WorkbookContext, question: str) -> QueryAnswer:
    sheet_name, df = _first_non_empty_sheet(context)
    if df.empty:
        return QueryAnswer(question, "上传的数据为空，无法查询。", limitations=["没有可分析的数据行。"])

    normalized_question = _normalize(question)
    if any(term in normalized_question for term in ["股票", "股价", "上市", "stock", "share"]):
        answer = _answer_stock_growth(df)
    elif any(term in normalized_question for term in ["健康", "发展", "较好", "顺利", "潜力"]):
        answer = _score_health(df)
    else:
        answer = _generic_profile_answer(context, question)
    answer.question = question
    if sheet_name:
        answer.evidence.insert(0, f"主要分析 Sheet：{sheet_name}。")
    return answer
