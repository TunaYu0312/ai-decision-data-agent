import pandas as pd

from src.data_profiler import profile_workbook
from src.models import WorkbookContext


def test_profile_workbook_handles_mixed_cell_types_in_privacy_scan():
    df = pd.DataFrame(
        {
            "brand": ["A", "B", None],
            "stores": [123, pd.NA, 456.7],
            "latest_update": [pd.Timestamp("2026-01-01"), None, "2026-02-01"],
            "contact": [13800138000, "", "masked"],
        }
    )
    context = WorkbookContext(
        file_name="mixed.xlsx",
        file_type=".xlsx",
        sheets={"Sheet1": df},
    )

    profile = profile_workbook(context)

    sheet = profile.sheets["Sheet1"]
    assert sheet.row_count == 3
    assert sheet.column_count == 4
    assert any("phone numbers" in warning for warning in sheet.privacy_warnings)
