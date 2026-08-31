#!/usr/bin/env python3
"""Run structural controls on a Company Accounting Pack.

Passing this validator does not establish accounting, tax, legal, or audit correctness.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path


REQUIRED_FILES = [
    "company-profile.json",
    "interview-state.json",
    "industry-accounting-map.md",
    "applicable-framework.md",
    "system-recommendation.md",
    "accounting-policy-register.json",
    "chart-of-accounts.csv",
    "transaction-intake.csv",
    "journal.csv",
    "evidence-register.csv",
    "open-items.csv",
    "reconciliations.md",
    "monthly-close-checklist.md",
    "professional-review-pack.md",
    "change-log.md",
    "version-manifest.json",
]

CSV_REQUIRED_HEADERS = {
    "chart-of-accounts.csv": {
        "account_code", "account_name", "account_type", "normal_balance", "review_status"
    },
    "transaction-intake.csv": {
        "intake_id", "economic_event_id", "transaction_date", "description",
        "original_currency", "original_amount", "document_id", "dedup_status",
        "proposed_status"
    },
    "journal.csv": {
        "entry_id", "line_no", "entry_date", "economic_event_id", "account_code",
        "debit", "credit", "currency", "document_id", "policy_id", "posting_status"
    },
    "evidence-register.csv": {
        "document_id", "document_type", "source_locator", "document_date",
        "economic_event_id", "completeness_status", "sensitivity_class"
    },
    "open-items.csv": {
        "open_item_id", "item_type", "description", "status", "owner", "next_action",
        "due_date", "blocks_close", "professional_review_required"
    },
}

ALLOWED_POLICY_STATUSES = {
    "draft",
    "owner_confirmed",
    "professional_review_required",
    "professionally_reviewed",
}

STAGES = ("onboarding", "draft", "posting", "close")
GATES = ("G0", "G1", "G2", "G3", "G4")
ALLOWED_GATE_STATUSES = {
    "NOT_STARTED", "AWAITING_CONFIRMATION", "CONFIRMED", "BLOCKED"
}
ALLOWED_ITEM_STATUSES = {
    "FACT", "AI_PROPOSAL", "OPEN_QUESTION", "PROFESSIONAL_DECISION_REQUIRED"
}
STATE_ITEM_ARRAYS = (
    "confirmed_facts",
    "owner_confirmed_decisions",
    "ai_proposals",
    "assumptions",
    "open_questions",
    "conflicts",
    "professional_review_items",
    "next_questions",
)
STATE_ITEM_FIELDS = {
    "id", "status", "statement", "source_type", "source_locator",
    "confirmed_by", "confirmed_at", "affects"
}
EXPECTED_ITEM_STATUSES = {
    "confirmed_facts": {"FACT"},
    "owner_confirmed_decisions": {"FACT", "AI_PROPOSAL"},
    "ai_proposals": {"AI_PROPOSAL"},
    "assumptions": {"AI_PROPOSAL"},
    "open_questions": {"OPEN_QUESTION"},
    "conflicts": {"OPEN_QUESTION"},
    "professional_review_items": {"PROFESSIONAL_DECISION_REQUIRED"},
    "next_questions": {"OPEN_QUESTION"},
}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)


def load_json(path: Path, report: Report):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report.error(f"{path.name}: invalid JSON: {exc}")
        return None


def load_csv(path: Path, report: Report) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames or []
            return headers, list(reader)
    except (OSError, csv.Error) as exc:
        report.error(f"{path.name}: unreadable CSV: {exc}")
        return [], []


def duplicate_values(rows: list[dict[str, str]], field: str) -> list[str]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        value = (row.get(field) or "").strip()
        if value:
            counts[value] += 1
    return sorted(value for value, count in counts.items() if count > 1)


def decimal_or_zero(value: str, label: str, report: Report) -> Decimal:
    stripped = (value or "").strip()
    if not stripped:
        return Decimal("0")
    try:
        return Decimal(stripped)
    except InvalidOperation:
        report.error(f"{label}: not a decimal: {stripped!r}")
        return Decimal("0")


def validate_policy_register(data, report: Report) -> None:
    if not isinstance(data, dict) or not isinstance(data.get("policies"), list):
        report.error("accounting-policy-register.json: policies must be an array")
        return
    seen: set[str] = set()
    required = {
        "policy_id", "statement", "scope", "rationale", "evidence_or_source",
        "assumptions", "status", "decision_owner", "effective_from", "supersedes",
        "review_due"
    }
    for index, policy in enumerate(data["policies"], start=1):
        if not isinstance(policy, dict):
            report.error(f"policy #{index}: must be an object")
            continue
        missing = sorted(key for key in required if key not in policy)
        if missing:
            report.error(f"policy #{index}: missing fields {', '.join(missing)}")
        policy_id = str(policy.get("policy_id", "")).strip()
        if not policy_id:
            report.error(f"policy #{index}: blank policy_id")
        elif policy_id in seen:
            report.error(f"duplicate policy_id: {policy_id}")
        seen.add(policy_id)
        status = str(policy.get("status", "")).strip()
        if status not in ALLOWED_POLICY_STATUSES:
            report.error(f"policy {policy_id or index}: invalid status {status!r}")


def validate_interview_state(data, stage: str, report: Report) -> None:
    if not isinstance(data, dict):
        report.error("interview-state.json: must be an object")
        return
    if data.get("schema_version") != "1.1":
        report.error("interview-state.json: schema_version must be '1.1'")
    if data.get("mode") not in {"setup", "migrate", "operate", "review"}:
        report.error("interview-state.json: invalid mode")
    if data.get("workflow_stage") != stage:
        report.error(
            f"interview-state.json: workflow_stage {data.get('workflow_stage')!r} does not match requested stage {stage!r}"
        )
    readiness = str(data.get("readiness", ""))
    if not readiness:
        report.error("interview-state.json: readiness is required")
    elif stage in {"posting", "close"} and "NOT_READY" in readiness:
        report.error(f"interview-state.json: readiness {readiness!r} is not valid for {stage}")

    current_gate = data.get("current_gate")
    if current_gate not in GATES:
        report.error("interview-state.json: current_gate must be G0 through G4")

    gates = data.get("gates")
    gate_statuses: dict[str, str] = {}
    if not isinstance(gates, dict):
        report.error("interview-state.json: gates must be an object")
    else:
        for gate in GATES:
            gate_data = gates.get(gate)
            if not isinstance(gate_data, dict):
                report.error(f"interview-state.json: missing gate object {gate}")
                continue
            status = gate_data.get("status")
            gate_statuses[gate] = status
            if status not in ALLOWED_GATE_STATUSES:
                report.error(f"interview-state.json: {gate} has invalid status {status!r}")
            if status == "CONFIRMED":
                for field in ("confirmed_by", "confirmed_at"):
                    if not str(gate_data.get(field, "")).strip():
                        report.error(f"interview-state.json: confirmed {gate} requires {field}")
            if not isinstance(gate_data.get("evidence"), list):
                report.error(f"interview-state.json: {gate}.evidence must be an array")

        confirmed_seen = True
        for gate in GATES:
            if gate_statuses.get(gate) == "CONFIRMED" and not confirmed_seen:
                report.error(f"interview-state.json: {gate} confirmed before an earlier gate")
            if gate_statuses.get(gate) != "CONFIRMED":
                confirmed_seen = False

    authorization = data.get("persistence_authorization")
    authorization_granted = False
    if not isinstance(authorization, dict):
        report.error("interview-state.json: persistence_authorization must be an object")
    else:
        auth_status = authorization.get("status")
        if auth_status not in {"NOT_GRANTED", "GRANTED"}:
            report.error("interview-state.json: invalid persistence authorization status")
        authorization_granted = auth_status == "GRANTED"
        if authorization_granted:
            for field in ("source_type", "source_locator", "authorized_by", "authorized_at"):
                if not str(authorization.get(field, "")).strip():
                    report.error(f"interview-state.json: granted authorization requires {field}")
            if not isinstance(authorization.get("scope"), list) or not authorization.get("scope"):
                report.error("interview-state.json: granted authorization requires non-empty scope")

    if gate_statuses.get("G0") == "CONFIRMED" and not authorization_granted:
        report.error("interview-state.json: G0 cannot be confirmed without persistence authorization")

    seen_ids: set[str] = set()
    for array_name in STATE_ITEM_ARRAYS:
        items = data.get(array_name)
        if not isinstance(items, list):
            report.error(f"interview-state.json: {array_name} must be an array")
            continue
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                report.error(f"interview-state.json: {array_name} item {index} must be an object")
                continue
            missing = sorted(STATE_ITEM_FIELDS - set(item))
            if missing:
                report.error(
                    f"interview-state.json: {array_name} item {index} missing fields {', '.join(missing)}"
                )
            item_id = str(item.get("id", "")).strip()
            if not item_id:
                report.error(f"interview-state.json: {array_name} item {index} has blank id")
            elif item_id in seen_ids:
                report.error(f"interview-state.json: duplicate state item id {item_id}")
            seen_ids.add(item_id)
            if item.get("status") not in ALLOWED_ITEM_STATUSES:
                report.error(
                    f"interview-state.json: {array_name} item {item_id or index} has invalid status"
                )
            elif item.get("status") not in EXPECTED_ITEM_STATUSES[array_name]:
                report.error(
                    f"interview-state.json: {array_name} item {item_id or index} has status {item.get('status')!r}"
                )
            if not str(item.get("statement", "")).strip():
                report.error(f"interview-state.json: {array_name} item {item_id or index} has blank statement")
            for field in ("source_type", "source_locator"):
                if not str(item.get(field, "")).strip():
                    report.error(
                        f"interview-state.json: {array_name} item {item_id or index} requires {field}"
                    )
            if not isinstance(item.get("affects"), list):
                report.error(f"interview-state.json: {array_name} item {item_id or index} affects must be an array")
            if array_name == "owner_confirmed_decisions":
                for field in ("confirmed_by", "confirmed_at"):
                    if not str(item.get(field, "")).strip():
                        report.error(
                            f"interview-state.json: owner decision {item_id or index} requires {field}"
                        )

    sources = data.get("official_sources_checked")
    if not isinstance(sources, list):
        report.error("interview-state.json: official_sources_checked must be an array")
    else:
        source_fields = {"id", "status", "statement", "title", "url", "checked_at", "applies_if", "affects"}
        for index, source in enumerate(sources, start=1):
            if not isinstance(source, dict):
                report.error(f"interview-state.json: official source {index} must be an object")
                continue
            missing = sorted(source_fields - set(source))
            if missing:
                report.error(f"interview-state.json: official source {index} missing fields {', '.join(missing)}")
            source_id = str(source.get("id", "")).strip()
            if not source_id:
                report.error(f"interview-state.json: official source {index} has blank id")
            elif source_id in seen_ids:
                report.error(f"interview-state.json: duplicate state item id {source_id}")
            seen_ids.add(source_id)
            if source.get("status") != "OFFICIAL_SOURCE":
                report.error(f"interview-state.json: official source {source_id or index} must use OFFICIAL_SOURCE")
            for field in ("statement", "title", "url", "checked_at"):
                if not str(source.get(field, "")).strip():
                    report.error(f"interview-state.json: official source {source_id or index} requires {field}")
            for field in ("applies_if", "affects"):
                if not isinstance(source.get(field), list):
                    report.error(f"interview-state.json: official source {source_id or index} {field} must be an array")

    if stage == "onboarding":
        if gate_statuses.get("G0") != "CONFIRMED":
            report.warning("onboarding is awaiting G0; scaffold is not ready for posting")
    else:
        if gate_statuses.get("G0") != "CONFIRMED":
            report.error(f"{stage} stage requires confirmed G0")
        if not authorization_granted:
            report.error(f"{stage} stage requires persistence authorization")
        if not data.get("confirmed_facts"):
            report.error(f"{stage} stage requires at least one confirmed fact")

    if stage in {"posting", "close"}:
        for gate in GATES[1:]:
            if gate_statuses.get(gate) != "CONFIRMED":
                report.error(f"{stage} stage requires confirmed {gate}")


def validate_manifest(data, pack_dir: Path, stage: str, state, report: Report) -> None:
    if not isinstance(data, dict):
        report.error("version-manifest.json: must be an object")
        return
    required = {
        "schema_version", "skill_name", "skill_version", "company_pack_version",
        "status", "workflow_stage", "current_gate", "output_files", "validation",
        "generated_at", "updated_at"
    }
    missing = sorted(required - set(data))
    if missing:
        report.error(f"version-manifest.json: missing fields {', '.join(missing)}")
    if data.get("workflow_stage") != stage:
        report.error(
            f"version-manifest.json: workflow_stage {data.get('workflow_stage')!r} does not match requested stage {stage!r}"
        )
    if isinstance(state, dict) and data.get("current_gate") != state.get("current_gate"):
        report.error("version-manifest.json: current_gate does not match interview-state.json")

    outputs = data.get("output_files")
    if not isinstance(outputs, list):
        report.error("version-manifest.json: output_files must be an array")
    else:
        if len(outputs) != len(set(outputs)):
            report.error("version-manifest.json: output_files contains duplicates")
        missing_outputs = sorted(set(REQUIRED_FILES) - set(outputs))
        if missing_outputs:
            report.error(f"version-manifest.json: output_files missing {', '.join(missing_outputs)}")
        for output in outputs:
            output_path = Path(str(output))
            if output_path.is_absolute() or ".." in output_path.parts:
                report.error(f"version-manifest.json: unsafe output path {output!r}")
            elif not (pack_dir / output_path).is_file():
                report.error(f"version-manifest.json: listed output does not exist: {output}")

    validation = data.get("validation")
    if not isinstance(validation, dict):
        report.error("version-manifest.json: validation must be an object")
    elif validation.get("stage") not in STAGES:
        report.error("version-manifest.json: validation.stage is invalid")

    status = str(data.get("status", ""))
    if stage in {"posting", "close"} and "NOT_READY" in status:
        report.error(f"version-manifest.json: status {status!r} is not valid for {stage}")
    if stage == "close" and not str(data.get("period", "")).strip():
        report.error("version-manifest.json: close stage requires period")


def validate_journal(
    rows: list[dict[str, str]], coa_codes: set[str], report: Report
) -> None:
    totals: dict[str, list[Decimal]] = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    line_keys: set[tuple[str, str]] = set()
    lines_by_entry: dict[str, int] = defaultdict(int)
    sides_by_entry: dict[str, set[str]] = defaultdict(set)

    for row_number, row in enumerate(rows, start=2):
        entry_id = (row.get("entry_id") or "").strip()
        line_no = (row.get("line_no") or "").strip()
        if not entry_id:
            report.error(f"journal.csv row {row_number}: blank entry_id")
            continue
        key = (entry_id, line_no)
        if key in line_keys:
            report.error(f"journal.csv duplicate entry/line: {entry_id}/{line_no}")
        line_keys.add(key)

        debit = decimal_or_zero(row.get("debit", ""), f"journal row {row_number} debit", report)
        credit = decimal_or_zero(row.get("credit", ""), f"journal row {row_number} credit", report)
        if debit < 0 or credit < 0:
            report.error(f"journal row {row_number}: debit and credit must be non-negative")
        if debit and credit:
            report.error(f"journal row {row_number}: both debit and credit are populated")
        if not debit and not credit:
            report.error(f"journal row {row_number}: neither debit nor credit is populated")

        totals[entry_id][0] += debit
        totals[entry_id][1] += credit
        lines_by_entry[entry_id] += 1
        if debit:
            sides_by_entry[entry_id].add("debit")
        if credit:
            sides_by_entry[entry_id].add("credit")

        code = (row.get("account_code") or "").strip()
        if not code:
            report.error(f"journal row {row_number}: blank account_code")
        elif coa_codes and code not in coa_codes:
            report.error(f"journal row {row_number}: account_code {code!r} is not in chart-of-accounts.csv")

    for entry_id, (debit, credit) in sorted(totals.items()):
        if lines_by_entry[entry_id] < 2 or sides_by_entry[entry_id] != {"debit", "credit"}:
            report.error(f"journal entry {entry_id}: requires at least one debit and one credit line")
        if abs(debit - credit) > Decimal("0.01"):
            report.error(f"journal entry {entry_id}: out of balance by {debit - credit}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate structural accounting-pack controls.")
    parser.add_argument("pack_dir", help="Company Accounting Pack directory")
    parser.add_argument(
        "--stage", choices=STAGES, default="onboarding",
        help="Validation readiness stage (default: onboarding)",
    )
    args = parser.parse_args()

    pack_dir = Path(args.pack_dir).expanduser().resolve()
    report = Report()
    if not pack_dir.is_dir():
        print(f"ERROR: not a directory: {pack_dir}")
        return 1

    for name in REQUIRED_FILES:
        if not (pack_dir / name).is_file():
            report.error(f"missing required file: {name}")

    json_data = {}
    for name in [
        "company-profile.json",
        "interview-state.json",
        "accounting-policy-register.json",
        "version-manifest.json",
    ]:
        path = pack_dir / name
        if path.is_file():
            json_data[name] = load_json(path, report)

    policy_data = json_data.get("accounting-policy-register.json")
    if policy_data is not None:
        validate_policy_register(policy_data, report)

    state = json_data.get("interview-state.json")
    if state is not None:
        validate_interview_state(state, args.stage, report)

    manifest = json_data.get("version-manifest.json")
    if manifest is not None:
        validate_manifest(manifest, pack_dir, args.stage, state, report)

    csv_rows: dict[str, list[dict[str, str]]] = {}
    for name, required_headers in CSV_REQUIRED_HEADERS.items():
        path = pack_dir / name
        if not path.is_file():
            continue
        headers, rows = load_csv(path, report)
        missing_headers = sorted(required_headers - set(headers))
        if missing_headers:
            report.error(f"{name}: missing headers {', '.join(missing_headers)}")
        csv_rows[name] = rows

    coa_rows = csv_rows.get("chart-of-accounts.csv", [])
    duplicate_accounts = duplicate_values(coa_rows, "account_code")
    for value in duplicate_accounts:
        report.error(f"chart-of-accounts.csv duplicate account_code: {value}")
    coa_codes = {(row.get("account_code") or "").strip() for row in coa_rows if (row.get("account_code") or "").strip()}

    journal_rows = csv_rows.get("journal.csv", [])
    validate_journal(journal_rows, coa_codes, report)

    for name, field in [
        ("transaction-intake.csv", "intake_id"),
        ("evidence-register.csv", "document_id"),
        ("open-items.csv", "open_item_id"),
    ]:
        for value in duplicate_values(csv_rows.get(name, []), field):
            report.error(f"{name} duplicate {field}: {value}")

    if isinstance(manifest, dict) and not str(manifest.get("system_of_record", "")).strip():
        if args.stage in {"posting", "close"}:
            report.error("version-manifest.json: system_of_record is required for posting/close")
        else:
            report.warning("version-manifest.json: system_of_record is not set")

    profile = json_data.get("company-profile.json")
    if isinstance(profile, dict):
        for field in ["jurisdictions", "legal_form", "functional_currency", "accounting_system_of_record"]:
            if not profile.get(field):
                if args.stage in {"posting", "close"}:
                    report.error(f"company-profile.json: {field} is required for posting/close")
                else:
                    report.warning(f"company-profile.json: {field} is not set")

    if journal_rows and not coa_rows:
        report.error("journal.csv has rows but chart-of-accounts.csv is empty")

    if args.stage in {"posting", "close"}:
        if not coa_rows:
            report.error(f"{args.stage} stage requires a non-empty chart of accounts")
        if isinstance(policy_data, dict) and not policy_data.get("policies"):
            report.error(f"{args.stage} stage requires at least one accounting policy")

    print(f"Company Accounting Pack validation: {pack_dir}")
    print(f"Stage: {args.stage}")
    print(f"Errors: {len(report.errors)}")
    for message in report.errors:
        print(f"  ERROR: {message}")
    print(f"Warnings: {len(report.warnings)}")
    for message in report.warnings:
        print(f"  WARNING: {message}")
    readiness = "MECHANICALLY READY FOR REQUESTED STAGE" if not report.errors else "NOT READY FOR REQUESTED STAGE"
    if args.stage in {"onboarding", "draft"}:
        readiness += "; NOT READY FOR POSTING OR CLOSE"
    print(f"Readiness: {readiness}")
    print("Scope: structural controls only; no accounting, tax, legal, or audit conclusion.")
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
