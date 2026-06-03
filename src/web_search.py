from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from typing import Callable

import requests


@dataclass
class WebSearchConfig:
    enabled: bool = False
    provider: str = "DuckDuckGo"
    api_key: str = ""
    max_results: int = 5


@dataclass
class WebSearchResult:
    title: str
    url: str
    snippet: str


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", unescape(text)).strip()
    return text


def _search_tavily(
    query: str,
    config: WebSearchConfig,
    post_func: Callable = requests.post,
    timeout: int = 30,
) -> list[WebSearchResult]:
    if not config.api_key:
        raise ValueError("Tavily API Key is required for Tavily web search.")
    response = post_func(
        "https://api.tavily.com/search",
        json={
            "api_key": config.api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": config.max_results,
            "include_answer": False,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    results = []
    for item in data.get("results", [])[: config.max_results]:
        results.append(
            WebSearchResult(
                title=str(item.get("title") or item.get("url") or "Untitled"),
                url=str(item.get("url") or ""),
                snippet=str(item.get("content") or item.get("snippet") or ""),
            )
        )
    return results


def _search_duckduckgo(
    query: str,
    config: WebSearchConfig,
    get_func: Callable = requests.get,
    timeout: int = 30,
) -> list[WebSearchResult]:
    response = get_func(
        "https://duckduckgo.com/html/",
        params={"q": query},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=timeout,
    )
    response.raise_for_status()
    html = response.text
    blocks = re.findall(r'<div class="result\b.*?</div>\s*</div>', html, flags=re.S)
    results = []
    for block in blocks[: config.max_results]:
        link_match = re.search(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.S)
        snippet_match = re.search(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', block, flags=re.S)
        if not link_match:
            continue
        results.append(
            WebSearchResult(
                title=_strip_html(link_match.group(2)),
                url=unescape(link_match.group(1)),
                snippet=_strip_html(snippet_match.group(1)) if snippet_match else "",
            )
        )
    return results


def search_web(
    query: str,
    config: WebSearchConfig,
    post_func: Callable = requests.post,
    get_func: Callable = requests.get,
    timeout: int = 30,
) -> list[WebSearchResult]:
    if not config.enabled:
        return []
    provider = config.provider.lower()
    if provider == "tavily":
        return _search_tavily(query, config, post_func=post_func, timeout=timeout)
    return _search_duckduckgo(query, config, get_func=get_func, timeout=timeout)


def web_results_to_prompt(results: list[WebSearchResult]) -> str:
    if not results:
        return "未提供联网检索结果。"
    lines = []
    for index, item in enumerate(results, start=1):
        lines.append(f"{index}. {item.title}\nURL: {item.url}\n摘要: {item.snippet}")
    return "\n\n".join(lines)
