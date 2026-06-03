from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def chart_to_html(fig) -> str:
    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def trend_chart(df: pd.DataFrame, x: str, y: str, title: str, color: str | None = None) -> dict[str, str]:
    if df.empty or x not in df or y not in df:
        return {"title": title, "html": "<p>数据不足，无法生成趋势图。</p>"}
    fig = px.line(df, x=x, y=y, color=color, markers=True, title=title)
    return {"title": title, "html": chart_to_html(fig)}


def bar_chart(df: pd.DataFrame, x: str, y: str, title: str, color: str | None = None) -> dict[str, str]:
    if df.empty or x not in df or y not in df:
        return {"title": title, "html": "<p>数据不足，无法生成排行图。</p>"}
    fig = px.bar(df, x=x, y=y, color=color, title=title)
    return {"title": title, "html": chart_to_html(fig)}


def pie_chart(df: pd.DataFrame, names: str, values: str, title: str) -> dict[str, str]:
    if df.empty or names not in df or values not in df:
        return {"title": title, "html": "<p>数据不足，无法生成结构图。</p>"}
    fig = px.pie(df, names=names, values=values, title=title)
    return {"title": title, "html": chart_to_html(fig)}


def scatter_chart(df: pd.DataFrame, x: str, y: str, title: str, color: str | None = None) -> dict[str, str]:
    if df.empty or x not in df or y not in df:
        return {"title": title, "html": "<p>数据不足，无法生成散点图。</p>"}
    fig = px.scatter(df, x=x, y=y, color=color, trendline=None, title=title)
    return {"title": title, "html": chart_to_html(fig)}


def funnel_chart(labels: list[str], values: list[float], title: str) -> dict[str, str]:
    fig = go.Figure(go.Funnel(y=labels, x=values))
    fig.update_layout(title=title)
    return {"title": title, "html": chart_to_html(fig)}
