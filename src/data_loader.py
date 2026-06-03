from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import pandas as pd

from .models import WorkbookContext


def _file_name(file: str | Path | BinaryIO) -> str:
    if isinstance(file, (str, Path)):
        return Path(file).name
    return getattr(file, "name", "uploaded_file")


def load_workbook(file: str | Path | BinaryIO) -> WorkbookContext:
    """Load an Excel workbook or CSV into a normalized workbook context."""
    name = _file_name(file)
    suffix = Path(name).suffix.lower()

    if suffix == ".xlsx":
        excel = pd.ExcelFile(file)
        sheets = {
            sheet_name: excel.parse(sheet_name)
            for sheet_name in excel.sheet_names
            if sheet_name and not sheet_name.startswith("_")
        }
        return WorkbookContext(name, "xlsx", sheets, Path(file) if isinstance(file, (str, Path)) else None)

    if suffix == ".csv":
        df = pd.read_csv(file)
        sheet_name = Path(name).stem or "csv_data"
        return WorkbookContext(name, "csv", {sheet_name: df}, Path(file) if isinstance(file, (str, Path)) else None)

    raise ValueError("Only .xlsx and .csv files are supported in the MVP.")
