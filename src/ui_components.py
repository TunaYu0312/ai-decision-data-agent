from __future__ import annotations

import pandas as pd

from .models import AnalysisResult, DataProfile, FieldMappingResult, ValidationResult


def profile_to_frame(profile: DataProfile) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Sheet": item.sheet_name,
                "Rows": item.row_count,
                "Columns": item.column_count,
                "Missing Rate": f"{item.missing_rate:.1%}",
                "Period Start": item.period_start or "",
                "Period End": item.period_end or "",
                "Privacy Warnings": " | ".join(item.privacy_warnings),
            }
            for item in profile.sheets.values()
        ]
    )


def mapping_to_frame(mapping: FieldMappingResult) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Uploaded Column": item.uploaded_column,
                "Suggested Standard Field": item.standard_field or "",
                "Confidence": item.confidence,
                "Required": item.required,
                "Status": item.status,
            }
            for item in mapping.column_mappings.values()
        ]
    )


def validation_to_frame(validation: ValidationResult) -> pd.DataFrame:
    rows = []
    for sheet in validation.missing_required_sheets:
        rows.append({"Type": "Missing Sheet", "Sheet": sheet, "Field": ""})
    for sheet, fields in validation.missing_required_fields.items():
        for field in fields:
            rows.append({"Type": "Missing Field", "Sheet": sheet, "Field": field})
    return pd.DataFrame(rows)


def action_plan_to_frame(result: AnalysisResult) -> pd.DataFrame:
    return pd.DataFrame(result.action_plan)
