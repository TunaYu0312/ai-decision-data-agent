from __future__ import annotations

import re

from .models import ColumnMapping, FieldMappingResult, ValidationResult, WorkbookContext


def normalize_name(value: str) -> str:
    return re.sub(r"[\s_\-　:/（）()]+", "", str(value).strip().lower())


def _alias_lookup(field_aliases: dict) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for standard_field, config in field_aliases.items():
        lookup[normalize_name(standard_field)] = standard_field
        for alias in config.get("aliases", []):
            lookup[normalize_name(alias)] = standard_field
    return lookup


def suggest_field_mapping(
    sheet_name: str,
    columns: list[str],
    field_aliases: dict,
    required_fields: set[str] | None = None,
) -> FieldMappingResult:
    required_fields = required_fields or set()
    lookup = _alias_lookup(field_aliases)
    mappings: dict[str, ColumnMapping] = {}
    for column in columns:
        standard = lookup.get(normalize_name(column))
        status = "Matched" if standard else "Unmatched"
        confidence = 1.0 if standard and normalize_name(column) == normalize_name(standard) else 0.86 if standard else 0.0
        mappings[str(column)] = ColumnMapping(
            uploaded_column=str(column),
            standard_field=standard,
            confidence=confidence,
            required=bool(standard in required_fields),
            status=status,
        )
    return FieldMappingResult(sheet_name=sheet_name, column_mappings=mappings)


def validate_skill_inputs(
    skill_id: str,
    context: WorkbookContext,
    mappings: dict[str, FieldMappingResult],
    sheet_schema_catalog: dict,
    skills: dict,
) -> ValidationResult:
    skill = skills[skill_id]
    required_sheets = list(skill.get("required_sheets", []))
    missing_sheets = [sheet for sheet in required_sheets if sheet not in context.sheets]
    missing_fields: dict[str, list[str]] = {}

    for sheet in required_sheets:
        if sheet in missing_sheets:
            continue
        schema = sheet_schema_catalog.get(sheet, {})
        required = [field for field, item in schema.get("fields", {}).items() if item.get("required")]
        mapped = mappings.get(sheet)
        mapped_fields = mapped.standard_fields() if mapped else set()
        absent = [field for field in required if field not in mapped_fields]
        if absent:
            missing_fields[sheet] = absent

    warnings = []
    optional_sheets = [sheet for sheet in skill.get("optional_sheets", []) if sheet not in context.sheets]
    if optional_sheets:
        warnings.append(f"缺少可选 Sheet: {', '.join(optional_sheets)}，相关结论会降级。")

    return ValidationResult(
        skill_id=skill_id,
        can_run_full_analysis=not missing_sheets and not missing_fields,
        missing_required_sheets=missing_sheets,
        missing_required_fields=missing_fields,
        warnings=warnings,
    )
