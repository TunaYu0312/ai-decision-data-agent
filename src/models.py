from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class WorkbookContext:
    file_name: str
    file_type: str
    sheets: dict[str, pd.DataFrame]
    source_path: Path | None = None


@dataclass
class SheetProfile:
    sheet_name: str
    row_count: int
    column_count: int
    columns: list[str]
    missing_rate: float
    period_start: str | None = None
    period_end: str | None = None
    privacy_warnings: list[str] = field(default_factory=list)


@dataclass
class DataProfile:
    sheets: dict[str, SheetProfile]


@dataclass
class ColumnMapping:
    uploaded_column: str
    standard_field: str | None
    confidence: float
    required: bool = False
    status: str = "Unmatched"


@dataclass
class FieldMappingResult:
    sheet_name: str
    column_mappings: dict[str, ColumnMapping]

    def standard_fields(self) -> set[str]:
        return {
            item.standard_field
            for item in self.column_mappings.values()
            if item.standard_field
        }

    def rename_map(self) -> dict[str, str]:
        return {
            item.uploaded_column: item.standard_field
            for item in self.column_mappings.values()
            if item.standard_field
        }


@dataclass
class ValidationResult:
    skill_id: str
    can_run_full_analysis: bool
    missing_required_sheets: list[str]
    missing_required_fields: dict[str, list[str]]
    warnings: list[str] = field(default_factory=list)


@dataclass
class MetricValue:
    key: str
    name: str
    value: Any
    note: str = ""


@dataclass
class AnalysisResult:
    skill_id: str
    skill_name: str
    business_question: str
    executive_summary: str
    data_availability_check: str
    key_metrics: list[MetricValue]
    key_findings: list[str]
    driver_analysis: list[str]
    decision_options: list[str]
    recommended_decision: str
    action_plan: list[dict[str, Any]]
    kpi_tracking: list[str]
    risks_assumptions: list[str]
    review_plan: str
    charts: list[dict[str, str]] = field(default_factory=list)
    appendix_tables: dict[str, pd.DataFrame] = field(default_factory=dict)

    def required_sections_complete(self) -> bool:
        return bool(
            self.decision_options
            and self.recommended_decision
            and self.action_plan
            and self.kpi_tracking
            and self.review_plan
        )
