from __future__ import annotations

import re

import pandas as pd

from .models import DataProfile, SheetProfile, WorkbookContext


PHONE_PATTERN = re.compile(r"(^1[3-9]\d{9}$)|(\b\d{3}[- ]?\d{4}[- ]?\d{4}\b)")
ID_PATTERN = re.compile(r"\b\d{17}[\dXx]\b")
NAME_COLUMNS = {"姓名", "真实姓名", "name", "customer_name", "mobile", "手机号", "电话", "身份证"}


def _detect_period(df: pd.DataFrame) -> tuple[str | None, str | None]:
    candidates = [col for col in df.columns if str(col).lower() in {"month", "月份", "date", "order_date", "订单日期", "start_date", "end_date"}]
    values: list[pd.Timestamp] = []
    for col in candidates:
        parsed = pd.to_datetime(df[col], errors="coerce")
        values.extend(parsed.dropna().tolist())
    if not values:
        return None, None
    return min(values).date().isoformat(), max(values).date().isoformat()


def _privacy_warnings(df: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    sensitive_cols = [str(col) for col in df.columns if str(col).strip().lower() in NAME_COLUMNS]
    if sensitive_cols:
        warnings.append(f"发现疑似敏感字段: {', '.join(sensitive_cols)}")
    sample = df.head(100).astype(str).to_numpy().flatten().tolist()
    if any(PHONE_PATTERN.search(value) for value in sample):
        warnings.append("发现疑似手机号样式数据，建议上传前脱敏。")
    if any(ID_PATTERN.search(value) for value in sample):
        warnings.append("发现疑似身份证号样式数据，建议上传前移除。")
    return warnings


def profile_workbook(context: WorkbookContext) -> DataProfile:
    sheets: dict[str, SheetProfile] = {}
    for sheet_name, df in context.sheets.items():
        missing_cells = int(df.isna().sum().sum())
        total_cells = max(int(df.shape[0] * df.shape[1]), 1)
        period_start, period_end = _detect_period(df)
        sheets[sheet_name] = SheetProfile(
            sheet_name=sheet_name,
            row_count=int(df.shape[0]),
            column_count=int(df.shape[1]),
            columns=[str(col) for col in df.columns],
            missing_rate=round(missing_cells / total_cells, 4),
            period_start=period_start,
            period_end=period_end,
            privacy_warnings=_privacy_warnings(df),
        )
    return DataProfile(sheets=sheets)
