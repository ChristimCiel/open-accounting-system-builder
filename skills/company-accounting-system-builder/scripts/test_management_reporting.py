#!/usr/bin/env python3
"""Forward and tamper tests for management-report validation."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from validate_management_reporting import (
    _validate_adjustments,
    _validate_dimensions,
    contains_embedded_chart_values,
    derive_pnl_lines,
    validate_management_reporting,
    validate_negative_gross_margin,
)
from render_management_dashboard import render_management_dashboard


class RecordingReport:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)


class ManagementReportingTests(unittest.TestCase):
    def test_fixed_pnl_math_preserves_profit_and_loss(self) -> None:
        profit = derive_pnl_lines({
            "GROSS_REVENUE": Decimal("1000"),
            "COST_OF_SALES": Decimal("600"),
            "OPERATING_EXPENSE": Decimal("200"),
        })
        self.assertEqual(profit["GROSS_PROFIT"], Decimal("400"))
        self.assertEqual(profit["NET_PROFIT"], Decimal("200"))

        loss = derive_pnl_lines({
            "GROSS_REVENUE": Decimal("100"),
            "COST_OF_SALES": Decimal("200"),
        })
        self.assertEqual(loss["GROSS_PROFIT"], Decimal("-100"))
        self.assertEqual(loss["NET_PROFIT"], Decimal("-100"))

    def test_chart_values_are_rejected_recursively(self) -> None:
        self.assertTrue(contains_embedded_chart_values({"series": [{"values": [1, 2]}]}))
        self.assertFalse(contains_embedded_chart_values({"line_ids": ["NET_REVENUE"]}))

    def test_negative_gross_margin_requires_visible_warning(self) -> None:
        report = RecordingReport()
        validate_negative_gross_margin({"GROSS_PROFIT": Decimal("-100")}, [], report)
        self.assertTrue(any("NEGATIVE_GROSS_MARGIN" in message for message in report.errors))

        cleared = RecordingReport()
        validate_negative_gross_margin(
            {"GROSS_PROFIT": Decimal("-100")},
            [{"code": "NEGATIVE_GROSS_MARGIN"}],
            cleared,
        )
        self.assertEqual(cleared.errors, [])

    def _fixture(self, pack_dir: Path):
        definition_path = Path(__file__).resolve().parents[1] / "assets" / "templates" / "management-report-definition.json"
        definition = json.loads(definition_path.read_text(encoding="utf-8"))
        journal_fields = [
            "entry_id", "line_no", "entry_date", "period", "economic_event_id",
            "account_code", "debit", "credit", "currency", "functional_debit",
            "functional_credit", "functional_amount", "fx_rate", "fx_source_ref",
            "dimension_project", "dimension_product", "dimension_channel",
            "dimension_location", "counterparty_id", "document_id", "policy_id",
            "posting_status", "prepared_by", "approved_by", "notes",
        ]
        journal_rows = []
        for entry_id, line_no, account, debit, credit in (
            ("JE-SALE", "1", "1000", "1000", ""),
            ("JE-SALE", "2", "4000", "", "1000"),
            ("JE-COST", "1", "5000", "600", ""),
            ("JE-COST", "2", "1000", "", "600"),
            ("JE-OPEX", "1", "6000", "200", ""),
            ("JE-OPEX", "2", "1000", "", "200"),
        ):
            row = {field: "" for field in journal_fields}
            row.update({
                "entry_id": entry_id,
                "line_no": line_no,
                "entry_date": "2026-08-31",
                "period": "2026-08",
                "economic_event_id": "EV-" + entry_id,
                "account_code": account,
                "debit": debit,
                "credit": credit,
                "currency": "TWD",
                "functional_debit": debit,
                "functional_credit": credit,
                "functional_amount": debit if debit else f"-{credit}",
                "document_id": "DOC-" + entry_id,
                "policy_id": "POL-BASE",
                "posting_status": "POSTED",
                "prepared_by": "synthetic-preparer",
                "approved_by": "synthetic-owner",
            })
            journal_rows.append(row)
        journal_path = pack_dir / "journal.csv"
        with journal_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=journal_fields)
            writer.writeheader()
            writer.writerows(journal_rows)
        ledger_hash = hashlib.sha256(journal_path.read_bytes()).hexdigest()

        coa_rows = [
            {"account_code": "1000", "account_type": "asset", "pnl_category": "NON_PNL", "pnl_line_id": "", "cost_function": "", "cost_nature": "", "cost_behavior": "", "cost_traceability": "", "cash_classification": "AVAILABLE_CASH", "review_status": "owner_confirmed"},
            {"account_code": "4000", "account_type": "revenue", "pnl_category": "REVENUE", "pnl_line_id": "GROSS_REVENUE", "cost_function": "", "cost_nature": "", "cost_behavior": "", "cost_traceability": "", "cash_classification": "NON_CASH", "review_status": "owner_confirmed"},
            {"account_code": "5000", "account_type": "expense", "pnl_category": "COST_OF_SALES", "pnl_line_id": "COST_OF_SALES", "cost_function": "COST_OF_SALES", "cost_nature": "Materials", "cost_behavior": "VARIABLE", "cost_traceability": "DIRECT", "cash_classification": "NON_CASH", "review_status": "owner_confirmed"},
            {"account_code": "6000", "account_type": "expense", "pnl_category": "OPERATING_EXPENSE", "pnl_line_id": "OPERATING_EXPENSE", "cost_function": "ADMINISTRATION", "cost_nature": "Administration", "cost_behavior": "FIXED", "cost_traceability": "INDIRECT", "cash_classification": "NON_CASH", "review_status": "owner_confirmed"},
        ]
        financial = derive_pnl_lines({
            "GROSS_REVENUE": Decimal("1000"),
            "COST_OF_SALES": Decimal("600"),
            "OPERATING_EXPENSE": Decimal("200"),
        })
        source_counts = {
            "GROSS_REVENUE": 1,
            "NET_REVENUE": 1,
            "COST_OF_SALES": 1,
            "GROSS_PROFIT": 2,
            "OPERATING_EXPENSE": 1,
            "OPERATING_PROFIT": 3,
            "PRETAX_PROFIT": 3,
            "CONTINUING_PROFIT": 3,
            "NET_PROFIT": 3,
        }
        report_lines = [{
            "line_id": line_id,
            "financial_amount": str(financial[line_id]),
            "management_adjustment": "0",
            "management_amount": str(financial[line_id]),
            "budget_amount": None,
            "variance_amount": None,
            "currency": "TWD",
            "source_entry_count": source_counts.get(line_id, 0),
            "data_status": "COMPLETE",
        } for line_id in financial]
        management_report = {
            "schema_version": "1.0",
            "report_id": "MR-2026-08",
            "definition_id": "OWNER-PNL-BASE",
            "definition_version": "1.0",
            "revision": 1,
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "as_of": "2026-08-31",
            "basis": "ACCRUAL",
            "functional_currency": "TWD",
            "reporting_currency": "TWD",
            "ledger_version": "synthetic-v1",
            "ledger_sha256": ledger_hash,
            "journal_line_count": len(journal_rows),
            "source_checksums": {},
            "status": "OWNER_APPROVED_MANAGEMENT",
            "budget_status": "NOT_PROVIDED",
            "budget_source_ids": [],
            "lines": report_lines,
            "cost_breakdown": [
                {"cost_id": "COST-5000", "account_code": "5000", "financial_amount": "600", "management_adjustment": "0", "management_amount": "600", "cost_nature": "Materials", "cost_behavior": "VARIABLE", "traceability": "DIRECT", "data_status": "COMPLETE"},
                {"cost_id": "COST-6000", "account_code": "6000", "financial_amount": "200", "management_adjustment": "0", "management_amount": "200", "cost_nature": "Administration", "cost_behavior": "FIXED", "traceability": "INDIRECT", "data_status": "COMPLETE"},
            ],
            "dimension_summary": [],
            "cash_summary": {"available_cash": None, "restricted_cash": None, "currency": "", "as_of": "", "basis": "SEPARATE_CASH_VIEW", "status": "NOT_ENABLED", "source_locator": "", "assumptions": []},
            "trust_summary": [
                {"check_id": check_id, "status": "CLEAR", "count": 0, "amount": "0", "impact": "No exceptions in synthetic data.", "source_locator": "test:control-source"}
                for check_id in ("EVIDENCE_GAPS", "OPEN_ITEMS", "UNPOSTED_TRANSACTIONS", "UNCLASSIFIED_COST", "REPORT_RECONCILIATION")
            ],
            "action_items": [],
            "reconciliation": {"ledger_pnl_amount": "200", "reported_net_profit": "200", "difference": "0", "status": "RECONCILED"},
            "missing_data": [],
            "warnings": [],
            "charts": [
                {"chart_id": "PNL_COLUMNS", "line_ids": ["NET_REVENUE", "GROSS_PROFIT", "OPERATING_PROFIT", "NET_PROFIT"]},
                {"chart_id": "PNL_BRIDGE_COLUMNS", "line_ids": ["NET_REVENUE", "COST_OF_SALES", "OPERATING_EXPENSE", "OTHER_INCOME", "OTHER_EXPENSE", "INCOME_TAX", "NET_PROFIT"]},
                {"chart_id": "COST_BARS", "cost_ids": ["COST-5000", "COST-6000"]},
                {"chart_id": "COST_DONUT", "cost_ids": ["COST-5000", "COST-6000"]},
            ],
            "prepared_by": "synthetic-preparer",
            "approved_by": "synthetic-owner",
            "professional_review": {
                "status": "NOT_REVIEWED",
                "reviewer_id": "",
                "qualification_or_role": "",
                "scope": {
                    "report_id": "",
                    "revision": 0,
                    "period_start": "",
                    "period_end": "",
                    "ledger_sha256": "",
                    "covered_areas": [],
                },
                "conclusion_reference": "",
                "conclusion_sha256": "",
                "reviewed_at": "",
            },
            "generated_at": "2026-08-31T23:59:00+08:00",
        }
        feature_selection = {"features": [{"feature_id": "O6", "source": "catalog", "lifecycle_status": "ENABLED"}]}
        modules = []
        for module in ("O6-DASH", "O6-PROFIT", "O6-COST", "O6-TRUST", "O6-CLOSE"):
            modules.append({"module_id": module, "status": "ENABLED", "recommendation": "AI_RECOMMENDED", "rationale": "Synthetic owner-reporting test."})
        config = {
            "schema_version": "1.0",
            "config_version": 1,
            "status": "OWNER_CONFIRMED",
            "reporting_cadence": "MONTHLY",
            "primary_basis": "ACCRUAL",
            "display_language": "zh-TW",
            "display_currency": "TWD",
            "comparisons": [],
            "dimension_types": [],
            "owner_questions": [
                {"question_id": "Q-DECISION", "question": "What decision?", "answer": "Cost control", "source_locator": "test:owner", "status": "ANSWERED"},
                {"question_id": "Q-DIMENSION", "question": "Which dimension?", "answer": "None", "source_locator": "test:owner", "status": "ANSWERED"},
                {"question_id": "Q-COMPARISON", "question": "Which comparison?", "answer": "Actual only", "source_locator": "test:owner", "status": "ANSWERED"},
                {"question_id": "Q-VISUAL", "question": "Which charts?", "answer": "P&L columns, P&L bridge columns, cost bars, cost doughnut", "source_locator": "test:owner", "status": "ANSWERED"},
            ],
            "visualizations": [
                {"visual_id": "VIZ-PNL-COLUMNS", "chart_id": "PNL_COLUMNS", "chart_type": "COLUMN", "status": "ENABLED", "recommendation": "AI_RECOMMENDED", "rationale": "Synthetic P&L comparison.", "requires_module": "O6-PROFIT"},
                {"visual_id": "VIZ-PNL-BRIDGE", "chart_id": "PNL_BRIDGE_COLUMNS", "chart_type": "COLUMN_BRIDGE", "status": "ENABLED", "recommendation": "AI_RECOMMENDED", "rationale": "Synthetic P&L bridge.", "requires_module": "O6-PROFIT"},
                {"visual_id": "VIZ-COST-BARS", "chart_id": "COST_BARS", "chart_type": "HORIZONTAL_BAR", "status": "ENABLED", "recommendation": "AI_RECOMMENDED", "rationale": "Synthetic cost ranking.", "requires_module": "O6-COST"},
                {"visual_id": "VIZ-COST-DONUT", "chart_id": "COST_DONUT", "chart_type": "DOUGHNUT", "status": "ENABLED", "recommendation": "OPTIONAL", "rationale": "Synthetic valid cost mix.", "requires_module": "O6-COST"},
                {"visual_id": "VIZ-DIMENSION-PROFIT", "chart_id": "DIMENSION_PROFIT_BARS", "chart_type": "COLUMN", "status": "DECLINED", "recommendation": "OPTIONAL", "rationale": "No dimension in base fixture.", "requires_module": "O6-DIMENSION"},
            ],
            "modules": modules,
            "selection_confirmation": {"status": "CONFIRMED", "confirmed_by": "synthetic-owner", "confirmed_at": "2026-08-31T00:00:00+08:00", "source_locator": "test:owner-confirmation"},
            "updated_at": "2026-08-31T00:00:00+08:00",
        }
        manifest = {
            "management_report_revision": 1,
            "management_report_status": "OWNER_APPROVED_MANAGEMENT",
            "management_report_ledger_sha256": ledger_hash,
        }
        profile = {
            "functional_currency": "TWD",
            "reporting_currency": "TWD",
            "professional_advisors": [],
        }
        source_payloads = {
            "company-profile.json": json.dumps(profile, ensure_ascii=False, sort_keys=True),
            "chart-of-accounts.csv": "synthetic chart of accounts\n",
            "accounting-policy-register.json": json.dumps({"policies": []}),
            "management-report-definition.json": json.dumps(definition, ensure_ascii=False, sort_keys=True),
            "management-dashboard-config.json": json.dumps(config, ensure_ascii=False, sort_keys=True),
            "dimensions.csv": "dimension_id,dimension_type,dimension_name,parent_id,status,effective_from,effective_to\n",
            "management-attribution.csv": "attribution_id,report_id,entry_id,line_no,dimension_type,dimension_id,attribution_type,ratio,amount,allocation_policy_id,source_locator,status\n",
            "management-adjustments.csv": "adjustment_id,report_id,period_start,period_end,line_id,account_code,dimension_id,adjustment_type,amount,reason,policy_id,source_locator,approved_by,status,reverse_on\n",
            "allocation-policy-register.json": json.dumps({"schema_version": "1.0", "policies": []}),
            "budgets.csv": "budget_id,period_start,period_end,line_id,dimension_id,currency,amount,source_locator,status,approved_by,approved_at\n",
            "evidence-register.csv": "document_id,document_type,document_number,source_system,source_locator,content_sha256,original_filename,document_date,counterparty_id,economic_event_id,currency,amount,completeness_status,sensitivity_class,retention_rule,owner,notes\n",
            "open-items.csv": "open_item_id,item_type,description,amount,currency,source_locator,status,owner,next_action,due_date,blocks_close,professional_review_required,created_at,updated_at\n",
        }
        checksum_fields = {
            "company-profile.json": "company_profile_sha256",
            "chart-of-accounts.csv": "chart_of_accounts_sha256",
            "accounting-policy-register.json": "policy_register_sha256",
            "management-report-definition.json": "definition_sha256",
            "management-dashboard-config.json": "dashboard_config_sha256",
            "dimensions.csv": "dimensions_sha256",
            "management-attribution.csv": "attribution_sha256",
            "management-adjustments.csv": "adjustments_sha256",
            "allocation-policy-register.json": "allocation_policies_sha256",
            "budgets.csv": "budgets_sha256",
            "evidence-register.csv": "evidence_register_sha256",
            "open-items.csv": "open_items_sha256",
        }
        for filename, payload in source_payloads.items():
            source_path = pack_dir / filename
            source_path.write_text(payload, encoding="utf-8")
            management_report["source_checksums"][checksum_fields[filename]] = hashlib.sha256(source_path.read_bytes()).hexdigest()
        renderer_path = Path(__file__).resolve().with_name("render_management_dashboard.py")
        management_report["source_checksums"]["renderer_sha256"] = hashlib.sha256(
            renderer_path.read_bytes()
        ).hexdigest()
        workbook_renderer_path = Path(__file__).resolve().with_name("render_management_workbook.mjs")
        management_report["source_checksums"]["workbook_renderer_sha256"] = hashlib.sha256(
            workbook_renderer_path.read_bytes()
        ).hexdigest()
        (pack_dir / "management-dashboard.md").write_text(
            render_management_dashboard(config, management_report),
            encoding="utf-8",
        )
        return {
            "profile": profile,
            "feature_selection": feature_selection,
            "policy_data": {"policies": []},
            "allocation_policy_data": {"schema_version": "1.0", "policies": []},
            "manifest": manifest,
            "definition": definition,
            "config": config,
            "management_report": management_report,
            "csv_rows": {
                "journal.csv": journal_rows,
                "chart-of-accounts.csv": coa_rows,
                "management-adjustments.csv": [],
                "management-attribution.csv": [],
                "dimensions.csv": [],
                "budgets.csv": [],
                "evidence-register.csv": [],
                "open-items.csv": [],
            },
        }

    def _run(self, pack_dir: Path, fixture) -> RecordingReport:
        report = RecordingReport()
        validate_management_reporting(
            pack_dir=pack_dir,
            stage="close",
            report=report,
            **fixture,
        )
        return report

    def _persist_config_and_dashboard(self, pack_dir: Path, fixture) -> None:
        config_path = pack_dir / "management-dashboard-config.json"
        config_path.write_text(
            json.dumps(fixture["config"], ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        fixture["management_report"]["source_checksums"]["dashboard_config_sha256"] = hashlib.sha256(
            config_path.read_bytes()
        ).hexdigest()
        (pack_dir / "management-dashboard.md").write_text(
            render_management_dashboard(fixture["config"], fixture["management_report"]),
            encoding="utf-8",
        )

    def _persist_source(self, pack_dir: Path, fixture, filename: str, checksum_field: str, payload: str) -> None:
        source_path = pack_dir / filename
        source_path.write_text(payload, encoding="utf-8")
        fixture["management_report"]["source_checksums"][checksum_field] = hashlib.sha256(
            source_path.read_bytes()
        ).hexdigest()

    def _persist_evidence_register(self, pack_dir: Path, fixture) -> None:
        path = pack_dir / "evidence-register.csv"
        fieldnames = [
            "document_id", "document_type", "document_number", "source_system",
            "source_locator", "content_sha256", "original_filename", "document_date",
            "counterparty_id", "economic_event_id", "currency", "amount",
            "completeness_status", "sensitivity_class", "retention_rule", "owner", "notes",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(fixture["csv_rows"]["evidence-register.csv"])
        fixture["management_report"]["source_checksums"]["evidence_register_sha256"] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()

    def _configure_valid_professional_review(self, pack_dir: Path, fixture) -> Path:
        evidence_dir = pack_dir / "evidence"
        evidence_dir.mkdir()
        conclusion_path = evidence_dir / "professional-conclusion.txt"
        conclusion_path.write_text(
            "Synthetic written conclusion for MR-2026-08 revision 1.\n",
            encoding="utf-8",
        )
        conclusion_sha = hashlib.sha256(conclusion_path.read_bytes()).hexdigest()
        fixture["profile"]["professional_advisors"] = [{
            "advisor_id": "CPA-1",
            "qualification_or_role": "CPA",
            "status": "ACTIVE",
            "verification_source": "test:professional-register",
            "verified_at": "2026-08-01",
        }]
        self._persist_source(
            pack_dir,
            fixture,
            "company-profile.json",
            "company_profile_sha256",
            json.dumps(fixture["profile"], ensure_ascii=False, sort_keys=True),
        )
        fixture["csv_rows"]["evidence-register.csv"] = [{
            "document_id": "PRO-CONCLUSION-1",
            "document_type": "PROFESSIONAL_CONCLUSION",
            "document_number": "",
            "source_system": "LOCAL_IMMUTABLE_FILE",
            "source_locator": "evidence/professional-conclusion.txt",
            "content_sha256": conclusion_sha,
            "original_filename": "professional-conclusion.txt",
            "document_date": "2026-09-01",
            "counterparty_id": "CPA-1",
            "economic_event_id": "",
            "currency": "",
            "amount": "",
            "completeness_status": "VERIFIED",
            "sensitivity_class": "CONFIDENTIAL",
            "retention_rule": "PROFESSIONAL_REVIEW",
            "owner": "synthetic-owner",
            "notes": "Synthetic validator fixture.",
        }]
        self._persist_evidence_register(pack_dir, fixture)
        fixture["management_report"]["status"] = "PROFESSIONALLY_REVIEWED"
        fixture["manifest"]["management_report_status"] = "PROFESSIONALLY_REVIEWED"
        fixture["management_report"]["approved_by"] = "CPA-1"
        fixture["management_report"]["generated_at"] = "2026-09-01T12:00:00+08:00"
        fixture["management_report"]["professional_review"] = {
            "status": "REVIEWED",
            "reviewer_id": "CPA-1",
            "qualification_or_role": "CPA",
            "scope": {
                "report_id": "MR-2026-08",
                "revision": 1,
                "period_start": "2026-08-01",
                "period_end": "2026-08-31",
                "ledger_sha256": fixture["management_report"]["ledger_sha256"],
                "covered_areas": [
                    "ACCRUAL_PNL_DRAFT",
                    "MANAGEMENT_ADJUSTMENTS",
                    "COST_BREAKDOWN",
                    "TRUST_AND_ACTIONS",
                ],
            },
            "conclusion_reference": "PRO-CONCLUSION-1",
            "conclusion_sha256": conclusion_sha,
            "reviewed_at": "2026-09-01T10:00:00+08:00",
        }
        (pack_dir / "management-dashboard.md").write_text(
            render_management_dashboard(fixture["config"], fixture["management_report"]),
            encoding="utf-8",
        )
        return conclusion_path

    def test_valid_report_recomputes_from_posted_journal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="management-report-valid-") as temp:
            pack_dir = Path(temp)
            fixture = self._fixture(pack_dir)
            report = self._run(pack_dir, fixture)
            self.assertEqual(report.errors, [])

    def test_valid_dimension_profit_reconciles_to_company(self) -> None:
        with tempfile.TemporaryDirectory(prefix="management-report-dimension-valid-") as temp:
            pack_dir = Path(temp)
            fixture = self._fixture(pack_dir)
            fixture["config"]["dimension_types"] = ["STORE"]
            fixture["config"]["modules"].append({
                "module_id": "O6-DIMENSION",
                "status": "ENABLED",
                "recommendation": "OPTIONAL",
                "rationale": "Synthetic store-profit test.",
            })
            dimensions = [{
                "dimension_id": "STORE-A",
                "dimension_type": "STORE",
                "dimension_name": "Store A",
                "parent_id": "",
                "status": "ACTIVE",
            }]
            attributions = []
            for attribution_id, entry_id, line_no, amount in (
                ("ATTR-REV", "JE-SALE", "2", "1000"),
                ("ATTR-COGS", "JE-COST", "1", "600"),
                ("ATTR-OPEX", "JE-OPEX", "1", "200"),
            ):
                attributions.append({
                    "attribution_id": attribution_id,
                    "report_id": "MR-2026-08",
                    "entry_id": entry_id,
                    "line_no": line_no,
                    "dimension_type": "STORE",
                    "dimension_id": "STORE-A",
                    "attribution_type": "DIRECT",
                    "ratio": "1",
                    "amount": amount,
                    "allocation_policy_id": "",
                    "source_locator": "test:direct-attribution",
                    "status": "APPROVED",
                })
            financial = {
                line["line_id"]: line["financial_amount"]
                for line in fixture["management_report"]["lines"]
            }
            fixture["management_report"]["dimension_summary"] = [{
                "dimension_type": "STORE",
                "dimension_id": "STORE-A",
                "dimension_name": "Store A",
                "financial_amounts": financial,
                "management_adjustments": {line_id: "0" for line_id in financial},
                "management_amounts": financial,
                "data_status": "COMPLETE",
            }]
            fixture["csv_rows"]["dimensions.csv"] = dimensions
            fixture["csv_rows"]["management-attribution.csv"] = attributions
            self._persist_source(pack_dir, fixture, "dimensions.csv", "dimensions_sha256", json.dumps(dimensions, sort_keys=True))
            self._persist_source(pack_dir, fixture, "management-attribution.csv", "attribution_sha256", json.dumps(attributions, sort_keys=True))
            self._persist_config_and_dashboard(pack_dir, fixture)
            report = self._run(pack_dir, fixture)
            self.assertEqual(report.errors, [])

    def test_valid_explicit_budget_reconciles(self) -> None:
        with tempfile.TemporaryDirectory(prefix="management-report-budget-valid-") as temp:
            pack_dir = Path(temp)
            fixture = self._fixture(pack_dir)
            fixture["config"]["modules"].append({
                "module_id": "O6-BUDGET",
                "status": "ENABLED",
                "recommendation": "OPTIONAL",
                "rationale": "Synthetic approved-budget test.",
            })
            base_line_ids = {
                "GROSS_REVENUE", "REVENUE_DEDUCTIONS", "COST_OF_SALES",
                "OPERATING_EXPENSE", "OTHER_INCOME", "OTHER_EXPENSE",
                "INCOME_TAX", "DISCONTINUED_OPERATIONS",
            }
            report_lines = {
                line["line_id"]: line
                for line in fixture["management_report"]["lines"]
            }
            budget_rows = []
            for line_id in sorted(base_line_ids):
                budget_rows.append({
                    "budget_id": "BUD-" + line_id,
                    "period_start": "2026-08-01",
                    "period_end": "2026-08-31",
                    "line_id": line_id,
                    "dimension_id": "",
                    "currency": "TWD",
                    "amount": report_lines[line_id]["financial_amount"],
                    "source_locator": "test:approved-budget",
                    "status": "APPROVED",
                    "approved_by": "synthetic-owner",
                    "approved_at": "2026-07-31T00:00:00+08:00",
                })
            fixture["management_report"]["budget_status"] = "PROVIDED"
            fixture["management_report"]["budget_source_ids"] = [row["budget_id"] for row in budget_rows]
            for line in fixture["management_report"]["lines"]:
                line["budget_amount"] = line["financial_amount"]
                line["variance_amount"] = "0"
            fixture["csv_rows"]["budgets.csv"] = budget_rows
            self._persist_source(pack_dir, fixture, "budgets.csv", "budgets_sha256", json.dumps(budget_rows, sort_keys=True))
            self._persist_config_and_dashboard(pack_dir, fixture)
            report = self._run(pack_dir, fixture)
            self.assertEqual(report.errors, [])

    def test_stale_or_hardcoded_report_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="management-report-tamper-") as temp:
            pack_dir = Path(temp)
            fixture = self._fixture(pack_dir)
            fixture["management_report"]["lines"][0]["financial_amount"] = "999999"
            fixture["management_report"]["charts"][0]["values"] = [1, 2, 3]
            fixture["management_report"]["lines"][0]["budget_amount"] = "0"
            report = self._run(pack_dir, fixture)
            combined = "\n".join(report.errors)
            self.assertIn("does not recompute from journal", combined)
            self.assertIn("charts may not embed data or values", combined)
            self.assertIn("budget and variance must be null", combined)

    def test_chart_points_and_manual_markdown_tamper_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="management-report-visual-tamper-") as temp:
            pack_dir = Path(temp)
            fixture = self._fixture(pack_dir)
            fixture["management_report"]["charts"][0]["points"] = [999999]
            dashboard_path = pack_dir / "management-dashboard.md"
            dashboard_path.write_text(
                dashboard_path.read_text(encoding="utf-8") + "\n本期淨利：999999\n",
                encoding="utf-8",
            )
            report = self._run(pack_dir, fixture)
            combined = "\n".join(report.errors)
            self.assertIn("only ID references are allowed", combined)
            self.assertIn("not the deterministic rendering", combined)

    def test_cost_doughnut_rejects_negative_part_to_whole_data(self) -> None:
        with tempfile.TemporaryDirectory(prefix="management-report-donut-negative-") as temp:
            pack_dir = Path(temp)
            fixture = self._fixture(pack_dir)
            fixture["management_report"]["cost_breakdown"][0]["management_amount"] = "-600"
            self._persist_config_and_dashboard(pack_dir, fixture)
            report = self._run(pack_dir, fixture)
            self.assertTrue(any(
                "COST_DONUT cannot represent negative cost categories" in message
                for message in report.errors
            ))

    def test_cost_doughnut_must_cover_the_complete_cost_whole(self) -> None:
        with tempfile.TemporaryDirectory(prefix="management-report-donut-incomplete-") as temp:
            pack_dir = Path(temp)
            fixture = self._fixture(pack_dir)
            donut = next(
                item for item in fixture["management_report"]["charts"]
                if item["chart_id"] == "COST_DONUT"
            )
            donut["cost_ids"] = ["COST-5000"]
            report = self._run(pack_dir, fixture)
            self.assertTrue(any(
                "COST_DONUT must reference every cost category" in message
                for message in report.errors
            ))

    def test_close_requires_owner_visual_answer_and_enabled_chart_reference(self) -> None:
        with tempfile.TemporaryDirectory(prefix="management-report-visual-selection-") as temp:
            pack_dir = Path(temp)
            fixture = self._fixture(pack_dir)
            fixture["config"]["owner_questions"] = [
                item for item in fixture["config"]["owner_questions"]
                if item["question_id"] != "Q-VISUAL"
            ]
            fixture["management_report"]["charts"] = [
                item for item in fixture["management_report"]["charts"]
                if item["chart_id"] != "PNL_COLUMNS"
            ]
            self._persist_config_and_dashboard(pack_dir, fixture)
            report = self._run(pack_dir, fixture)
            combined = "\n".join(report.errors)
            self.assertIn("Q-VISUAL", combined)
            self.assertIn("missing enabled visual references PNL_COLUMNS", combined)

    def test_cash_cannot_copy_net_profit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="management-report-cash-tamper-") as temp:
            pack_dir = Path(temp)
            fixture = self._fixture(pack_dir)
            fixture["config"]["modules"].append({
                "module_id": "O6-CASH",
                "status": "ENABLED",
                "recommendation": "OPTIONAL",
                "rationale": "Synthetic cash test.",
            })
            fixture["management_report"]["cash_summary"] = {
                "available_cash": "200",
                "restricted_cash": "0",
                "currency": "TWD",
                "as_of": "2026-08-31",
                "basis": "NET_PROFIT",
                "status": "COMPLETE",
                "source_locator": "journal.csv|chart-of-accounts.csv",
                "assumptions": [],
            }
            self._persist_config_and_dashboard(pack_dir, fixture)
            report = self._run(pack_dir, fixture)
            self.assertTrue(any("basis must be LEDGER_BALANCE_AS_OF" in message for message in report.errors))

    def test_valid_cash_view_recomputes_from_ledger_accounts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="management-report-cash-valid-") as temp:
            pack_dir = Path(temp)
            fixture = self._fixture(pack_dir)
            fixture["config"]["modules"].append({
                "module_id": "O6-CASH",
                "status": "ENABLED",
                "recommendation": "OPTIONAL",
                "rationale": "Synthetic ledger cash test.",
            })
            fixture["management_report"]["cash_summary"] = {
                "available_cash": "200",
                "restricted_cash": "0",
                "currency": "TWD",
                "as_of": "2026-08-31",
                "basis": "LEDGER_BALANCE_AS_OF",
                "status": "COMPLETE",
                "source_locator": "journal.csv|chart-of-accounts.csv",
                "assumptions": ["Synthetic ledger contains opening-to-date cash entries."],
            }
            self._persist_config_and_dashboard(pack_dir, fixture)
            report = self._run(pack_dir, fixture)
            self.assertEqual(report.errors, [])

    def test_owner_cannot_self_declare_professional_review(self) -> None:
        with tempfile.TemporaryDirectory(prefix="management-report-review-tamper-") as temp:
            pack_dir = Path(temp)
            fixture = self._fixture(pack_dir)
            fixture["management_report"]["status"] = "PROFESSIONALLY_REVIEWED"
            fixture["manifest"]["management_report_status"] = "PROFESSIONALLY_REVIEWED"
            fixture["management_report"]["approved_by"] = "synthetic-owner"
            fixture["management_report"]["professional_review"] = {
                "status": "REVIEWED",
                "reviewer_id": "synthetic-owner",
                "qualification_or_role": "CPA",
                "scope": {
                    "report_id": "MR-2026-08",
                    "revision": 1,
                    "period_start": "2026-08-01",
                    "period_end": "2026-08-31",
                    "ledger_sha256": fixture["management_report"]["ledger_sha256"],
                    "covered_areas": ["all"],
                },
                "conclusion_reference": "FAKE-DOC",
                "conclusion_sha256": "0" * 64,
                "reviewed_at": "2026-08-31T23:00:00+08:00",
            }
            (pack_dir / "management-dashboard.md").write_text(
                render_management_dashboard(fixture["config"], fixture["management_report"]),
                encoding="utf-8",
            )
            report = self._run(pack_dir, fixture)
            combined = "\n".join(report.errors)
            self.assertIn("reviewer is not an active confirmed advisor", combined)
            self.assertIn("conclusion_reference is missing", combined)

    def test_valid_professional_review_requires_bound_local_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="management-report-review-valid-") as temp:
            pack_dir = Path(temp)
            fixture = self._fixture(pack_dir)
            self._configure_valid_professional_review(pack_dir, fixture)
            report = self._run(pack_dir, fixture)
            self.assertEqual(report.errors, [])

    def test_professional_review_rejects_missing_conclusion_bytes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="management-report-review-missing-") as temp:
            pack_dir = Path(temp)
            fixture = self._fixture(pack_dir)
            conclusion_path = self._configure_valid_professional_review(pack_dir, fixture)
            conclusion_path.unlink()
            report = self._run(pack_dir, fixture)
            self.assertTrue(any("conclusion source file does not exist" in message for message in report.errors))

    def test_professional_review_rejects_impossible_timeline_and_scope(self) -> None:
        with tempfile.TemporaryDirectory(prefix="management-report-review-time-") as temp:
            pack_dir = Path(temp)
            fixture = self._fixture(pack_dir)
            self._configure_valid_professional_review(pack_dir, fixture)
            fixture["management_report"]["professional_review"]["reviewed_at"] = "1900-01-01T00:00:00+08:00"
            fixture["management_report"]["professional_review"]["scope"]["revision"] = 99
            fixture["profile"]["professional_advisors"][0]["verified_at"] = "not-a-date"
            fixture["csv_rows"]["evidence-register.csv"][0]["document_date"] = "1900-01-01"
            self._persist_source(
                pack_dir,
                fixture,
                "company-profile.json",
                "company_profile_sha256",
                json.dumps(fixture["profile"], ensure_ascii=False, sort_keys=True),
            )
            self._persist_evidence_register(pack_dir, fixture)
            (pack_dir / "management-dashboard.md").write_text(
                render_management_dashboard(fixture["config"], fixture["management_report"]),
                encoding="utf-8",
            )
            report = self._run(pack_dir, fixture)
            combined = "\n".join(report.errors)
            self.assertIn("reviewed_at cannot be before period_end", combined)
            self.assertIn("verified_at must be an ISO date or date-time", combined)
            self.assertIn("scope revision does not match report", combined)

    def test_partial_review_cannot_set_global_professional_status(self) -> None:
        with tempfile.TemporaryDirectory(prefix="management-report-review-partial-") as temp:
            pack_dir = Path(temp)
            fixture = self._fixture(pack_dir)
            self._configure_valid_professional_review(pack_dir, fixture)
            fixture["management_report"]["professional_review"]["scope"]["covered_areas"] = ["CASH_SUMMARY"]
            (pack_dir / "management-dashboard.md").write_text(
                render_management_dashboard(fixture["config"], fixture["management_report"]),
                encoding="utf-8",
            )
            report = self._run(pack_dir, fixture)
            self.assertTrue(any(
                "global PROFESSIONALLY_REVIEWED status requires exactly the full enabled report scope" in message
                for message in report.errors
            ))

    def test_reporting_currency_cannot_be_relabelled(self) -> None:
        with tempfile.TemporaryDirectory(prefix="management-report-currency-tamper-") as temp:
            pack_dir = Path(temp)
            fixture = self._fixture(pack_dir)
            fixture["profile"]["reporting_currency"] = "USD"
            fixture["management_report"]["reporting_currency"] = "USD"
            fixture["config"]["display_currency"] = "USD"
            for line in fixture["management_report"]["lines"]:
                line["currency"] = "USD"
            self._persist_config_and_dashboard(pack_dir, fixture)
            report = self._run(pack_dir, fixture)
            self.assertTrue(any("supports only reporting_currency equal to functional_currency" in message for message in report.errors))

    def test_allocation_ratio_and_policy_applicability_are_enforced(self) -> None:
        report = RecordingReport()
        policy = {
            "status": "owner_confirmed",
            "target_dimension_type": "PROJECT",
            "source_cost_pool": ["9999"],
            "effective_from": "2026-09-01",
            "effective_to": "",
        }
        attributions = []
        for attribution_id, dimension_id, ratio, amount in (
            ("A1", "STORE-A", "1.2", "120"),
            ("A2", "STORE-B", "-0.2", "-20"),
        ):
            attributions.append({
                "attribution_id": attribution_id,
                "report_id": "MR-2026-08",
                "entry_id": "JE-1",
                "line_no": "1",
                "dimension_type": "STORE",
                "dimension_id": dimension_id,
                "attribution_type": "ALLOCATED",
                "ratio": ratio,
                "amount": amount,
                "allocation_policy_id": "ALLOC-1",
                "source_locator": "test:allocation",
                "status": "APPROVED",
            })
        _validate_dimensions(
            {"O6-DIMENSION"},
            {"dimension_types": ["STORE"]},
            [
                {"dimension_type": "STORE", "dimension_id": "STORE-A", "dimension_name": "Store A", "status": "ACTIVE"},
                {"dimension_type": "STORE", "dimension_id": "STORE-B", "dimension_name": "Store B", "status": "ACTIVE"},
            ],
            attributions,
            {("JE-1", "1"): ("COST_OF_SALES", Decimal("100"), "5000")},
            [],
            [],
            derive_pnl_lines({"COST_OF_SALES": Decimal("100")}),
            derive_pnl_lines({"COST_OF_SALES": Decimal("100")}),
            "MR-2026-08",
            {"ALLOC-1": policy},
            date.fromisoformat("2026-08-01"),
            date.fromisoformat("2026-08-31"),
            report,
        )
        combined = "\n".join(report.errors)
        self.assertIn("target_dimension_type mismatch", combined)
        self.assertIn("source account is outside policy cost pool", combined)
        self.assertIn("policy was not effective at period start", combined)
        self.assertIn("must be between 0 and 1", combined)

    def test_management_adjustment_period_and_account_are_enforced(self) -> None:
        report = RecordingReport()
        _validate_adjustments(
            [{
                "adjustment_id": "ADJ-1",
                "report_id": "MR-1",
                "period_start": "2026-07-01",
                "period_end": "2026-07-31",
                "line_id": "OPERATING_EXPENSE",
                "account_code": "9999",
                "dimension_id": "",
                "adjustment_type": "NON_GAAP_ADJUSTMENT",
                "amount": "10",
                "reason": "Synthetic",
                "policy_id": "POL-1",
                "source_locator": "test:adjustment",
                "approved_by": "owner",
                "status": "APPROVED",
            }],
            "MR-1",
            date.fromisoformat("2026-08-01"),
            date.fromisoformat("2026-08-31"),
            {"POL-1": "owner_confirmed"},
            {},
            report,
        )
        combined = "\n".join(report.errors)
        self.assertIn("period must exactly match", combined)
        self.assertIn("account_code must identify a P&L source account", combined)

    def test_unvalidated_optional_module_blocks_close(self) -> None:
        with tempfile.TemporaryDirectory(prefix="management-report-module-tamper-") as temp:
            pack_dir = Path(temp)
            fixture = self._fixture(pack_dir)
            fixture["config"]["modules"].append({
                "module_id": "O6-SCENARIO",
                "status": "ENABLED",
                "recommendation": "OPTIONAL",
                "rationale": "Synthetic unsupported module test.",
            })
            self._persist_config_and_dashboard(pack_dir, fixture)
            report = self._run(pack_dir, fixture)
            self.assertTrue(any("unvalidated modules enabled" in message for message in report.errors))

    def test_made_up_status_and_management_cost_tamper_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="management-report-status-tamper-") as temp:
            pack_dir = Path(temp)
            fixture = self._fixture(pack_dir)
            fixture["management_report"]["lines"][0]["data_status"] = "MADE_UP"
            fixture["management_report"]["cost_breakdown"][0]["management_adjustment"] = "999"
            fixture["management_report"]["cost_breakdown"][0]["management_amount"] = "1599"
            (pack_dir / "management-dashboard.md").write_text(
                render_management_dashboard(fixture["config"], fixture["management_report"]),
                encoding="utf-8",
            )
            report = self._run(pack_dir, fixture)
            combined = "\n".join(report.errors)
            self.assertIn("close requires COMPLETE data_status", combined)
            self.assertIn("cost adjustments do not reconcile", combined)

    def test_journal_change_invalidates_checksum_and_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="management-report-metamorphic-") as temp:
            pack_dir = Path(temp)
            fixture = self._fixture(pack_dir)
            journal_path = pack_dir / "journal.csv"
            journal_path.write_text(journal_path.read_text(encoding="utf-8").replace(",1000,", ",900,", 1), encoding="utf-8")
            report = self._run(pack_dir, fixture)
            self.assertTrue(any("ledger_sha256" in message for message in report.errors))


if __name__ == "__main__":
    unittest.main()
