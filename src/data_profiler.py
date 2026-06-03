from __future__ import annotations

import re

import pandas as pd

from .models import DataProfile, SheetProfile, WorkbookContext


PHONE_PATTERN = re.compile(r"(^1[3-9]\d{9}$)|(\b\d{3}[- ]?\d{4}[- ]?\d{4}\b)")
ID_PATTERN = re.compile(r"\b\d{17}[\dXx]\b")
SENSITIVE_COLUMN_NAMES = {
    "name",
    "customer_name",
    "mobile",
    "phone",
    "phone_number",
    "id_card",
    "id_number",
    "\u59d3\u540d",
    "\u771f\u5b9e\u59d3\u540d",
    "\u624b\u673a\u53f7",
    "\u7535\u8bdd",
    "\u8eab\u4efd\u8bc1",
}
PERIOD_COLUMN_NAMES = {
    "month",
    "date",
    "order_date",
    "start_date",
    "end_date",
    "\u6708\u4efd",
    "\u8ba2\u5355\u65e5\u671f",
    "\u5f00\u59cb\u65e5\u671f",
    "\u7ed3\u675f\u65e5\u671f",
}


def _detect_period(df: pd.DataFrame) -> tuple[str | None, str | None]:
    candidates = [
        col
        for col in df.columns
        if str(col).strip().lower() in PERIOD_COLUMN_NAMES
    ]
    values: list[pd.Timestamp] = []
    for col in candidates:
        parsed = pd.to_datetime(df[col], errors="coerce")
        values.extend(parsed.dropna().tolist())
    if not values:
        return None, None
    return min(values).date().isoformat(), max(values).date().isoformat()


def _is_missing_value(value: object) -> bool:
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(missing) if isinstance(missing, bool) else False


def _sample_text_values(df: pd.DataFrame, max_rows: int = 100) -> list[str]:
    values = df.head(max_rows).to_numpy().flatten().tolist()
    texts: list[str] = []
    for value in values:
        if _is_missing_value(value):
            continue
        text = str(value).strip()
        if text and text.lower() not in {"nan", "nat", "none", "<na>"}:
            texts.append(text)
    return texts


def _privacy_warnings(df: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    sensitive_cols = [
        str(col)
        for col in df.columns
        if str(col).strip().lower() in SENSITIVE_COLUMN_NAMES
    ]
    if sensitive_cols:
        warnings.append(f"Found possible sensitive columns: {', '.join(sensitive_cols)}")

    sample = _sample_text_values(df)
    if any(PHONE_PATTERN.search(value) for value in sample):
        warnings.append("Found values that look like phone numbers; mask them before sharing.")
    if any(ID_PATTERN.search(value) for value in sample):
        warnings.append("Found values that look like ID numbers; remove or mask them before sharing.")
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
