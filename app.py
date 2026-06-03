from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src.auto_agent import auto_select_skill, infer_sheet_roles, prepare_context_for_skill
from src.data_loader import load_workbook
from src.data_profiler import profile_workbook
from src.field_mapper import suggest_field_mapping, validate_skill_inputs
from src.intent_router import route_question
from src.knowledge_loader import KnowledgeBase
from src.local_settings import save_local_env, load_local_env
from src.llm_client import LLMConfig, PROVIDER_PRESETS, enhance_query_with_llm
from src.query_engine import query_workbook
from src.query_report_builder import build_query_html_report
from src.report_builder import build_html_report, build_markdown_report
from src.skill_engine import run_skill
from src.ui_components import action_plan_to_frame, mapping_to_frame, profile_to_frame, validation_to_frame
from src.web_search import WebSearchConfig, search_web


PROJECT_ROOT = Path(__file__).resolve().parent
SAMPLE_DIR = PROJECT_ROOT / "data_samples"


@st.cache_resource
def load_kb() -> KnowledgeBase:
    return KnowledgeBase.load_default(PROJECT_ROOT)


def init_state() -> None:
    local_env = load_local_env(PROJECT_ROOT)
    def config_value(key: str, default: str = "") -> str:
        if key in os.environ:
            return os.environ[key]
        try:
            if key in st.secrets:
                return str(st.secrets[key])
        except Exception:
            pass
        return local_env.get(key) or default

    saved_provider = config_value("LLM_PROVIDER", "DeepSeek")
    saved_base_url = config_value("LLM_BASE_URL", PROVIDER_PRESETS["DeepSeek"]["base_url"])
    saved_model = config_value("LLM_MODEL", PROVIDER_PRESETS["DeepSeek"]["model"])
    saved_api_key = config_value("LLM_API_KEY")
    saved_enabled = config_value("LLM_ENABLED").lower() in {"1", "true", "yes", "y"} or bool(saved_api_key)
    saved_web_enabled = config_value("WEB_SEARCH_ENABLED").lower() in {"1", "true", "yes", "y"}
    defaults = {
        "workbook_context": None,
        "data_profile": None,
        "field_mappings": {},
        "sheet_roles": {},
        "skill_selection": None,
        "selected_skill_id": None,
        "prepared_context": None,
        "prepared_mappings": {},
        "analysis_result": None,
        "html_report_path": None,
        "markdown_report_path": None,
        "query_history": [],
        "llm_provider": saved_provider,
        "llm_base_url": saved_base_url,
        "llm_model": saved_model,
        "llm_api_key": saved_api_key,
        "llm_enabled": saved_enabled,
        "web_search_enabled": saved_web_enabled,
        "web_search_provider": config_value("WEB_SEARCH_PROVIDER", "DuckDuckGo"),
        "web_search_api_key": config_value("WEB_SEARCH_API_KEY"),
        "query_running": False,
        "query_status": "idle",
        "query_last_question": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def persist_llm_settings() -> Path:
    return save_local_env(
        PROJECT_ROOT,
        {
            "LLM_PROVIDER": st.session_state.llm_provider,
            "LLM_BASE_URL": st.session_state.llm_base_url,
            "LLM_MODEL": st.session_state.llm_model,
            "LLM_API_KEY": st.session_state.llm_api_key,
            "LLM_ENABLED": "true" if st.session_state.llm_enabled else "false",
            "WEB_SEARCH_ENABLED": "true" if st.session_state.web_search_enabled else "false",
            "WEB_SEARCH_PROVIDER": st.session_state.web_search_provider,
            "WEB_SEARCH_API_KEY": st.session_state.web_search_api_key,
        },
    )


def current_web_search_config() -> WebSearchConfig:
    return WebSearchConfig(
        enabled=st.session_state.web_search_enabled,
        provider=st.session_state.web_search_provider,
        api_key=st.session_state.web_search_api_key,
        max_results=5,
    )


def load_context(file_or_path, kb: KnowledgeBase) -> None:
    context = load_workbook(file_or_path)
    mappings = {
        sheet: suggest_field_mapping(sheet, df.columns.astype(str).tolist(), kb.field_aliases)
        for sheet, df in context.sheets.items()
    }
    roles = infer_sheet_roles(context, mappings, kb.sheet_schema_catalog)
    selection = auto_select_skill(roles, mappings, kb.skills, kb.sheet_schema_catalog)
    prepared_context, prepared_mappings = prepare_context_for_skill(context, mappings, roles, selection.skill_id)
    st.session_state.workbook_context = context
    st.session_state.data_profile = profile_workbook(context)
    st.session_state.field_mappings = mappings
    st.session_state.sheet_roles = roles
    st.session_state.skill_selection = selection
    st.session_state.selected_skill_id = selection.skill_id
    st.session_state.prepared_context = prepared_context
    st.session_state.prepared_mappings = prepared_mappings
    st.session_state.analysis_result = None
    st.session_state.html_report_path = None
    st.session_state.markdown_report_path = None
    st.session_state.query_history = []


def refresh_prepared_context(kb: KnowledgeBase) -> None:
    context = st.session_state.workbook_context
    if not context:
        return
    roles = infer_sheet_roles(context, st.session_state.field_mappings, kb.sheet_schema_catalog)
    selection = auto_select_skill(roles, st.session_state.field_mappings, kb.skills, kb.sheet_schema_catalog)
    selected_skill_id = st.session_state.selected_skill_id or selection.skill_id
    prepared_context, prepared_mappings = prepare_context_for_skill(context, st.session_state.field_mappings, roles, selected_skill_id)
    st.session_state.sheet_roles = roles
    st.session_state.skill_selection = selection
    st.session_state.prepared_context = prepared_context
    st.session_state.prepared_mappings = prepared_mappings


def current_llm_config() -> LLMConfig:
    return LLMConfig(
        provider=st.session_state.llm_provider,
        api_key=st.session_state.llm_api_key,
        base_url=st.session_state.llm_base_url,
        model=st.session_state.llm_model,
        enabled=st.session_state.llm_enabled,
    )


def run_current_analysis(kb: KnowledgeBase, question: str) -> None:
    refresh_prepared_context(kb)
    result = run_skill(st.session_state.selected_skill_id, st.session_state.prepared_context, st.session_state.prepared_mappings, question, kb)
    st.session_state.analysis_result = result
    st.session_state.markdown_report_path = build_markdown_report(result, PROJECT_ROOT / "outputs" / "markdown")
    st.session_state.html_report_path = build_html_report(result, project_root=PROJECT_ROOT)


def answer_data_question(kb: KnowledgeBase, question: str) -> None:
    context = st.session_state.workbook_context
    if not context:
        st.warning("请先上传数据。")
        return
    route = route_question(question, st.session_state.selected_skill_id)
    if route.mode == "professional_skill":
        st.session_state.selected_skill_id = route.skill_id
        run_current_analysis(kb, question)
        result = st.session_state.analysis_result
        record = {
            "question": question,
            "mode": "专业分析",
            "answer": result.executive_summary,
            "evidence": [route.reason, result.data_availability_check],
            "limitations": result.risks_assumptions,
            "tables": [],
            "report_path": st.session_state.html_report_path,
            "llm_used": False,
            "llm_provider": None,
        }
    else:
        local_answer = query_workbook(context, question)
        final_answer = local_answer
        if st.session_state.llm_api_key:
            st.session_state.llm_enabled = True
            try:
                persist_llm_settings()
            except OSError as exc:
                st.warning(f"模型配置暂未保存到本地：{exc}")
        if st.session_state.llm_enabled:
            try:
                web_results = []
                if st.session_state.web_search_enabled:
                    try:
                        web_results = search_web(question, current_web_search_config())
                    except Exception as search_exc:
                        local_answer.limitations.append(f"联网检索失败，已继续使用表内数据和大模型分析：{search_exc}")
                final_answer = enhance_query_with_llm(
                    context,
                    question,
                    local_answer,
                    current_llm_config(),
                    web_results=web_results,
                )
            except Exception as exc:
                local_answer.limitations.append(f"大模型增强失败，已返回本地规则结果：{exc}")
                final_answer = local_answer
        report_path = build_query_html_report(final_answer, project_root=PROJECT_ROOT)
        record = {
            "question": question,
            "mode": "通用问数",
            "answer": final_answer.answer,
            "evidence": final_answer.evidence,
            "limitations": final_answer.limitations,
            "tables": final_answer.tables,
            "report_path": report_path,
            "llm_used": final_answer.llm_used,
            "llm_provider": final_answer.llm_provider,
        }
    st.session_state.query_history.append(record)


def sample_options() -> dict[str, Path]:
    return {path.name: path for path in sorted(SAMPLE_DIR.glob("*.xlsx"))}


def render_upload_area(kb: KnowledgeBase) -> None:
    st.subheader("1. 上传数据")
    uploaded = st.file_uploader("上传 Excel / CSV。系统会直接读取 Sheet、字段和样本数据。", type=["xlsx", "csv"])
    sample_files = sample_options()
    sample_name = st.selectbox("或使用内置虚拟 Excel 测试", [""] + list(sample_files.keys()))
    col1, col2 = st.columns([1, 1])
    with col1:
        if uploaded and st.button("读取上传文件", type="primary", use_container_width=True):
            load_context(uploaded, kb)
    with col2:
        if sample_name and st.button("读取样例数据", use_container_width=True):
            load_context(sample_files[sample_name], kb)


def render_data_overview(kb: KnowledgeBase) -> None:
    context = st.session_state.workbook_context
    if not context:
        return
    st.subheader("2. 数据概况")
    st.caption(f"数据包：{context.file_name}，共 {len(context.sheets)} 个 Sheet。")
    if st.session_state.data_profile:
        st.dataframe(profile_to_frame(st.session_state.data_profile), use_container_width=True)

    inferred = st.session_state.skill_selection
    skill_names = {skill_id: skill.get("name", skill_id) for skill_id, skill in kb.skills.items()}
    skill_ids = list(kb.skills.keys())
    if inferred and inferred.skill_id not in skill_ids:
        skill_ids.append(inferred.skill_id)
    default_index = skill_ids.index(inferred.skill_id) if inferred and inferred.skill_id in skill_ids else 0
    selected = st.selectbox(
        "系统推荐专题，可人工覆盖",
        skill_ids,
        index=default_index,
        format_func=lambda skill_id: skill_names.get(skill_id, skill_id),
    )
    st.session_state.selected_skill_id = selected
    if inferred:
        st.info(f"自动推荐：{skill_names.get(inferred.skill_id, inferred.skill_id)}。{inferred.reason} 缺少角色：{', '.join(inferred.missing_roles) or '无'}。")

    with st.expander("查看 Sheet 角色识别明细", expanded=False):
        role_rows = [
            {
                "Uploaded Sheet": item.uploaded_sheet,
                "Inferred Role": item.role,
                "Score": item.score,
                "Matched Fields": ", ".join(item.matched_fields),
                "Missing Required Fields": ", ".join(item.missing_required_fields),
            }
            for item in st.session_state.sheet_roles.values()
        ]
        if role_rows:
            st.dataframe(pd.DataFrame(role_rows), use_container_width=True)
        else:
            st.write("未匹配到五个专业专题的数据结构，当前使用通用数据分析。")


def render_query_console(kb: KnowledgeBase) -> None:
    if not st.session_state.workbook_context:
        return
    st.subheader("3. 对话式问数")
    status = "已启用" if st.session_state.llm_enabled and st.session_state.llm_api_key else "未启用"
    web_status = "已启用" if st.session_state.web_search_enabled else "未启用"
    st.caption(f"大模型增强：{status}；联网检索：{web_status}。普通问题返回表内洞察；命中专业关键词时，自动进入专业分析模式。")
    with st.container(border=True):
        llm_cols = st.columns([1, 1, 2])
        with llm_cols[0]:
            st.session_state.llm_enabled = st.checkbox("启用大模型", value=st.session_state.llm_enabled, key="query_llm_enabled")
        with llm_cols[1]:
            st.session_state.llm_provider = st.selectbox(
                "模型",
                list(PROVIDER_PRESETS),
                index=list(PROVIDER_PRESETS).index(st.session_state.llm_provider) if st.session_state.llm_provider in PROVIDER_PRESETS else 0,
                key="query_llm_provider",
            )
        with llm_cols[2]:
            st.session_state.llm_api_key = st.text_input("API Key", value=st.session_state.llm_api_key, type="password", key="query_llm_key")
        if st.session_state.llm_api_key and not st.session_state.llm_enabled:
            st.session_state.llm_enabled = True
            st.info("已检测到 API Key，本次问数将启用大模型增强。")
        preset = PROVIDER_PRESETS.get(st.session_state.llm_provider)
        if preset and (not st.session_state.llm_base_url or st.session_state.llm_provider != "Custom"):
            st.session_state.llm_base_url = preset["base_url"]
            st.session_state.llm_model = preset["model"]
        if st.session_state.llm_api_key:
            if st.button("保存模型配置到本地 .env.local", use_container_width=True):
                path = persist_llm_settings()
                st.success(f"已保存模型配置：{path}")
        if st.session_state.llm_enabled and not st.session_state.llm_api_key:
            st.warning("已勾选大模型，但还没有填写 API Key。本次会退回本地规则结果。")
        with st.container(border=True):
            search_cols = st.columns([1, 1, 2])
            with search_cols[0]:
                st.session_state.web_search_enabled = st.checkbox("联网检索", value=st.session_state.web_search_enabled, key="query_web_search_enabled")
            with search_cols[1]:
                st.session_state.web_search_provider = st.selectbox(
                    "搜索源",
                    ["DuckDuckGo", "Tavily"],
                    index=["DuckDuckGo", "Tavily"].index(st.session_state.web_search_provider)
                    if st.session_state.web_search_provider in {"DuckDuckGo", "Tavily"}
                    else 0,
                    key="query_web_search_provider",
                )
            with search_cols[2]:
                st.session_state.web_search_api_key = st.text_input(
                    "搜索 API Key（Tavily 需要）",
                    value=st.session_state.web_search_api_key,
                    type="password",
                    key="query_web_search_key",
                )
            st.caption("联网检索会把搜索结果摘要和来源交给大模型；没有检索结果时，报告不会声称使用了外部实时信息。")
            if st.session_state.web_search_enabled and not (st.session_state.llm_enabled and st.session_state.llm_api_key):
                st.info("联网检索需要和大模型增强一起使用；未启用大模型时不会调用搜索。")
            if st.session_state.web_search_enabled and st.session_state.web_search_provider == "Tavily" and not st.session_state.web_search_api_key:
                st.warning("Tavily 需要搜索 API Key；也可以切换到 DuckDuckGo 先做无 Key 检索。")
        examples = [
            "目前发展比较健康的连锁品牌有哪几个？",
            "上市的品牌中，哪几个品牌目前股票增长比较顺利？",
            "请总结这个数据表的关键发现。",
            "请分析5月华东区经销商业绩下降的主要原因。",
            "请评估本期社群陪跑项目是否带来了真实业绩提升。",
        ]
        selected_example = st.selectbox("示例问题", [""] + examples)
        default_question = selected_example or "请总结这个数据表的关键发现。"
        input_col, submit_col = st.columns([7, 1.15])
        with input_col:
            question = st.text_area("输入你的数据问题", value=default_question, height=120, key="query_question")
        if st.session_state.query_last_question != question:
            st.session_state.query_status = "idle"
        with submit_col:
            st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
            button_slot = st.empty()
            if st.session_state.query_status == "completed" and st.session_state.query_last_question == question:
                submitted = button_slot.button("✓ 结果完成", type="secondary", use_container_width=True, key="query_done_button")
            elif st.session_state.query_status == "running":
                button_slot.button("运行中....", type="primary", use_container_width=True, disabled=True, key="query_running_button")
                submitted = False
            else:
                submitted = button_slot.button("▶", type="primary", use_container_width=True, help="提交问题并生成结果", key="query_submit_button")
        st.caption("提示：如果问题需要表外信息，例如实时股票涨幅，系统会明确提示缺少数据，不会编造。")
        if submitted:
            button_slot.button("运行中....", type="primary", use_container_width=True, disabled=True, key="query_running_button_active")
            st.session_state.query_running = True
            st.session_state.query_status = "running"
            st.session_state.query_last_question = question
            with st.spinner("正在读取数据、检索信息并生成报告..."):
                try:
                    answer_data_question(kb, question)
                    st.session_state.query_status = "completed"
                    button_slot.button("✓ 结果完成", type="secondary", use_container_width=True, disabled=True, key="query_done_button_active")
                except Exception as exc:
                    st.session_state.query_status = "idle"
                    st.error(f"问数失败：{exc}")
                finally:
                    st.session_state.query_running = False

    if st.session_state.query_history:
        latest = st.session_state.query_history[-1]
        st.markdown("### 最新结果")
        with st.container(border=True):
            provider = latest.get("llm_provider") if latest.get("llm_used") else "本地规则"
            st.markdown(f"**问题**：{latest['question']}")
            st.markdown(f"**模式**：{latest['mode']} | **分析引擎**：{provider}")
            report_path = Path(latest["report_path"])
            if report_path.exists():
                st.markdown("**HTML 分析报告**")
                components.html(report_path.read_text(encoding="utf-8"), height=760, scrolling=True)
                st.download_button(
                    "下载 HTML 查询报告",
                    report_path.read_bytes(),
                    file_name=report_path.name,
                    mime="text/html",
                    key=f"latest_query_report_{report_path.name}",
                )
            st.markdown("**文本结论**")
            st.write(latest["answer"])
            if latest["evidence"]:
                st.markdown("**依据**")
                for evidence in latest["evidence"]:
                    st.write(f"- {evidence}")
            if latest["limitations"]:
                st.markdown("**限制**")
                for limitation in latest["limitations"]:
                    st.write(f"- {limitation}")
            for table in latest["tables"][:2]:
                st.dataframe(table, use_container_width=True)

        if len(st.session_state.query_history) > 1:
            st.markdown("### 历史问题")
            history_rows = [
                {
                    "问题": item["question"],
                    "模式": item["mode"],
                    "引擎": item.get("llm_provider") if item.get("llm_used") else "本地规则",
                    "报告": str(item["report_path"]),
                }
                for item in reversed(st.session_state.query_history[:-1])
            ]
            st.dataframe(pd.DataFrame(history_rows), use_container_width=True)


def render_analysis_controls(kb: KnowledgeBase) -> None:
    if not st.session_state.workbook_context:
        return
    if st.session_state.selected_skill_id == "generic_data_analysis":
        st.info("当前数据使用通用数据分析。请优先使用上方对话式问数；如需专业报告，请上传匹配五个专题的数据包。")
        return
    st.subheader("手动运行专业专题报告")
    skill = kb.skills[st.session_state.selected_skill_id]
    default_question = skill.get("recommended_questions", ["请基于上传数据完成业务诊断，并给出决策建议和行动计划。"])[0]
    question = st.text_area("业务问题", value=default_question, height=90)
    refresh_prepared_context(kb)
    validation = validate_skill_inputs(st.session_state.selected_skill_id, st.session_state.prepared_context, st.session_state.prepared_mappings, kb.sheet_schema_catalog, kb.skills)
    if validation.can_run_full_analysis:
        st.success("当前数据满足该专题完整分析要求。")
    else:
        st.warning("当前只能做有限分析，以下数据缺口会影响部分结论。")
        st.dataframe(validation_to_frame(validation), use_container_width=True)
    if st.button("生成专业 HTML 报告", type="primary", use_container_width=True):
        try:
            run_current_analysis(kb, question)
            st.success("专业分析和报告已生成。")
        except Exception as exc:
            st.error(f"分析失败：{exc}")


def render_result() -> None:
    result = st.session_state.analysis_result
    if not result:
        return
    st.subheader("专业分析结果")
    st.write(result.executive_summary)
    metric_cols = st.columns(min(len(result.key_metrics), 4) or 1)
    for idx, metric in enumerate(result.key_metrics):
        with metric_cols[idx % len(metric_cols)]:
            st.metric(metric.name, metric.value)
    tabs = st.tabs(["发现与归因", "决策与行动", "HTML 报告"])
    with tabs[0]:
        for item in result.key_findings:
            st.write(f"- {item}")
        for chart in result.charts:
            with st.expander(chart["title"], expanded=False):
                components.html(chart["html"], height=420, scrolling=True)
    with tabs[1]:
        for idx, item in enumerate(result.decision_options, start=1):
            st.write(f"{idx}. {item}")
        st.info(result.recommended_decision)
        edited = st.data_editor(action_plan_to_frame(result), use_container_width=True, num_rows="dynamic")
        result.action_plan = edited.to_dict("records")
        st.session_state.analysis_result = result
    with tabs[2]:
        path = Path(st.session_state.html_report_path)
        st.write(path)
        st.download_button("下载 HTML 报告", path.read_bytes(), file_name=path.name, mime="text/html")
        components.html(path.read_text(encoding="utf-8"), height=720, scrolling=True)


def render_report_center() -> None:
    st.subheader("报告中心")
    st.caption("集中查看本次会话生成的查询报告和专业分析报告。")
    if st.session_state.query_history:
        st.markdown("**查询分析报告**")
        for idx, item in enumerate(reversed(st.session_state.query_history), start=1):
            report_path = Path(item["report_path"])
            with st.container(border=True):
                st.write(f"**{idx}. {item['mode']}**")
                st.write(item["question"])
                st.write(item["answer"])
                if report_path.exists():
                    st.code(str(report_path), language="text")
                    st.download_button(
                        "下载 HTML",
                        report_path.read_bytes(),
                        file_name=report_path.name,
                        mime="text/html",
                        key=f"report_center_query_{idx}_{report_path.name}",
                    )
    else:
        st.info("还没有查询报告。请先到“对话问数”提出一个问题。")

    if st.session_state.html_report_path:
        st.markdown("**专业分析报告**")
        path = Path(st.session_state.html_report_path)
        if path.exists():
            st.code(str(path), language="text")
            st.download_button(
                "下载专业分析 HTML",
                path.read_bytes(),
                file_name=path.name,
                mime="text/html",
                key="report_center_professional",
            )
            with st.expander("预览专业分析报告", expanded=False):
                components.html(path.read_text(encoding="utf-8"), height=720, scrolling=True)


def page_auto_agent(kb: KnowledgeBase) -> None:
    st.title("AI Decision Data Agent")
    st.caption("上传数据，查看概况，然后用自然语言问数据；命中业务专题时自动进入专业 Skill。")
    upload_tab, overview_tab, query_tab, skill_tab, report_tab, settings_tab = st.tabs(
        ["数据上传", "数据概况", "对话问数", "专业分析", "报告中心", "模型设置"]
    )
    with upload_tab:
        render_upload_area(kb)
    with overview_tab:
        render_data_overview(kb)
    with query_tab:
        render_query_console(kb)
    with skill_tab:
        render_analysis_controls(kb)
        render_result()
    with report_tab:
        render_report_center()
    with settings_tab:
        page_settings()


def page_data_details(kb: KnowledgeBase) -> None:
    st.header("Data Details")
    context = st.session_state.workbook_context
    if not context:
        st.warning("请先在 Auto Agent 页面上传或选择样例数据。")
        return
    tab1, tab2, tab3 = st.tabs(["Sheet Preview", "Field Mapping", "Validation"])
    with tab1:
        sheet = st.selectbox("选择 Sheet", list(context.sheets))
        st.dataframe(context.sheets[sheet].head(100), use_container_width=True)
    with tab2:
        for sheet, mapping in list(st.session_state.field_mappings.items()):
            st.subheader(sheet)
            edited = st.data_editor(mapping_to_frame(mapping), use_container_width=True, num_rows="fixed", key=f"map_{sheet}")
            for _, row in edited.iterrows():
                col = row["Uploaded Column"]
                value = str(row["Suggested Standard Field"]).strip() or None
                mapping.column_mappings[col].standard_field = value
                mapping.column_mappings[col].status = "Matched" if value else "Unmatched"
            st.session_state.field_mappings[sheet] = mapping
    with tab3:
        if st.session_state.selected_skill_id == "generic_data_analysis":
            st.info("通用数据分析不需要专业字段校验。")
            return
        refresh_prepared_context(kb)
        validation = validate_skill_inputs(st.session_state.selected_skill_id, st.session_state.prepared_context, st.session_state.prepared_mappings, kb.sheet_schema_catalog, kb.skills)
        st.write(validation)
        st.dataframe(validation_to_frame(validation), use_container_width=True)


def page_samples() -> None:
    st.header("Sample Workbooks")
    rows = [{"File": path.name, "Size KB": round(path.stat().st_size / 1024, 1), "Path": str(path)} for path in sample_options().values()]
    st.dataframe(pd.DataFrame(rows), use_container_width=True)


def page_kb(kb: KnowledgeBase) -> None:
    st.header("Knowledge Base")
    tab1, tab2, tab3, tab4 = st.tabs(["术语", "指标", "Schema", "Skills"])
    with tab1:
        st.markdown(kb.business_terms)
    with tab2:
        st.json(kb.metric_catalog)
    with tab3:
        st.json(kb.sheet_schema_catalog)
    with tab4:
        st.json(kb.skills)


def page_settings() -> None:
    st.header("Settings")
    st.subheader("大模型增强")
    st.write("用于自然语言问数的深度解释和 HTML 查询报告。关闭时使用本地规则查询。")
    st.session_state.llm_enabled = st.checkbox("启用大模型增强", value=st.session_state.llm_enabled)
    provider_names = list(PROVIDER_PRESETS)
    provider = st.selectbox("模型供应商", provider_names, index=provider_names.index(st.session_state.llm_provider) if st.session_state.llm_provider in provider_names else 0)
    if provider != st.session_state.llm_provider:
        st.session_state.llm_provider = provider
        preset = PROVIDER_PRESETS[provider]
        st.session_state.llm_base_url = preset["base_url"]
        st.session_state.llm_model = preset["model"]
    st.session_state.llm_api_key = st.text_input("API Key", value=st.session_state.llm_api_key, type="password")
    st.session_state.llm_base_url = st.text_input("Base URL", value=st.session_state.llm_base_url)
    st.session_state.llm_model = st.text_input("Model", value=st.session_state.llm_model)
    st.caption("DeepSeek 默认 Base URL: https://api.deepseek.com，Model: deepseek-chat。其他 OpenAI-compatible 服务也可以填写自己的 Base URL 和模型名。")
    st.subheader("联网检索")
    st.write("用于把最新网络信息作为上下文补充给大模型。DeepSeek Chat API 不会自动浏览网页，因此这里使用独立搜索层。")
    st.session_state.web_search_enabled = st.checkbox("启用联网检索", value=st.session_state.web_search_enabled)
    st.session_state.web_search_provider = st.selectbox(
        "搜索源",
        ["DuckDuckGo", "Tavily"],
        index=["DuckDuckGo", "Tavily"].index(st.session_state.web_search_provider)
        if st.session_state.web_search_provider in {"DuckDuckGo", "Tavily"}
        else 0,
    )
    st.session_state.web_search_api_key = st.text_input(
        "搜索 API Key（Tavily 需要；DuckDuckGo 可留空）",
        value=st.session_state.web_search_api_key,
        type="password",
    )
    st.caption("联网结果会作为来源材料进入报告；如果搜索失败，系统会明确说明并继续基于上传表格分析。")
    if st.session_state.web_search_enabled and not (st.session_state.llm_enabled and st.session_state.llm_api_key):
        st.info("联网检索需要和大模型增强一起使用；请同时启用大模型并填写 API Key。")
    if st.session_state.web_search_enabled and st.session_state.web_search_provider == "Tavily" and not st.session_state.web_search_api_key:
        st.warning("Tavily 需要搜索 API Key；DuckDuckGo 可不填 Key。")
    if st.button("保存到本地 .env.local", type="primary"):
        if st.session_state.llm_api_key:
            st.session_state.llm_enabled = True
        path = persist_llm_settings()
        st.success(f"已保存。下次打开应用会自动读取：{path}")


def main() -> None:
    st.set_page_config(page_title="AI Decision Data Agent", layout="wide")
    init_state()
    kb = load_kb()
    page = st.sidebar.radio("导航", ["Auto Agent", "Data Details", "Sample Workbooks", "Knowledge Base", "Settings"])
    if page == "Auto Agent":
        page_auto_agent(kb)
    elif page == "Data Details":
        page_data_details(kb)
    elif page == "Sample Workbooks":
        page_samples()
    elif page == "Knowledge Base":
        page_kb(kb)
    else:
        page_settings()


if __name__ == "__main__":
    main()
