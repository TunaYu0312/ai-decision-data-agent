from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

import pandas as pd
import requests

from .models import WorkbookContext
from .query_engine import QueryAnswer
from .web_search import WebSearchResult, web_results_to_prompt


DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"


@dataclass
class LLMConfig:
    provider: str
    api_key: str
    base_url: str
    model: str
    enabled: bool = False


PROVIDER_PRESETS = {
    "DeepSeek": {"base_url": "https://api.deepseek.com", "model": DEFAULT_DEEPSEEK_MODEL},
    "OpenAI Compatible": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    "OpenRouter": {"base_url": "https://openrouter.ai/api/v1", "model": "deepseek/deepseek-chat"},
    "Custom": {"base_url": "", "model": ""},
}


def chat_completions_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _workbook_context_payload(context: WorkbookContext, max_rows: int = 50) -> str:
    payload = {"file_name": context.file_name, "sheets": []}
    for sheet_name, df in context.sheets.items():
        sample = df.head(max_rows).where(pd.notna(df.head(max_rows)), None).to_dict(orient="records")
        payload["sheets"].append(
            {
                "sheet_name": sheet_name,
                "shape": [int(df.shape[0]), int(df.shape[1])],
                "columns": [str(col) for col in df.columns],
                "sample_rows": sample,
            }
        )
    return json.dumps(payload, ensure_ascii=False, default=str)


def _answer_payload(answer: QueryAnswer) -> str:
    tables = []
    for table in answer.tables[:2]:
        tables.append(table.head(12).where(pd.notna(table.head(12)), None).to_dict(orient="records"))
    return json.dumps(
        {
            "local_answer": answer.answer,
            "evidence": answer.evidence,
            "limitations": answer.limitations,
            "tables": tables,
        },
        ensure_ascii=False,
        default=str,
    )


def enhance_query_with_llm(
    context: WorkbookContext,
    question: str,
    local_answer: QueryAnswer,
    config: LLMConfig,
    web_results: list[WebSearchResult] | None = None,
    post_func: Callable = requests.post,
    timeout: int = 60,
) -> QueryAnswer:
    if not config.api_key:
        raise ValueError("API key is required.")
    if not config.base_url:
        raise ValueError("Base URL is required.")
    if not config.model:
        raise ValueError("Model is required.")

    system_prompt = (
        "你是一个严谨的数据分析助手。你只能基于用户上传表格的字段、样本和本地规则分析结果作答。"
        "如果问题需要表格之外的实时信息、股票行情、外部事实或公司最新状态，而上下文没有提供，必须明确说明缺少数据，不能编造。"
        "不要输出思考过程，不要解释你如何推理。"
        "输出中文 Markdown，面向业务负责人，必须突出问题、结论和下一步动作。"
        "建议结构："
        "## 直接结论，3-5条加粗要点；"
        "## 关键发现，按重要性排序；"
        "## 外部信息补充，如果提供了联网检索结果，说明它们如何补充或修正表内判断；"
        "## 数据依据，用简短项目符号说明；"
        "## 建议与下一步，用行动项、优先级、预期效果表达；"
        "## 数据限制，只写会影响判断的限制。"
        "如果适合对比或排序，可以输出 Markdown 表格。"
        "如果联网检索结果为空，不要声称已经联网。"
    )
    web_context = web_results_to_prompt(web_results or [])
    user_prompt = (
        f"用户问题：{question}\n\n"
        f"上传数据上下文：\n{_workbook_context_payload(context)}\n\n"
        f"本地规则分析结果：\n{_answer_payload(local_answer)}\n\n"
        f"联网检索结果：\n{web_context}"
    )
    response = post_func(
        chat_completions_url(config.base_url),
        headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
        json={
            "model": config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "stream": False,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    evidence = local_answer.evidence + [f"{config.provider} model: {config.model}"]
    if web_results:
        evidence.append("已启用联网检索：" + "；".join(f"{item.title} ({item.url})" for item in web_results[:5]))
    return QueryAnswer(
        question=question,
        answer=content,
        evidence=evidence,
        limitations=local_answer.limitations,
        tables=local_answer.tables,
        charts=local_answer.charts,
        llm_used=True,
        llm_provider=config.provider,
    )


def deepseek_enhance_query(
    context: WorkbookContext,
    question: str,
    local_answer: QueryAnswer,
    api_key: str,
    model: str = DEFAULT_DEEPSEEK_MODEL,
    post_func: Callable = requests.post,
    timeout: int = 60,
) -> QueryAnswer:
    return enhance_query_with_llm(
        context,
        question,
        local_answer,
        LLMConfig("DeepSeek", api_key, "https://api.deepseek.com", model, True),
        web_results=None,
        post_func=post_func,
        timeout=timeout,
    )
