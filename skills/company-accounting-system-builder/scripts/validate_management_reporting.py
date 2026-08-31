#!/usr/bin/env python3
"""Mechanical validation for management reporting artifacts.

This module proves lineage and arithmetic only. It does not establish that an
accounting classification, allocation, tax treatment, or professional opinion
is correct.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from render_management_dashboard import render_management_dashboard


TOLERANCE = Decimal("0.01")
RATIO_TOLERANCE = Decimal("0.0001")
BASE_LINE_IDS = (
    "GROSS_REVENUE",
    "REVENUE_DEDUCTIONS",
    "COST_OF_SALES",
    "OPERATING_EXPENSE",
    "OTHER_INCOME",
    "OTHER_EXPENSE",
    "INCOME_TAX",
    "DISCONTINUED_OPERATIONS",
)
ALL_LINE_IDS = (
    "GROSS_REVENUE",
    "REVENUE_DEDUCTIONS",
    "NET_REVENUE",
    "COST_OF_SALES",
    "GROSS_PROFIT",
    "OPERATING_EXPENSE",
    "OPERATING_PROFIT",
    "OTHER_INCOME",
    "OTHER_EXPENSE",
    "PRETAX_PROFIT",
    "INCOME_TAX",
    "CONTINUING_PROFIT",
    "DISCONTINUED_OPERATIONS",
    "NET_PROFIT",
)
EXPECTED_OPERATIONS = {
    "GROSS_REVENUE": "ACCOUNT_SUM",
    "REVENUE_DEDUCTIONS": "ACCOUNT_SUM",
    "NET_REVENUE": "SUBTRACT_LINES",
    "COST_OF_SALES": "ACCOUNT_SUM",
    "GROSS_PROFIT": "SUBTRACT_LINES",
    "OPERATING_EXPENSE": "ACCOUNT_SUM",
    "OPERATING_PROFIT": "SUBTRACT_LINES",
    "OTHER_INCOME": "ACCOUNT_SUM",
    "OTHER_EXPENSE": "ACCOUNT_SUM",
    "PRETAX_PROFIT": "ADD_SUBTRACT_LINES",
    "INCOME_TAX": "ACCOUNT_SUM",
    "CONTINUING_PROFIT": "SUBTRACT_LINES",
    "DISCONTINUED_OPERATIONS": "ACCOUNT_SUM_SIGNED",
    "NET_PROFIT": "SUM_LINES",
}
CATEGORY_TO_LINE = {
    "REVENUE": "GROSS_REVENUE",
    "REVENUE_DEDUCTION": "REVENUE_DEDUCTIONS",
    "COST_OF_SALES": "COST_OF_SALES",
    "OPERATING_EXPENSE": "OPERATING_EXPENSE",
    "OTHER_INCOME": "OTHER_INCOME",
    "OTHER_EXPENSE": "OTHER_EXPENSE",
    "INCOME_TAX": "INCOME_TAX",
    "DISCONTINUED_OPERATIONS": "DISCONTINUED_OPERATIONS",
}
ALLOWED_PNL_CATEGORIES = set(CATEGORY_TO_LINE) | {"NON_PNL"}
INCOME_CATEGORIES = {"REVENUE", "OTHER_INCOME", "DISCONTINUED_OPERATIONS"}
ALLOWED_DEFINITION_OPERATIONS = {
    "ACCOUNT_SUM",
    "ACCOUNT_SUM_SIGNED",
    "SUM_LINES",
    "SUBTRACT_LINES",
    "ADD_SUBTRACT_LINES",
}
CORE_MODULES = {"O6-DASH", "O6-PROFIT", "O6-COST", "O6-TRUST", "O6-CLOSE"}
KNOWN_MODULES = CORE_MODULES | {
    "O6-CASH", "O6-MONEY", "O6-DIMENSION", "O6-TREND", "O6-BUDGET",
    "O6-TAX-RESERVE", "O6-SCENARIO",
}
ALLOWED_MODULE_STATUSES = {"PROPOSED", "ENABLED", "DECLINED", "DISABLED"}
ALLOWED_REPORT_STATUSES = {
    "DRAFT",
    "CONTROL_CHECKED",
    "OWNER_APPROVED_MANAGEMENT",
    "PROFESSIONAL_REVIEW_REQUIRED",
    "PROFESSIONALLY_REVIEWED",
}
APPROVED_POLICY_STATUSES = {"owner_confirmed", "professionally_reviewed"}
UNVALIDATED_CLOSE_MODULES = {"O6-MONEY", "O6-TREND", "O6-TAX-RESERVE", "O6-SCENARIO"}
REQUIRED_TRUST_CHECKS = {
    "EVIDENCE_GAPS",
    "OPEN_ITEMS",
    "UNPOSTED_TRANSACTIONS",
    "UNCLASSIFIED_COST",
    "REPORT_RECONCILIATION",
}
BASE_FULL_REVIEW_AREAS = {
    "ACCRUAL_PNL_DRAFT",
    "MANAGEMENT_ADJUSTMENTS",
    "COST_BREAKDOWN",
    "TRUST_AND_ACTIONS",
}
OPTIONAL_REVIEW_AREAS = {
    "O6-CASH": "CASH_SUMMARY",
    "O6-DIMENSION": "DIMENSION_SUMMARY",
    "O6-BUDGET": "BUDGET_COMPARISON",
}


def decimal_value(value, label: str, report, *, nullable: bool = False):
    if value is None or str(value).strip() == "":
        if nullable:
            return None
        report.error(f"{label}: amount is required")
        return Decimal("0")
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        report.error(f"{label}: invalid decimal {value!r}")
        return Decimal("0")


def derive_pnl_lines(base: dict[str, Decimal]) -> dict[str, Decimal]:
    """Derive the fixed P&L tree without evaluating arbitrary formulas."""
    values = {line_id: Decimal(base.get(line_id, Decimal("0"))) for line_id in BASE_LINE_IDS}
    values["NET_REVENUE"] = values["GROSS_REVENUE"] - values["REVENUE_DEDUCTIONS"]
    values["GROSS_PROFIT"] = values["NET_REVENUE"] - values["COST_OF_SALES"]
    values["OPERATING_PROFIT"] = values["GROSS_PROFIT"] - values["OPERATING_EXPENSE"]
    values["PRETAX_PROFIT"] = (
        values["OPERATING_PROFIT"] + values["OTHER_INCOME"] - values["OTHER_EXPENSE"]
    )
    values["CONTINUING_PROFIT"] = values["PRETAX_PROFIT"] - values["INCOME_TAX"]
    values["NET_PROFIT"] = values["CONTINUING_PROFIT"] + values["DISCONTINUED_OPERATIONS"]
    return {line_id: values[line_id] for line_id in ALL_LINE_IDS}


def contains_embedded_chart_values(value) -> bool:
    """Reject chart payloads that contain a second, embedded numeric dataset."""
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in {"values", "data", "dataset", "series_values"}:
                return True
            if contains_embedded_chart_values(child):
                return True
    elif isinstance(value, list):
        return any(contains_embedded_chart_values(child) for child in value)
    return False


def o6_is_enabled(feature_selection) -> bool:
    if not isinstance(feature_selection, dict):
        return False
    for feature in feature_selection.get("features", []):
        if not isinstance(feature, dict):
            continue
        feature_id = str(feature.get("feature_id", "")).strip()
        lifecycle = str(feature.get("lifecycle_status", "")).upper()
        if lifecycle != "ENABLED":
            continue
        if feature_id == "O6":
            return True
        if feature.get("source") == "custom":
            haystack = " ".join(
                str(feature.get(key, ""))
                for key in ("name", "desired_outcome", "outputs")
            ).lower()
            if any(term in haystack for term in ("profit", "p&l", "management report", "損益", "獲利", "管理報表")):
                return True
    return False


def _parse_date(value, label: str, report):
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        report.error(f"{label}: must be YYYY-MM-DD")
        return None


def _warning_codes(warnings) -> set[str]:
    codes: set[str] = set()
    if not isinstance(warnings, list):
        return codes
    for item in warnings:
        if isinstance(item, str):
            codes.add(item.strip())
        elif isinstance(item, dict):
            codes.add(str(item.get("code", "")).strip())
    return codes


def validate_negative_gross_margin(financial, warnings, report) -> None:
    if financial.get("GROSS_PROFIT", Decimal("0")) < 0 and "NEGATIVE_GROSS_MARGIN" not in _warning_codes(warnings):
        report.error("management-report.json: negative gross profit must remain negative and include NEGATIVE_GROSS_MARGIN")


def _policy_statuses(policy_data) -> dict[str, str]:
    if not isinstance(policy_data, dict):
        return {}
    result = {}
    for policy in policy_data.get("policies", []):
        if isinstance(policy, dict):
            result[str(policy.get("policy_id", "")).strip()] = str(policy.get("status", "")).strip()
    return result


def validate_allocation_policies(data, report) -> dict[str, dict]:
    if not isinstance(data, dict) or data.get("schema_version") != "1.0" or not isinstance(data.get("policies"), list):
        report.error("allocation-policy-register.json: invalid schema or policies array")
        return {}
    required = {
        "allocation_policy_id", "name", "source_cost_pool", "target_dimension_type",
        "driver", "driver_source_locator", "denominator_policy", "zero_denominator_action",
        "rounding_rule", "residual_target", "frequency", "status", "approved_by",
        "approved_at", "effective_from", "effective_to", "version", "supersedes",
    }
    result: dict[str, dict] = {}
    for index, policy in enumerate(data["policies"], start=1):
        if not isinstance(policy, dict):
            report.error(f"allocation-policy-register.json policy #{index}: must be an object")
            continue
        missing = sorted(required - set(policy))
        if missing:
            report.error(f"allocation-policy-register.json policy #{index}: missing {', '.join(missing)}")
        policy_id = str(policy.get("allocation_policy_id", "")).strip()
        if not policy_id or policy_id in result:
            report.error(f"allocation-policy-register.json policy #{index}: blank or duplicate ID")
        result[policy_id] = policy
        for field in required - {"supersedes", "effective_to"}:
            if not str(policy.get(field, "")).strip():
                report.error(f"allocation-policy-register.json policy {policy_id or index}: {field} is required")
        if policy.get("zero_denominator_action") != "UNALLOCATED":
            report.error(f"allocation-policy-register.json policy {policy_id or index}: zero denominator must remain UNALLOCATED")
        if policy.get("status") not in {"draft", "owner_confirmed", "professional_review_required", "professionally_reviewed"}:
            report.error(f"allocation-policy-register.json policy {policy_id or index}: invalid status")
        if not isinstance(policy.get("source_cost_pool"), list) or not policy.get("source_cost_pool"):
            report.error(f"allocation-policy-register.json policy {policy_id or index}: source_cost_pool must be a non-empty account-code array")
        version = policy.get("version")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            report.error(f"allocation-policy-register.json policy {policy_id or index}: version must be an integer >= 1")
    return result


def validate_definition(definition, report) -> None:
    if not isinstance(definition, dict):
        report.error("management-report-definition.json: must be an object")
        return
    if definition.get("schema_version") != "1.0":
        report.error("management-report-definition.json: schema_version must be '1.0'")
    if definition.get("definition_id") != "OWNER-PNL-BASE":
        report.error("management-report-definition.json: unexpected definition_id")
    if definition.get("report_type") != "ACCRUAL_AND_MANAGEMENT_PNL_DRAFT":
        report.error("management-report-definition.json: report_type must remain an unreviewed accrual/management draft")
    if definition.get("allowed_basis") != ["ACCRUAL"]:
        report.error("management-report-definition.json: allowed_basis must be ACCRUAL only")
    lines = definition.get("lines")
    if not isinstance(lines, list):
        report.error("management-report-definition.json: lines must be an array")
        return
    seen: set[str] = set()
    for index, line in enumerate(lines, start=1):
        if not isinstance(line, dict):
            report.error(f"management-report-definition.json line #{index}: must be an object")
            continue
        line_id = str(line.get("line_id", "")).strip()
        if line_id in seen:
            report.error(f"management-report-definition.json: duplicate line_id {line_id}")
        seen.add(line_id)
        operation = str(line.get("operation", "")).strip()
        if operation not in ALLOWED_DEFINITION_OPERATIONS:
            report.error(f"management-report-definition.json {line_id}: operation is not allowed")
        if line_id in EXPECTED_OPERATIONS and operation != EXPECTED_OPERATIONS[line_id]:
            report.error(f"management-report-definition.json {line_id}: unexpected operation")
        if any(key in line for key in ("formula", "expression", "amount", "value", "code")):
            report.error(f"management-report-definition.json {line_id}: executable formula or constant is forbidden")
    if set(ALL_LINE_IDS) != seen:
        report.error("management-report-definition.json: fixed P&L line set is incomplete or changed")
    if contains_embedded_chart_values(definition.get("charts", [])):
        report.error("management-report-definition.json: charts may not embed data or values")


def validate_dashboard_config(config, stage: str, enabled: bool, report) -> set[str]:
    enabled_modules: set[str] = set()
    if not isinstance(config, dict):
        report.error("management-dashboard-config.json: must be an object")
        return enabled_modules
    if config.get("schema_version") != "1.0":
        report.error("management-dashboard-config.json: schema_version must be '1.0'")
    config_version = config.get("config_version")
    if not isinstance(config_version, int) or isinstance(config_version, bool) or config_version < 1:
        report.error("management-dashboard-config.json: config_version must be an integer >= 1")
    if config.get("status") not in {"DRAFT", "OWNER_CONFIRMED"}:
        report.error("management-dashboard-config.json: invalid status")
    if config.get("reporting_cadence") not in {"MONTHLY", "QUARTERLY", "ANNUAL", "CUSTOM"}:
        report.error("management-dashboard-config.json: invalid reporting_cadence")
    if config.get("primary_basis") != "ACCRUAL":
        report.error("management-dashboard-config.json: primary_basis must be ACCRUAL")
    if config.get("display_language") not in {"zh-TW", "en"}:
        report.error("management-dashboard-config.json: display_language must be zh-TW or en")
    for field in ("comparisons", "dimension_types", "owner_questions"):
        if not isinstance(config.get(field), list):
            report.error(f"management-dashboard-config.json: {field} must be an array")
    modules = config.get("modules")
    if not isinstance(modules, list):
        report.error("management-dashboard-config.json: modules must be an array")
        modules = []
    seen: set[str] = set()
    for index, module in enumerate(modules, start=1):
        if not isinstance(module, dict):
            report.error(f"management-dashboard-config.json module #{index}: must be an object")
            continue
        module_id = str(module.get("module_id", "")).strip()
        status = str(module.get("status", "")).upper()
        if not module_id or module_id in seen:
            report.error(f"management-dashboard-config.json: blank or duplicate module_id {module_id!r}")
        seen.add(module_id)
        if status not in ALLOWED_MODULE_STATUSES:
            report.error(f"management-dashboard-config.json {module_id}: invalid status {status!r}")
        if str(module.get("recommendation", "")).upper() not in {"AI_RECOMMENDED", "OPTIONAL", "NOT_RECOMMENDED"}:
            report.error(f"management-dashboard-config.json {module_id}: invalid recommendation")
        if not str(module.get("rationale", "")).strip():
            report.error(f"management-dashboard-config.json {module_id}: rationale is required")
        if status == "ENABLED":
            enabled_modules.add(module_id)

    if enabled and stage == "close":
        if config.get("status") != "OWNER_CONFIRMED":
            report.error("management-dashboard-config.json: O6 close requires OWNER_CONFIRMED status")
        confirmation = config.get("selection_confirmation")
        if not isinstance(confirmation, dict) or confirmation.get("status") != "CONFIRMED":
            report.error("management-dashboard-config.json: O6 close requires confirmed selection_confirmation")
        else:
            for field in ("confirmed_by", "confirmed_at", "source_locator"):
                if not str(confirmation.get(field, "")).strip():
                    report.error(f"management-dashboard-config.json: confirmation {field} is required")
        missing_core = sorted(CORE_MODULES - enabled_modules)
        if missing_core:
            report.error(
                "management-dashboard-config.json: O6 close requires core modules "
                + ", ".join(missing_core)
            )
        if not str(config.get("display_currency", "")).strip():
            report.error("management-dashboard-config.json: display_currency is required for close")
        if not str(config.get("updated_at", "")).strip():
            report.error("management-dashboard-config.json: updated_at is required for close")
        unsupported = sorted(UNVALIDATED_CLOSE_MODULES & enabled_modules)
        unsupported.extend(sorted(module_id for module_id in enabled_modules if module_id not in KNOWN_MODULES))
        if unsupported:
            report.error(
                "management-dashboard-config.json: v1.3 cannot close with unvalidated modules enabled: "
                + ", ".join(unsupported)
            )
        owner_questions = config.get("owner_questions")
        if not isinstance(owner_questions, list) or len(owner_questions) < 3:
            report.error("management-dashboard-config.json: close requires at least three answered owner decision questions")
        else:
            for index, item in enumerate(owner_questions, start=1):
                if not isinstance(item, dict):
                    report.error(f"management-dashboard-config.json owner question #{index}: must be an object")
                    continue
                for field in ("question_id", "question", "answer", "source_locator"):
                    if not str(item.get(field, "")).strip():
                        report.error(f"management-dashboard-config.json owner question #{index}: {field} is required")
                if str(item.get("status", "")).upper() != "ANSWERED":
                    report.error(f"management-dashboard-config.json owner question #{index}: status must be ANSWERED")
    return enabled_modules


def _functional_sides(row, row_number: int, functional_currency: str, report) -> tuple[Decimal, Decimal]:
    debit = decimal_value(row.get("functional_debit"), f"journal.csv row {row_number} functional_debit", report, nullable=True)
    credit = decimal_value(row.get("functional_credit"), f"journal.csv row {row_number} functional_credit", report, nullable=True)
    if debit is None and credit is None:
        report.error(f"journal.csv row {row_number}: functional debit or credit is required for reporting")
        debit = credit = Decimal("0")
    debit = debit or Decimal("0")
    credit = credit or Decimal("0")
    if debit < 0 or credit < 0 or (debit and credit):
        report.error(f"journal.csv row {row_number}: invalid functional debit/credit")
    currency = str(row.get("currency", "")).strip()
    original_debit = decimal_value(row.get("debit"), f"journal.csv row {row_number} debit", report, nullable=True) or Decimal("0")
    original_credit = decimal_value(row.get("credit"), f"journal.csv row {row_number} credit", report, nullable=True) or Decimal("0")
    if currency and functional_currency and currency != functional_currency:
        if not str(row.get("fx_rate", "")).strip() or not str(row.get("fx_source_ref", "")).strip():
            report.error(f"journal.csv row {row_number}: foreign-currency line requires fx_rate and fx_source_ref")
        fx_rate = decimal_value(row.get("fx_rate"), f"journal.csv row {row_number} fx_rate", report)
        if fx_rate <= 0:
            report.error(f"journal.csv row {row_number}: fx_rate must be positive")
        if abs(debit - original_debit * fx_rate) > TOLERANCE or abs(credit - original_credit * fx_rate) > TOLERANCE:
            report.error(f"journal.csv row {row_number}: functional amount does not equal original amount times fx_rate")
    elif currency and functional_currency:
        if abs(debit - original_debit) > TOLERANCE or abs(credit - original_credit) > TOLERANCE:
            report.error(f"journal.csv row {row_number}: same-currency functional debit/credit must equal original debit/credit")
    functional_amount = decimal_value(
        row.get("functional_amount"),
        f"journal.csv row {row_number} functional_amount",
        report,
    )
    if abs(functional_amount - (debit - credit)) > TOLERANCE:
        report.error(f"journal.csv row {row_number}: functional_amount must be signed debit minus credit")
    return debit, credit


def _report_line_map(report_data, report) -> dict[str, dict]:
    lines = report_data.get("lines") if isinstance(report_data, dict) else None
    if not isinstance(lines, list):
        report.error("management-report.json: lines must be an array")
        return {}
    result: dict[str, dict] = {}
    required = {
        "line_id", "financial_amount", "management_adjustment", "management_amount",
        "budget_amount", "variance_amount", "currency", "source_entry_count", "data_status",
    }
    for index, line in enumerate(lines, start=1):
        if not isinstance(line, dict):
            report.error(f"management-report.json line #{index}: must be an object")
            continue
        missing = sorted(required - set(line))
        if missing:
            report.error(f"management-report.json line #{index}: missing {', '.join(missing)}")
        line_id = str(line.get("line_id", "")).strip()
        if not line_id or line_id in result:
            report.error(f"management-report.json: blank or duplicate line_id {line_id!r}")
        result[line_id] = line
    if set(result) != set(ALL_LINE_IDS):
        report.error("management-report.json: lines must contain the complete fixed P&L line set exactly once")
    return result


def _validate_adjustments(
    rows, report_id: str, period_start, period_end, policy_statuses: dict[str, str], coa, report
) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    totals = defaultdict(lambda: Decimal("0"))
    account_totals = defaultdict(lambda: Decimal("0"))
    reclassification_total = Decimal("0")
    seen: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        adjustment_id = str(row.get("adjustment_id", "")).strip()
        if not adjustment_id or adjustment_id in seen:
            report.error(f"management-adjustments.csv row {row_number}: blank or duplicate adjustment_id")
        seen.add(adjustment_id)
        if str(row.get("report_id", "")).strip() != report_id:
            report.error(f"management-adjustments.csv row {row_number}: report_id mismatch")
        if str(row.get("period_start", "")).strip() != str(period_start) or str(row.get("period_end", "")).strip() != str(period_end):
            report.error(f"management-adjustments.csv row {row_number}: period must exactly match the report")
        line_id = str(row.get("line_id", "")).strip()
        if line_id not in BASE_LINE_IDS:
            report.error(f"management-adjustments.csv row {row_number}: line_id must be a base P&L line")
        amount = decimal_value(row.get("amount"), f"management-adjustments.csv row {row_number} amount", report)
        totals[line_id] += amount
        account_code = str(row.get("account_code", "")).strip()
        account = coa.get(account_code)
        if not account or str(account.get("pnl_category", "")).upper() == "NON_PNL":
            report.error(f"management-adjustments.csv row {row_number}: account_code must identify a P&L source account")
        account_totals[account_code] += amount
        adjustment_type = str(row.get("adjustment_type", "")).upper()
        if adjustment_type == "RECLASSIFICATION":
            reclassification_total += amount
        elif adjustment_type != "NON_GAAP_ADJUSTMENT":
            report.error(f"management-adjustments.csv row {row_number}: invalid adjustment_type")
        for field in ("reason", "policy_id", "source_locator", "approved_by"):
            if not str(row.get(field, "")).strip():
                report.error(f"management-adjustments.csv row {row_number}: {field} is required")
        policy_id = str(row.get("policy_id", "")).strip()
        if policy_statuses.get(policy_id) not in APPROVED_POLICY_STATUSES:
            report.error(f"management-adjustments.csv row {row_number}: policy is not owner-confirmed or professionally reviewed")
        if str(row.get("status", "")).upper() != "APPROVED":
            report.error(f"management-adjustments.csv row {row_number}: status must be APPROVED")
    if abs(reclassification_total) > TOLERANCE:
        report.error("management-adjustments.csv: RECLASSIFICATION adjustments must net to zero")
    return dict(totals), dict(account_totals)


def _validate_budget(
    rows,
    budget_status: str,
    budget_source_ids,
    period_start,
    period_end,
    reporting_currency: str,
    report,
):
    if not isinstance(budget_source_ids, list):
        report.error("management-report.json: budget_source_ids must be an array")
        budget_source_ids = []
    matching = []
    seen_ids: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        budget_id = str(row.get("budget_id", "")).strip()
        if not budget_id or budget_id in seen_ids:
            report.error(f"budgets.csv row {row_number}: blank or duplicate budget_id")
        seen_ids.add(budget_id)
        row_start = _parse_date(row.get("period_start"), f"budgets.csv row {row_number} period_start", report)
        row_end = _parse_date(row.get("period_end"), f"budgets.csv row {row_number} period_end", report)
        if row_start == period_start and row_end == period_end and not str(row.get("dimension_id", "")).strip():
            matching.append((row_number, row))

    if budget_status == "NOT_PROVIDED":
        if budget_source_ids:
            report.error("management-report.json: budget_source_ids must be empty when no budget is provided")
        return None

    if not matching:
        report.error("budgets.csv: PROVIDED budget requires approved company-total rows for the report period")
        return {line_id: Decimal("0") for line_id in ALL_LINE_IDS}
    matching_ids = {str(row.get("budget_id", "")).strip() for _, row in matching}
    if set(str(value) for value in budget_source_ids) != matching_ids:
        report.error("management-report.json: budget_source_ids do not match budgets.csv")
    base = {line_id: Decimal("0") for line_id in BASE_LINE_IDS}
    covered: set[str] = set()
    for row_number, row in matching:
        line_id = str(row.get("line_id", "")).strip()
        if line_id not in BASE_LINE_IDS:
            report.error(f"budgets.csv row {row_number}: line_id must be a base P&L line")
            continue
        if line_id in covered:
            report.error(f"budgets.csv: company-total base line {line_id} appears more than once")
        covered.add(line_id)
        if str(row.get("currency", "")).strip() != reporting_currency:
            report.error(f"budgets.csv row {row_number}: currency mismatch")
        for field in ("source_locator", "approved_by", "approved_at"):
            if not str(row.get(field, "")).strip():
                report.error(f"budgets.csv row {row_number}: {field} is required")
        if str(row.get("status", "")).upper() != "APPROVED":
            report.error(f"budgets.csv row {row_number}: status must be APPROVED")
        base[line_id] += decimal_value(row.get("amount"), f"budgets.csv row {row_number} amount", report)
    missing = sorted(set(BASE_LINE_IDS) - covered)
    if missing:
        report.error("budgets.csv: explicit company-total budget rows are required for " + ", ".join(missing))
    return derive_pnl_lines(base)


def _validate_dimensions(
    enabled_modules: set[str], config, dimensions, attributions, journal_amounts,
    adjustment_rows, dimension_summary, financial, management, report_id: str,
    allocation_policies: dict[str, dict], period_start, period_end, report,
) -> None:
    if "O6-DIMENSION" not in enabled_modules:
        return
    dimension_types = config.get("dimension_types", []) if isinstance(config, dict) else []
    if not isinstance(dimension_types, list) or not dimension_types:
        report.error("management-dashboard-config.json: O6-DIMENSION requires dimension_types")
        return
    active_dimensions = {
        (str(row.get("dimension_type", "")).strip(), str(row.get("dimension_id", "")).strip()): str(row.get("dimension_name", "")).strip()
        for row in dimensions
        if str(row.get("status", "")).upper() == "ACTIVE"
    }
    dimension_ids_seen: set[str] = set()
    dimension_id_to_key: dict[str, tuple[str, str]] = {}
    for dimension_key in active_dimensions:
        dimension_id = dimension_key[1]
        if dimension_id in dimension_ids_seen:
            report.error(f"dimensions.csv: dimension_id {dimension_id!r} must be globally unique")
        dimension_ids_seen.add(dimension_id)
        dimension_id_to_key[dimension_id] = dimension_key
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    attribution_ids: set[str] = set()
    for row_number, row in enumerate(attributions, start=2):
        attribution_id = str(row.get("attribution_id", "")).strip()
        if not attribution_id or attribution_id in attribution_ids:
            report.error(f"management-attribution.csv row {row_number}: blank or duplicate attribution_id")
        attribution_ids.add(attribution_id)
        if str(row.get("report_id", "")).strip() != report_id:
            report.error(f"management-attribution.csv row {row_number}: report_id mismatch")
        key = (
            str(row.get("entry_id", "")).strip(),
            str(row.get("line_no", "")).strip(),
            str(row.get("dimension_type", "")).strip(),
        )
        grouped[key].append(row)
        if (key[0], key[1]) not in journal_amounts:
            report.error(f"management-attribution.csv row {row_number}: journal P&L line is missing or outside report period")
        dimension_key = (key[2], str(row.get("dimension_id", "")).strip())
        if dimension_key not in active_dimensions:
            report.error(f"management-attribution.csv row {row_number}: dimension is missing or inactive")
        attribution_type = str(row.get("attribution_type", "")).upper()
        policy_id = str(row.get("allocation_policy_id", "")).strip()
        if attribution_type == "ALLOCATED" and (
            policy_id not in allocation_policies
            or allocation_policies[policy_id].get("status") not in APPROVED_POLICY_STATUSES
        ):
            report.error(f"management-attribution.csv row {row_number}: allocated amount requires an approved policy")
        elif attribution_type == "ALLOCATED":
            policy = allocation_policies[policy_id]
            detail = journal_amounts.get((key[0], key[1]))
            if policy.get("target_dimension_type") != key[2]:
                report.error(f"management-attribution.csv row {row_number}: policy target_dimension_type mismatch")
            if detail and detail[2] not in policy.get("source_cost_pool", []):
                report.error(f"management-attribution.csv row {row_number}: source account is outside policy cost pool")
            if detail and detail[0] not in {"COST_OF_SALES", "OPERATING_EXPENSE"}:
                report.error(f"management-attribution.csv row {row_number}: allocation policy may only allocate cost lines")
            effective_from = _parse_date(policy.get("effective_from"), f"allocation policy {policy_id} effective_from", report)
            effective_to = _parse_date(policy.get("effective_to"), f"allocation policy {policy_id} effective_to", report) if str(policy.get("effective_to", "")).strip() else None
            if effective_from and period_start and effective_from > period_start:
                report.error(f"management-attribution.csv row {row_number}: policy was not effective at period start")
            if effective_to and period_end and effective_to < period_end:
                report.error(f"management-attribution.csv row {row_number}: policy expired before period end")
        if attribution_type == "DIRECT" and policy_id:
            report.error(f"management-attribution.csv row {row_number}: DIRECT attribution must not cite allocation policy")
        if attribution_type not in {"DIRECT", "ALLOCATED", "UNALLOCATED", "UNASSIGNED"}:
            report.error(f"management-attribution.csv row {row_number}: invalid attribution_type")
        if not str(row.get("source_locator", "")).strip():
            report.error(f"management-attribution.csv row {row_number}: source_locator is required")
        if str(row.get("status", "")).upper() != "APPROVED":
            report.error(f"management-attribution.csv row {row_number}: status must be APPROVED")

    for journal_key, detail in journal_amounts.items():
        entry_id, line_no = journal_key
        _, source_amount, _ = detail
        for dimension_type in dimension_types:
            rows = grouped.get((entry_id, line_no, str(dimension_type)), [])
            if not rows:
                report.error(f"management-attribution.csv: missing {dimension_type} attribution for {entry_id}/{line_no}")
                continue
            ratio_total = sum(
                (decimal_value(row.get("ratio"), f"attribution {entry_id}/{line_no} ratio", report) for row in rows),
                Decimal("0"),
            )
            amount_total = sum(
                (decimal_value(row.get("amount"), f"attribution {entry_id}/{line_no} amount", report) for row in rows),
                Decimal("0"),
            )
            if abs(ratio_total - Decimal("1")) > RATIO_TOLERANCE:
                report.error(f"management-attribution.csv: ratios for {entry_id}/{line_no}/{dimension_type} do not total 1")
            if abs(amount_total - source_amount) > TOLERANCE:
                report.error(f"management-attribution.csv: amounts for {entry_id}/{line_no}/{dimension_type} do not reconcile")
            for row in rows:
                ratio = decimal_value(row.get("ratio"), f"attribution {entry_id}/{line_no} ratio", report)
                amount = decimal_value(row.get("amount"), f"attribution {entry_id}/{line_no} amount", report)
                if ratio < 0 or ratio > 1:
                    report.error(f"management-attribution.csv: ratio for {entry_id}/{line_no}/{dimension_type} must be between 0 and 1")
                if abs(amount - source_amount * ratio) > TOLERANCE:
                    report.error(f"management-attribution.csv: amount for {entry_id}/{line_no}/{dimension_type} does not equal source times ratio")

    base_by_dimension: dict[tuple[str, str], dict[str, Decimal]] = defaultdict(
        lambda: {line_id: Decimal("0") for line_id in BASE_LINE_IDS}
    )
    for (entry_id, line_no, dimension_type), rows in grouped.items():
        detail = journal_amounts.get((entry_id, line_no))
        if not detail or dimension_type not in dimension_types:
            continue
        line_id, _, _ = detail
        for row in rows:
            dimension_id = str(row.get("dimension_id", "")).strip()
            base_by_dimension[(dimension_type, dimension_id)][line_id] += decimal_value(
                row.get("amount"),
                f"management-attribution.csv {entry_id}/{line_no}/{dimension_type}/{dimension_id} amount",
                report,
            )

    adjustment_base_by_dimension: dict[tuple[str, str], dict[str, Decimal]] = defaultdict(
        lambda: {line_id: Decimal("0") for line_id in BASE_LINE_IDS}
    )
    for row_number, row in enumerate(adjustment_rows, start=2):
        amount = decimal_value(row.get("amount"), f"management-adjustments.csv row {row_number} amount", report)
        if abs(amount) <= TOLERANCE:
            continue
        dimension_id = str(row.get("dimension_id", "")).strip()
        dimension_key = dimension_id_to_key.get(dimension_id)
        if not dimension_key or dimension_key[0] not in dimension_types:
            report.error(f"management-adjustments.csv row {row_number}: O6-DIMENSION requires a valid enabled dimension_id")
            continue
        line_id = str(row.get("line_id", "")).strip()
        if line_id in BASE_LINE_IDS:
            adjustment_base_by_dimension[dimension_key][line_id] += amount

    if not isinstance(dimension_summary, list):
        report.error("management-report.json: dimension_summary must be an array")
        return
    summaries: dict[tuple[str, str], dict] = {}
    for index, item in enumerate(dimension_summary, start=1):
        if not isinstance(item, dict):
            report.error(f"management-report.json dimension #{index}: must be an object")
            continue
        key = (str(item.get("dimension_type", "")).strip(), str(item.get("dimension_id", "")).strip())
        if key in summaries:
            report.error(f"management-report.json: duplicate dimension summary {key}")
        summaries[key] = item
        if key not in active_dimensions:
            report.error(f"management-report.json dimension #{index}: dimension is missing or inactive")
        elif str(item.get("dimension_name", "")).strip() != active_dimensions[key]:
            report.error(f"management-report.json dimension #{index}: dimension_name mismatch")
        financial_amounts = item.get("financial_amounts")
        management_adjustments = item.get("management_adjustments")
        management_amounts = item.get("management_amounts")
        if not all(
            isinstance(values, dict) and set(values) == set(ALL_LINE_IDS)
            for values in (financial_amounts, management_adjustments, management_amounts)
        ):
            report.error(f"management-report.json dimension #{index}: all financial, adjustment, and management maps must contain every P&L line")
            continue
        expected_financial = derive_pnl_lines(base_by_dimension.get(key, {}))
        managed_base = {
            line_id: base_by_dimension.get(key, {}).get(line_id, Decimal("0"))
            + adjustment_base_by_dimension.get(key, {}).get(line_id, Decimal("0"))
            for line_id in BASE_LINE_IDS
        }
        expected_management = derive_pnl_lines(managed_base)
        for line_id in ALL_LINE_IDS:
            reported_financial = decimal_value(financial_amounts.get(line_id), f"management-report.json dimension #{index} financial {line_id}", report)
            reported_adjustment = decimal_value(management_adjustments.get(line_id), f"management-report.json dimension #{index} adjustment {line_id}", report)
            reported_management = decimal_value(management_amounts.get(line_id), f"management-report.json dimension #{index} management {line_id}", report)
            expected_adjustment = expected_management[line_id] - expected_financial[line_id]
            if abs(reported_financial - expected_financial[line_id]) > TOLERANCE:
                report.error(f"management-report.json dimension #{index}: financial {line_id} does not recompute")
            if abs(reported_adjustment - expected_adjustment) > TOLERANCE:
                report.error(f"management-report.json dimension #{index}: adjustment {line_id} does not recompute")
            if abs(reported_management - expected_management[line_id]) > TOLERANCE:
                report.error(f"management-report.json dimension #{index}: management {line_id} does not recompute")
        if str(item.get("data_status", "")).upper() != "COMPLETE":
            report.error(f"management-report.json dimension #{index}: data_status must be COMPLETE")

    required_dimension_summaries = set(base_by_dimension) | set(adjustment_base_by_dimension)
    if set(summaries) != required_dimension_summaries:
        report.error("management-report.json: dimension_summary must include every attributed dimension exactly once")
    for dimension_type in dimension_types:
        for line_id in ALL_LINE_IDS:
            financial_total = Decimal("0")
            adjustment_total = Decimal("0")
            management_total = Decimal("0")
            for (summary_type, _), item in summaries.items():
                if summary_type == dimension_type:
                    financial_total += decimal_value(item.get("financial_amounts", {}).get(line_id), f"dimension financial total {dimension_type} {line_id}", report)
                    adjustment_total += decimal_value(item.get("management_adjustments", {}).get(line_id), f"dimension adjustment total {dimension_type} {line_id}", report)
                    management_total += decimal_value(item.get("management_amounts", {}).get(line_id), f"dimension management total {dimension_type} {line_id}", report)
            if abs(financial_total - financial[line_id]) > TOLERANCE:
                report.error(f"management-report.json: {dimension_type} financial total for {line_id} does not reconcile to company")
            if abs(adjustment_total - (management[line_id] - financial[line_id])) > TOLERANCE:
                report.error(f"management-report.json: {dimension_type} adjustment total for {line_id} does not reconcile to company")
            if abs(management_total - management[line_id]) > TOLERANCE:
                report.error(f"management-report.json: {dimension_type} management total for {line_id} does not reconcile to company")


def validate_management_reporting(
    pack_dir: Path,
    stage: str,
    profile,
    feature_selection,
    policy_data,
    allocation_policy_data,
    manifest,
    definition,
    config,
    management_report,
    csv_rows: dict[str, list[dict[str, str]]],
    report,
) -> None:
    """Validate management reporting structure and, for O6 close, lineage."""
    validate_definition(definition, report)
    allocation_policies = validate_allocation_policies(allocation_policy_data, report)
    enabled = o6_is_enabled(feature_selection)
    enabled_modules = validate_dashboard_config(config, stage, enabled, report)
    if not enabled or stage != "close":
        return
    if not isinstance(definition, dict):
        return

    if not isinstance(management_report, dict):
        report.error("management-report.json: must be an object")
        return
    if management_report.get("schema_version") != "1.0":
        report.error("management-report.json: schema_version must be '1.0'")
    if management_report.get("definition_id") != "OWNER-PNL-BASE":
        report.error("management-report.json: definition_id mismatch")
    if management_report.get("definition_version") != definition.get("definition_version"):
        report.error("management-report.json: definition_version mismatch")
    revision = management_report.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        report.error("management-report.json: revision must be an integer >= 1")
    if management_report.get("basis") != "ACCRUAL":
        report.error("management-report.json: basis must be ACCRUAL")
    status = str(management_report.get("status", ""))
    if status not in ALLOWED_REPORT_STATUSES:
        report.error("management-report.json: invalid status")
    if status not in {"OWNER_APPROVED_MANAGEMENT", "PROFESSIONALLY_REVIEWED"}:
        report.error("management-report.json: close requires owner-approved management or professionally reviewed status")
    professional_review = management_report.get("professional_review")
    if not isinstance(professional_review, dict):
        report.error("management-report.json: professional_review must be an object")
    elif status == "PROFESSIONALLY_REVIEWED":
        if professional_review.get("status") != "REVIEWED":
            report.error("management-report.json: professionally reviewed status requires REVIEWED evidence")
        for field in ("reviewer_id", "qualification_or_role", "conclusion_reference", "conclusion_sha256", "reviewed_at"):
            if not str(professional_review.get(field, "")).strip():
                report.error(f"management-report.json professional_review: {field} is required")
        scope = professional_review.get("scope")
        required_scope = {
            "report_id": management_report.get("report_id"),
            "revision": management_report.get("revision"),
            "period_start": management_report.get("period_start"),
            "period_end": management_report.get("period_end"),
            "ledger_sha256": management_report.get("ledger_sha256"),
        }
        if not isinstance(scope, dict):
            report.error("management-report.json professional_review: scope must be a structured object")
        else:
            for field, expected in required_scope.items():
                if scope.get(field) != expected:
                    report.error(
                        f"management-report.json professional_review: scope {field} does not match report"
                    )
            covered_areas = scope.get("covered_areas")
            if not isinstance(covered_areas, list) or not covered_areas:
                report.error("management-report.json professional_review: scope covered_areas must be non-empty")
            else:
                normalized_areas = {
                    str(area).strip().upper() for area in covered_areas if str(area).strip()
                }
                expected_areas = set(BASE_FULL_REVIEW_AREAS)
                expected_areas.update(
                    area for module_id, area in OPTIONAL_REVIEW_AREAS.items()
                    if module_id in enabled_modules
                )
                if len(normalized_areas) != len(covered_areas):
                    report.error("management-report.json professional_review: scope covered_areas must be unique, non-empty IDs")
                if normalized_areas != expected_areas:
                    report.error(
                        "management-report.json professional_review: global PROFESSIONALLY_REVIEWED status requires exactly the full enabled report scope "
                        + ", ".join(sorted(expected_areas))
                    )
        reviewed_at = None
        try:
            reviewed_at = datetime.fromisoformat(
                str(professional_review.get("reviewed_at", "")).replace("Z", "+00:00")
            )
            if reviewed_at.utcoffset() is None:
                raise ValueError
        except ValueError:
            report.error("management-report.json professional_review: reviewed_at must be a timezone-aware ISO date-time")
        generated_at = None
        try:
            generated_at = datetime.fromisoformat(
                str(management_report.get("generated_at", "")).replace("Z", "+00:00")
            )
            if generated_at.utcoffset() is None:
                raise ValueError
        except ValueError:
            report.error("management-report.json: generated_at must be a timezone-aware ISO date-time for professional review")
        review_period_end = None
        try:
            review_period_end = date.fromisoformat(str(management_report.get("period_end", "")))
        except ValueError:
            pass
        if reviewed_at and review_period_end and reviewed_at.date() < review_period_end:
            report.error("management-report.json professional_review: reviewed_at cannot be before period_end")
        if reviewed_at and generated_at and reviewed_at > generated_at:
            report.error("management-report.json professional_review: reviewed_at cannot be after generated_at")
        reviewer_id = str(professional_review.get("reviewer_id", "")).strip()
        advisors = {
            str(item.get("advisor_id", "")).strip(): item
            for item in profile.get("professional_advisors", [])
            if isinstance(profile, dict) and isinstance(item, dict)
        } if isinstance(profile, dict) else {}
        advisor = advisors.get(reviewer_id)
        if not advisor or str(advisor.get("status", "")).upper() != "ACTIVE":
            report.error("management-report.json professional_review: reviewer is not an active confirmed advisor")
        elif str(advisor.get("qualification_or_role", "")).strip() != str(professional_review.get("qualification_or_role", "")).strip():
            report.error("management-report.json professional_review: qualification does not match company profile")
        elif not str(advisor.get("verification_source", "")).strip() or not str(advisor.get("verified_at", "")).strip():
            report.error("company-profile.json: professional advisor requires verification source and date")
        elif reviewed_at:
            advisor_verified_at = None
            raw_verified_at = str(advisor.get("verified_at", "")).strip()
            try:
                advisor_verified_at = date.fromisoformat(raw_verified_at)
            except ValueError:
                try:
                    verified_datetime = datetime.fromisoformat(raw_verified_at.replace("Z", "+00:00"))
                    advisor_verified_at = verified_datetime.date()
                except ValueError:
                    report.error("company-profile.json: professional advisor verified_at must be an ISO date or date-time")
            if advisor_verified_at and advisor_verified_at > reviewed_at.date():
                report.error("company-profile.json: professional advisor cannot be verified after reviewed_at")
        if management_report.get("prepared_by") == reviewer_id or management_report.get("approved_by") != reviewer_id:
            report.error("management-report.json professional_review: preparer and professional reviewer must be separated, and reviewer must approve")
        conclusion_reference = str(professional_review.get("conclusion_reference", "")).strip()
        evidence = next(
            (
                row for row in csv_rows.get("evidence-register.csv", [])
                if str(row.get("document_id", "")).strip() == conclusion_reference
            ),
            None,
        )
        if not evidence:
            report.error("management-report.json professional_review: conclusion_reference is missing from evidence-register.csv")
        else:
            if str(evidence.get("document_type", "")).upper() not in {"PROFESSIONAL_CONCLUSION", "ACCOUNTANT_REVIEW", "CPA_REVIEW"}:
                report.error("management-report.json professional_review: evidence document_type is not a professional conclusion")
            if str(evidence.get("completeness_status", "")).upper() not in {"COMPLETE", "SUFFICIENT", "VERIFIED"}:
                report.error("management-report.json professional_review: conclusion evidence is incomplete")
            conclusion_sha256 = str(professional_review.get("conclusion_sha256", "")).lower()
            if not re.fullmatch(r"[0-9a-f]{64}", conclusion_sha256):
                report.error("management-report.json professional_review: conclusion_sha256 must be 64 hex characters")
            if conclusion_sha256 != str(evidence.get("content_sha256", "")).lower():
                report.error("management-report.json professional_review: conclusion checksum does not match evidence register")
            source_locator = str(evidence.get("source_locator", "")).strip()
            conclusion_path = None
            if not source_locator:
                report.error("management-report.json professional_review: conclusion source_locator is required")
            else:
                candidate = (pack_dir / source_locator).resolve()
                try:
                    candidate.relative_to(pack_dir.resolve())
                    conclusion_path = candidate
                except ValueError:
                    report.error("management-report.json professional_review: conclusion source must stay inside the company pack")
            if conclusion_path is not None:
                if not conclusion_path.is_file():
                    report.error("management-report.json professional_review: conclusion source file does not exist")
                elif hashlib.sha256(conclusion_path.read_bytes()).hexdigest() != conclusion_sha256:
                    report.error("management-report.json professional_review: conclusion source bytes do not match checksum")
            document_date = None
            try:
                document_date = date.fromisoformat(str(evidence.get("document_date", "")).strip())
            except ValueError:
                report.error("management-report.json professional_review: conclusion document_date must be an ISO date")
            if document_date and review_period_end and document_date < review_period_end:
                report.error("management-report.json professional_review: conclusion document_date cannot be before period_end")
            if document_date and reviewed_at and document_date > reviewed_at.date():
                report.error("management-report.json professional_review: conclusion document_date cannot be after reviewed_at")
    elif professional_review.get("status") == "REVIEWED":
        report.error("management-report.json: REVIEWED evidence and report status are inconsistent")
    for field in ("report_id", "period_start", "period_end", "as_of", "functional_currency", "reporting_currency", "ledger_version", "ledger_sha256", "prepared_by", "approved_by", "generated_at"):
        if not str(management_report.get(field, "")).strip():
            report.error(f"management-report.json: {field} is required for close")

    period_start = _parse_date(management_report.get("period_start"), "management-report.json period_start", report)
    period_end = _parse_date(management_report.get("period_end"), "management-report.json period_end", report)
    as_of = _parse_date(management_report.get("as_of"), "management-report.json as_of", report)
    if period_start and period_end and period_start > period_end:
        report.error("management-report.json: period_start is after period_end")
    if as_of and period_end and as_of < period_end:
        report.error("management-report.json: as_of cannot be before period_end")

    functional_currency = str(management_report.get("functional_currency", "")).strip()
    reporting_currency = str(management_report.get("reporting_currency", "")).strip()
    if isinstance(profile, dict):
        expected_functional = str(profile.get("functional_currency", "")).strip()
        expected_reporting = str(profile.get("reporting_currency", "") or expected_functional).strip()
        if functional_currency != expected_functional:
            report.error("management-report.json: functional_currency does not match company-profile.json")
        if reporting_currency != expected_reporting:
            report.error("management-report.json: reporting_currency does not match company-profile.json")
    if isinstance(config, dict) and str(config.get("display_currency", "")).strip() != reporting_currency:
        report.error("management-dashboard-config.json: display_currency does not match report")
    if reporting_currency != functional_currency:
        report.error("management-report.json: v1.3 supports only reporting_currency equal to functional_currency")

    journal_path = pack_dir / "journal.csv"
    journal_rows = csv_rows.get("journal.csv", [])
    if not journal_path.is_file():
        return
    actual_hash = hashlib.sha256(journal_path.read_bytes()).hexdigest()
    if management_report.get("ledger_sha256") != actual_hash:
        report.error("management-report.json: ledger_sha256 does not match journal.csv")
    if management_report.get("journal_line_count") != len(journal_rows):
        report.error("management-report.json: journal_line_count does not match journal.csv")
    checksum_paths = {
        "company_profile_sha256": "company-profile.json",
        "chart_of_accounts_sha256": "chart-of-accounts.csv",
        "policy_register_sha256": "accounting-policy-register.json",
        "definition_sha256": "management-report-definition.json",
        "dashboard_config_sha256": "management-dashboard-config.json",
        "dimensions_sha256": "dimensions.csv",
        "attribution_sha256": "management-attribution.csv",
        "adjustments_sha256": "management-adjustments.csv",
        "allocation_policies_sha256": "allocation-policy-register.json",
        "budgets_sha256": "budgets.csv",
        "renderer_sha256": None,
        "evidence_register_sha256": "evidence-register.csv",
        "open_items_sha256": "open-items.csv",
    }
    source_checksums = management_report.get("source_checksums")
    if not isinstance(source_checksums, dict) or set(source_checksums) != set(checksum_paths):
        report.error("management-report.json: source_checksums must contain the complete source set")
    else:
        for checksum_field, filename in checksum_paths.items():
            source_path = (
                Path(__file__).resolve().with_name("render_management_dashboard.py")
                if filename is None
                else pack_dir / filename
            )
            if not source_path.is_file():
                report.error(f"management-report.json: checksum source is missing: {filename or 'render_management_dashboard.py'}")
                continue
            expected_checksum = hashlib.sha256(source_path.read_bytes()).hexdigest()
            if source_checksums.get(checksum_field) != expected_checksum:
                report.error(f"management-report.json: {checksum_field} does not match {filename or 'render_management_dashboard.py'}")
    if isinstance(manifest, dict):
        if manifest.get("management_report_revision") != management_report.get("revision"):
            report.error("version-manifest.json: management_report_revision does not match report")
        if manifest.get("management_report_status") != management_report.get("status"):
            report.error("version-manifest.json: management_report_status does not match report")
        if manifest.get("management_report_ledger_sha256") != actual_hash:
            report.error("version-manifest.json: management_report_ledger_sha256 does not match journal.csv")

    coa_rows = csv_rows.get("chart-of-accounts.csv", [])
    coa = {}
    for row_number, row in enumerate(coa_rows, start=2):
        code = str(row.get("account_code", "")).strip()
        category = str(row.get("pnl_category", "")).upper()
        if category not in ALLOWED_PNL_CATEGORIES:
            report.error(f"chart-of-accounts.csv row {row_number}: invalid or blank pnl_category")
        if category in CATEGORY_TO_LINE and str(row.get("pnl_line_id", "")).strip() != CATEGORY_TO_LINE[category]:
            report.error(f"chart-of-accounts.csv row {row_number}: pnl_line_id does not match pnl_category")
        if category == "NON_PNL" and str(row.get("pnl_line_id", "")).strip():
            report.error(f"chart-of-accounts.csv row {row_number}: NON_PNL account must not have pnl_line_id")
        account_type = str(row.get("account_type", "")).lower()
        if account_type in {"asset", "liability", "equity"} and category != "NON_PNL":
            report.error(f"chart-of-accounts.csv row {row_number}: balance-sheet account cannot enter P&L")
        cash_classification = str(row.get("cash_classification", "")).upper()
        if cash_classification not in {"AVAILABLE_CASH", "RESTRICTED_CASH", "CASH_EQUIVALENT", "NON_CASH"}:
            report.error(f"chart-of-accounts.csv row {row_number}: invalid or blank cash_classification")
        if account_type != "asset" and cash_classification != "NON_CASH":
            report.error(f"chart-of-accounts.csv row {row_number}: non-asset account cannot be classified as cash")
        if category in {"COST_OF_SALES", "OPERATING_EXPENSE"}:
            allowed_cost_values = {
                "cost_traceability": {"DIRECT", "INDIRECT"},
                "cost_behavior": {"FIXED", "VARIABLE", "MIXED"},
            }
            if not str(row.get("cost_nature", "")).strip():
                report.error(f"chart-of-accounts.csv row {row_number}: cost_nature is required for cost accounts")
            for field, allowed in allowed_cost_values.items():
                if str(row.get(field, "")).upper() not in allowed:
                    report.error(f"chart-of-accounts.csv row {row_number}: invalid or blank {field}")
            cost_function = str(row.get("cost_function", "")).upper()
            if category == "COST_OF_SALES" and cost_function != "COST_OF_SALES":
                report.error(f"chart-of-accounts.csv row {row_number}: COGS requires COST_OF_SALES function")
            if category == "OPERATING_EXPENSE" and cost_function not in {"SALES", "ADMINISTRATION", "RESEARCH_DEVELOPMENT", "OTHER_OPERATING"}:
                report.error(f"chart-of-accounts.csv row {row_number}: operating expense has invalid function")
        if str(row.get("review_status", "")).strip() not in APPROVED_POLICY_STATUSES:
            report.error(f"chart-of-accounts.csv row {row_number}: close requires owner-confirmed or professionally reviewed classification")
        coa[code] = row

    base = {line_id: Decimal("0") for line_id in BASE_LINE_IDS}
    account_cost_amounts = defaultdict(lambda: Decimal("0"))
    journal_pnl_amounts: dict[tuple[str, str], tuple[str, Decimal, str]] = {}
    source_entries: dict[str, set[str]] = defaultdict(set)
    functional_totals: dict[str, list[Decimal]] = defaultdict(
        lambda: [Decimal("0"), Decimal("0")]
    )
    parsed_functional_sides: dict[tuple[str, str], tuple[Decimal, Decimal]] = {}
    for row_number, row in enumerate(journal_rows, start=2):
        if str(row.get("posting_status", "")).upper() != "POSTED":
            continue
        entry_date = _parse_date(row.get("entry_date"), f"journal.csv row {row_number} entry_date", report)
        if not entry_date or not as_of or entry_date > as_of:
            continue
        key = (str(row.get("entry_id", "")).strip(), str(row.get("line_no", "")).strip())
        functional_debit, functional_credit = _functional_sides(
            row, row_number, functional_currency, report
        )
        parsed_functional_sides[key] = (functional_debit, functional_credit)
        functional_totals[key[0]][0] += functional_debit
        functional_totals[key[0]][1] += functional_credit
    for entry_id, (functional_debit, functional_credit) in functional_totals.items():
        if abs(functional_debit - functional_credit) > TOLERANCE:
            report.error(f"journal entry {entry_id}: functional-currency amounts are out of balance")

    for row_number, row in enumerate(journal_rows, start=2):
        if str(row.get("posting_status", "")).upper() != "POSTED":
            continue
        entry_date = _parse_date(row.get("entry_date"), f"journal.csv row {row_number} entry_date", report)
        if not entry_date or not period_start or not period_end or not (period_start <= entry_date <= period_end):
            continue
        entry_id = str(row.get("entry_id", "")).strip()
        functional_debit, functional_credit = parsed_functional_sides.get(
            (entry_id, str(row.get("line_no", "")).strip()),
            (Decimal("0"), Decimal("0")),
        )
        account_code = str(row.get("account_code", "")).strip()
        account = coa.get(account_code)
        if not account:
            continue
        category = str(account.get("pnl_category", "")).upper()
        if category == "NON_PNL" or category not in CATEGORY_TO_LINE:
            continue
        line_id = CATEGORY_TO_LINE[category]
        amount = (
            functional_credit - functional_debit
            if category in INCOME_CATEGORIES
            else functional_debit - functional_credit
        )
        base[line_id] += amount
        source_entries[line_id].add(str(row.get("entry_id", "")).strip())
        journal_pnl_amounts[(str(row.get("entry_id", "")).strip(), str(row.get("line_no", "")).strip())] = (line_id, amount, account_code)
        if category in {"COST_OF_SALES", "OPERATING_EXPENSE"}:
            account_cost_amounts[account_code] += amount
    available_cash = Decimal("0")
    restricted_cash = Decimal("0")
    for row_number, row in enumerate(journal_rows, start=2):
        if str(row.get("posting_status", "")).upper() != "POSTED":
            continue
        entry_date = _parse_date(row.get("entry_date"), f"journal.csv row {row_number} entry_date", report)
        if not entry_date or not as_of or entry_date > as_of:
            continue
        account = coa.get(str(row.get("account_code", "")).strip(), {})
        cash_classification = str(account.get("cash_classification", "")).upper()
        if cash_classification not in {"AVAILABLE_CASH", "RESTRICTED_CASH", "CASH_EQUIVALENT"}:
            continue
        key = (str(row.get("entry_id", "")).strip(), str(row.get("line_no", "")).strip())
        debit, credit = parsed_functional_sides.get(key, (Decimal("0"), Decimal("0")))
        if cash_classification in {"AVAILABLE_CASH", "CASH_EQUIVALENT"}:
            available_cash += debit - credit
        else:
            restricted_cash += debit - credit

    financial = derive_pnl_lines(base)
    source_entries["NET_REVENUE"] = source_entries["GROSS_REVENUE"] | source_entries["REVENUE_DEDUCTIONS"]
    source_entries["GROSS_PROFIT"] = source_entries["NET_REVENUE"] | source_entries["COST_OF_SALES"]
    source_entries["OPERATING_PROFIT"] = source_entries["GROSS_PROFIT"] | source_entries["OPERATING_EXPENSE"]
    source_entries["PRETAX_PROFIT"] = source_entries["OPERATING_PROFIT"] | source_entries["OTHER_INCOME"] | source_entries["OTHER_EXPENSE"]
    source_entries["CONTINUING_PROFIT"] = source_entries["PRETAX_PROFIT"] | source_entries["INCOME_TAX"]
    source_entries["NET_PROFIT"] = source_entries["CONTINUING_PROFIT"] | source_entries["DISCONTINUED_OPERATIONS"]
    policy_statuses = _policy_statuses(policy_data)
    adjustments, adjustment_by_account = _validate_adjustments(
        csv_rows.get("management-adjustments.csv", []),
        str(management_report.get("report_id", "")).strip(),
        period_start,
        period_end,
        policy_statuses,
        coa,
        report,
    )
    management_base = {
        line_id: financial[line_id] + adjustments.get(line_id, Decimal("0"))
        for line_id in BASE_LINE_IDS
    }
    management = derive_pnl_lines(management_base)

    report_lines = _report_line_map(management_report, report)
    budget_status = str(management_report.get("budget_status", "")).upper()
    if budget_status not in {"NOT_PROVIDED", "PROVIDED"}:
        report.error("management-report.json: budget_status must be NOT_PROVIDED or PROVIDED")
    if "O6-BUDGET" in enabled_modules and budget_status != "PROVIDED":
        report.error("management-report.json: O6-BUDGET requires a provided, traceable budget")
    budget = _validate_budget(
        csv_rows.get("budgets.csv", []),
        budget_status,
        management_report.get("budget_source_ids"),
        period_start,
        period_end,
        reporting_currency,
        report,
    )
    for line_id in ALL_LINE_IDS:
        line = report_lines.get(line_id)
        if not line:
            continue
        actual_financial = decimal_value(line.get("financial_amount"), f"management-report.json {line_id} financial_amount", report)
        actual_adjustment = decimal_value(line.get("management_adjustment"), f"management-report.json {line_id} management_adjustment", report)
        actual_management = decimal_value(line.get("management_amount"), f"management-report.json {line_id} management_amount", report)
        if abs(actual_financial - financial[line_id]) > TOLERANCE:
            report.error(f"management-report.json {line_id}: financial_amount does not recompute from journal")
        expected_adjustment = management[line_id] - financial[line_id]
        if abs(actual_adjustment - expected_adjustment) > TOLERANCE:
            report.error(f"management-report.json {line_id}: management_adjustment does not bridge")
        if abs(actual_management - management[line_id]) > TOLERANCE:
            report.error(f"management-report.json {line_id}: management_amount does not recompute")
        if str(line.get("currency", "")).strip() != reporting_currency:
            report.error(f"management-report.json {line_id}: currency mismatch")
        if line.get("source_entry_count") != len(source_entries[line_id]):
            report.error(f"management-report.json {line_id}: source_entry_count mismatch")
        if str(line.get("data_status", "")).upper() != "COMPLETE":
            report.error(f"management-report.json {line_id}: close requires COMPLETE data_status")
        if budget_status == "NOT_PROVIDED" and (line.get("budget_amount") is not None or line.get("variance_amount") is not None):
            report.error(f"management-report.json {line_id}: budget and variance must be null when no budget exists")
        if budget_status == "PROVIDED" and budget is not None:
            budget_amount = decimal_value(line.get("budget_amount"), f"management-report.json {line_id} budget_amount", report)
            variance_amount = decimal_value(line.get("variance_amount"), f"management-report.json {line_id} variance_amount", report)
            if abs(budget_amount - budget[line_id]) > TOLERANCE:
                report.error(f"management-report.json {line_id}: budget_amount does not recompute")
            if abs(variance_amount - (actual_management - budget_amount)) > TOLERANCE:
                report.error(f"management-report.json {line_id}: variance_amount must equal management minus budget")

    validate_negative_gross_margin(financial, management_report.get("warnings"), report)

    cost_rows = management_report.get("cost_breakdown")
    if not isinstance(cost_rows, list):
        report.error("management-report.json: cost_breakdown must be an array")
        cost_rows = []
    reported_cost_total = Decimal("0")
    reported_cost_adjustment_total = Decimal("0")
    reported_management_cost_total = Decimal("0")
    seen_cost_accounts: set[str] = set()
    seen_cost_ids: set[str] = set()
    for index, item in enumerate(cost_rows, start=1):
        if not isinstance(item, dict):
            report.error(f"management-report.json cost #{index}: must be an object")
            continue
        required = {"cost_id", "account_code", "financial_amount", "management_adjustment", "management_amount", "cost_nature", "cost_behavior", "traceability", "data_status"}
        missing = sorted(required - set(item))
        if missing:
            report.error(f"management-report.json cost #{index}: missing {', '.join(missing)}")
        account_code = str(item.get("account_code", "")).strip()
        cost_id = str(item.get("cost_id", "")).strip()
        if not cost_id or cost_id in seen_cost_ids:
            report.error(f"management-report.json cost #{index}: blank or duplicate cost_id")
        seen_cost_ids.add(cost_id)
        if account_code in seen_cost_accounts:
            report.error(f"management-report.json: duplicate cost account {account_code}")
        seen_cost_accounts.add(account_code)
        amount = decimal_value(item.get("financial_amount"), f"management-report.json cost #{index} financial_amount", report)
        cost_adjustment = decimal_value(item.get("management_adjustment"), f"management-report.json cost #{index} management_adjustment", report)
        management_cost = decimal_value(item.get("management_amount"), f"management-report.json cost #{index} management_amount", report)
        reported_cost_total += amount
        reported_cost_adjustment_total += cost_adjustment
        reported_management_cost_total += management_cost
        if abs(management_cost - (amount + cost_adjustment)) > TOLERANCE:
            report.error(f"management-report.json cost {account_code}: management amount does not bridge")
        if abs(cost_adjustment - adjustment_by_account.get(account_code, Decimal("0"))) > TOLERANCE:
            report.error(f"management-report.json cost {account_code}: management adjustment does not trace to approved adjustment rows")
        if abs(amount - account_cost_amounts.get(account_code, Decimal("0"))) > TOLERANCE:
            report.error(f"management-report.json cost {account_code}: amount does not recompute")
        account = coa.get(account_code, {})
        if str(item.get("cost_nature", "")).strip() != str(account.get("cost_nature", "")).strip():
            report.error(f"management-report.json cost {account_code}: cost_nature mismatch")
        if str(item.get("cost_behavior", "")).strip() != str(account.get("cost_behavior", "")).strip():
            report.error(f"management-report.json cost {account_code}: cost_behavior mismatch")
        if str(item.get("traceability", "")).strip() != str(account.get("cost_traceability", "")).strip():
            report.error(f"management-report.json cost {account_code}: traceability mismatch")
        if str(item.get("data_status", "")).upper() != "COMPLETE":
            report.error(f"management-report.json cost {account_code}: close requires COMPLETE data_status")
    if set(account_cost_amounts) != seen_cost_accounts:
        report.error("management-report.json: cost_breakdown must contain every cost account exactly once")
    expected_cost_total = financial["COST_OF_SALES"] + financial["OPERATING_EXPENSE"]
    if abs(reported_cost_total - expected_cost_total) > TOLERANCE:
        report.error("management-report.json: cost_breakdown does not reconcile to COGS plus operating expenses")
    expected_cost_adjustment = (
        management["COST_OF_SALES"] + management["OPERATING_EXPENSE"] - expected_cost_total
    )
    if abs(reported_cost_adjustment_total - expected_cost_adjustment) > TOLERANCE:
        report.error("management-report.json: cost adjustments do not reconcile to management P&L")
    if abs(reported_management_cost_total - (management["COST_OF_SALES"] + management["OPERATING_EXPENSE"])) > TOLERANCE:
        report.error("management-report.json: management cost breakdown does not reconcile to management P&L")

    reconciliation = management_report.get("reconciliation")
    if not isinstance(reconciliation, dict):
        report.error("management-report.json: reconciliation must be an object")
    else:
        ledger_amount = decimal_value(reconciliation.get("ledger_pnl_amount"), "management-report.json reconciliation ledger_pnl_amount", report)
        reported_amount = decimal_value(reconciliation.get("reported_net_profit"), "management-report.json reconciliation reported_net_profit", report)
        difference = decimal_value(reconciliation.get("difference"), "management-report.json reconciliation difference", report)
        if abs(ledger_amount - financial["NET_PROFIT"]) > TOLERANCE or abs(reported_amount - financial["NET_PROFIT"]) > TOLERANCE:
            report.error("management-report.json: reconciliation amounts do not match recomputed net profit")
        if abs(difference - (reported_amount - ledger_amount)) > TOLERANCE or abs(difference) > TOLERANCE:
            report.error("management-report.json: reconciliation difference is not zero")
        if reconciliation.get("status") != "RECONCILED":
            report.error("management-report.json: reconciliation status must be RECONCILED")

    if management_report.get("missing_data"):
        report.error("management-report.json: close cannot pass with missing_data")

    cash_summary = management_report.get("cash_summary")
    if not isinstance(cash_summary, dict):
        report.error("management-report.json: cash_summary must be an object")
    elif "O6-CASH" in enabled_modules:
        if cash_summary.get("status") != "COMPLETE":
            report.error("management-report.json: O6-CASH requires COMPLETE cash_summary")
        reported_available = decimal_value(cash_summary.get("available_cash"), "management-report.json cash_summary available_cash", report)
        reported_restricted = decimal_value(cash_summary.get("restricted_cash"), "management-report.json cash_summary restricted_cash", report)
        if abs(reported_available - available_cash) > TOLERANCE:
            report.error("management-report.json cash_summary: available_cash does not recompute from ledger cash accounts")
        if abs(reported_restricted - restricted_cash) > TOLERANCE:
            report.error("management-report.json cash_summary: restricted_cash does not recompute from ledger cash accounts")
        for field in ("currency", "as_of", "basis", "source_locator"):
            if not str(cash_summary.get(field, "")).strip():
                report.error(f"management-report.json cash_summary: {field} is required")
        if cash_summary.get("currency") != reporting_currency:
            report.error("management-report.json cash_summary: currency mismatch")
        if cash_summary.get("as_of") != management_report.get("as_of"):
            report.error("management-report.json cash_summary: as_of mismatch")
        if cash_summary.get("basis") != "LEDGER_BALANCE_AS_OF":
            report.error("management-report.json cash_summary: basis must be LEDGER_BALANCE_AS_OF")
        if cash_summary.get("source_locator") != "journal.csv|chart-of-accounts.csv":
            report.error("management-report.json cash_summary: source_locator must identify the ledger and COA")
    elif cash_summary.get("status") != "NOT_ENABLED":
        report.error("management-report.json: cash_summary must be NOT_ENABLED unless O6-CASH is enabled")
    elif cash_summary.get("available_cash") is not None or cash_summary.get("restricted_cash") is not None:
        report.error("management-report.json: disabled cash view must not contain cash amounts")

    trust_summary = management_report.get("trust_summary")
    if not isinstance(trust_summary, list):
        report.error("management-report.json: trust_summary must be an array")
    elif "O6-TRUST" in enabled_modules and not trust_summary:
        report.error("management-report.json: O6-TRUST requires concrete trust checks")
    else:
        trust_items: dict[str, dict] = {}
        for index, item in enumerate(trust_summary, start=1):
            if not isinstance(item, dict):
                report.error(f"management-report.json trust item #{index}: must be an object")
                continue
            for field in ("check_id", "status", "count", "impact", "source_locator"):
                if field not in item or (field != "count" and not str(item.get(field, "")).strip()):
                    report.error(f"management-report.json trust item #{index}: {field} is required")
            if not isinstance(item.get("count"), int) or isinstance(item.get("count"), bool) or item.get("count", -1) < 0:
                report.error(f"management-report.json trust item #{index}: count must be an integer >= 0")
            check_id = str(item.get("check_id", "")).strip()
            if not check_id or check_id in trust_items:
                report.error(f"management-report.json trust item #{index}: blank or duplicate check_id")
            trust_items[check_id] = item
        if "O6-TRUST" in enabled_modules:
            missing_checks = sorted(REQUIRED_TRUST_CHECKS - set(trust_items))
            if missing_checks:
                report.error("management-report.json: trust_summary missing " + ", ".join(missing_checks))
            expected_counts = {
                "EVIDENCE_GAPS": sum(
                    1 for row in csv_rows.get("evidence-register.csv", [])
                    if str(row.get("completeness_status", "")).upper() not in {"COMPLETE", "SUFFICIENT", "VERIFIED"}
                ),
                "OPEN_ITEMS": sum(
                    1 for row in csv_rows.get("open-items.csv", [])
                    if str(row.get("status", "")).upper() not in {"ANSWERED", "CLOSED", "IMPLEMENTED", "RESOLVED"}
                ),
                "UNPOSTED_TRANSACTIONS": sum(
                    1 for row in journal_rows
                    if str(row.get("posting_status", "")).upper() != "POSTED"
                ),
                "UNCLASSIFIED_COST": sum(
                    1 for row in coa_rows
                    if str(row.get("pnl_category", "")).upper() in {"COST_OF_SALES", "OPERATING_EXPENSE"}
                    and any(str(row.get(field, "")).upper() in {"", "UNCLASSIFIED"} for field in ("cost_function", "cost_nature", "cost_traceability", "cost_behavior"))
                ),
                "REPORT_RECONCILIATION": 0 if isinstance(reconciliation, dict) and reconciliation.get("status") == "RECONCILED" else 1,
            }
            for check_id, expected_count in expected_counts.items():
                if check_id in trust_items and trust_items[check_id].get("count") != expected_count:
                    report.error(f"management-report.json trust {check_id}: count does not match source data")

    action_items = management_report.get("action_items")
    if not isinstance(action_items, list):
        report.error("management-report.json: action_items must be an array")
    else:
        mapped_open_items: set[str] = set()
        action_ids: set[str] = set()
        for index, item in enumerate(action_items, start=1):
            if not isinstance(item, dict):
                report.error(f"management-report.json action item #{index}: must be an object")
                continue
            for field in ("action_id", "priority", "action", "why", "owner", "due_date", "source_locator", "status"):
                if not str(item.get(field, "")).strip():
                    report.error(f"management-report.json action item #{index}: {field} is required")
            action_id = str(item.get("action_id", "")).strip()
            if action_id in action_ids:
                report.error(f"management-report.json action item #{index}: duplicate action_id")
            action_ids.add(action_id)
            open_item_id = str(item.get("open_item_id", "")).strip()
            if open_item_id:
                mapped_open_items.add(open_item_id)
        unresolved_open_items = {
            str(row.get("open_item_id", "")).strip()
            for row in csv_rows.get("open-items.csv", [])
            if str(row.get("status", "")).upper() not in {"ANSWERED", "CLOSED", "IMPLEMENTED", "RESOLVED"}
            and str(row.get("open_item_id", "")).strip()
        }
        missing_actions = sorted(unresolved_open_items - mapped_open_items)
        if missing_actions:
            report.error("management-report.json: action_items missing unresolved open items " + ", ".join(missing_actions))
    charts = management_report.get("charts", [])
    if contains_embedded_chart_values(charts):
        report.error("management-report.json: charts may not embed data or values")
    valid_chart_ids = {
        str(item.get("chart_id", ""))
        for item in definition.get("charts", [])
        if isinstance(item, dict)
    }
    cost_ids = {str(item.get("cost_id", "")) for item in cost_rows if isinstance(item, dict)}
    dimension_ids = {str(item.get("dimension_id", "")) for item in management_report.get("dimension_summary", []) if isinstance(item, dict)}
    if not isinstance(charts, list):
        report.error("management-report.json: charts must be an array")
        charts = []
    seen_chart_ids: set[str] = set()
    for index, chart in enumerate(charts, start=1):
        if not isinstance(chart, dict):
            report.error(f"management-report.json chart #{index}: must be an object")
            continue
        chart_id = str(chart.get("chart_id", ""))
        unexpected_chart_fields = sorted(set(chart) - {"chart_id", "line_ids", "cost_ids", "dimension_ids"})
        if unexpected_chart_fields:
            report.error(
                f"management-report.json chart #{index}: only ID references are allowed; unexpected {', '.join(unexpected_chart_fields)}"
            )
        if chart_id in seen_chart_ids:
            report.error(f"management-report.json chart #{index}: duplicate chart_id")
        seen_chart_ids.add(chart_id)
        if chart_id not in valid_chart_ids:
            report.error(f"management-report.json chart #{index}: unknown chart_id")
        for field, valid_ids in (("line_ids", set(ALL_LINE_IDS)), ("cost_ids", cost_ids), ("dimension_ids", dimension_ids)):
            if field in chart and not isinstance(chart.get(field), list):
                report.error(f"management-report.json chart #{index}: {field} must be an array")
                continue
            for ref in chart.get(field, []):
                if str(ref) not in valid_ids:
                    report.error(f"management-report.json chart #{index}: unknown {field} reference {ref!r}")
        if chart_id in {"PNL_WATERFALL", "PNL_TREND"} and not chart.get("line_ids"):
            report.error(f"management-report.json chart #{index}: {chart_id} requires line_ids")
        if chart_id == "COST_BARS" and cost_ids and not chart.get("cost_ids"):
            report.error(f"management-report.json chart #{index}: COST_BARS requires cost_ids")
        if budget_status == "NOT_PROVIDED" and "budget" in str(chart).lower():
            report.error(f"management-report.json chart #{index}: budget chart is forbidden without budget")
    required_chart_ids = set()
    if "O6-PROFIT" in enabled_modules:
        required_chart_ids.add("PNL_WATERFALL")
    if "O6-COST" in enabled_modules:
        required_chart_ids.add("COST_BARS")
    if "O6-TREND" in enabled_modules:
        required_chart_ids.add("PNL_TREND")
    missing_charts = sorted(required_chart_ids - seen_chart_ids)
    if missing_charts:
        report.error("management-report.json: missing enabled visual references " + ", ".join(missing_charts))

    _validate_dimensions(
        enabled_modules,
        config,
        csv_rows.get("dimensions.csv", []),
        csv_rows.get("management-attribution.csv", []),
        journal_pnl_amounts,
        csv_rows.get("management-adjustments.csv", []),
        management_report.get("dimension_summary"),
        financial,
        management,
        str(management_report.get("report_id", "")).strip(),
        allocation_policies,
        period_start,
        period_end,
        report,
    )

    dashboard_path = pack_dir / "management-dashboard.md"
    try:
        dashboard = dashboard_path.read_text(encoding="utf-8")
    except OSError:
        dashboard = ""
    expected_dashboard = render_management_dashboard(config, management_report)
    if dashboard != expected_dashboard:
        report.error(
            "management-dashboard.md: content is not the deterministic rendering of management-report.json; regenerate with render_management_dashboard.py"
        )
