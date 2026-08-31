#!/usr/bin/env python3
"""Run structural controls on a Company Accounting Pack.

Passing this validator does not establish accounting, tax, legal, or audit correctness.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

from validate_management_reporting import validate_management_reporting


REQUIRED_FILES = [
    "company-profile.json",
    "feature-selection.json",
    "interview-state.json",
    "industry-accounting-map.md",
    "applicable-framework.md",
    "system-recommendation.md",
    "accounting-policy-register.json",
    "allocation-policy-register.json",
    "chart-of-accounts.csv",
    "transaction-intake.csv",
    "journal.csv",
    "dimensions.csv",
    "management-attribution.csv",
    "management-adjustments.csv",
    "budgets.csv",
    "management-report-definition.json",
    "management-dashboard-config.json",
    "management-report.json",
    "management-dashboard.md",
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
        "account_code", "account_name", "account_type", "normal_balance", "pnl_category",
        "pnl_line_id", "cost_function", "cost_nature", "cost_traceability",
        "cost_behavior", "responsibility_center", "cash_classification", "allocation_policy_id",
        "dimension_required", "review_status"
    },
    "transaction-intake.csv": {
        "intake_id", "economic_event_id", "transaction_date", "description",
        "original_currency", "original_amount", "document_id", "dedup_status",
        "proposed_status"
    },
    "journal.csv": {
        "entry_id", "line_no", "entry_date", "economic_event_id", "account_code",
        "debit", "credit", "currency", "functional_debit", "functional_credit",
        "functional_amount", "fx_rate", "fx_source_ref", "dimension_project",
        "dimension_product", "dimension_channel", "dimension_location", "document_id",
        "policy_id", "posting_status"
    },
    "evidence-register.csv": {
        "document_id", "document_type", "source_locator", "document_date",
        "content_sha256", "economic_event_id", "completeness_status", "sensitivity_class"
    },
    "open-items.csv": {
        "open_item_id", "item_type", "description", "status", "owner", "next_action",
        "due_date", "blocks_close", "professional_review_required"
    },
    "dimensions.csv": {
        "dimension_id", "dimension_type", "dimension_name", "parent_id", "status",
        "effective_from", "effective_to"
    },
    "management-attribution.csv": {
        "attribution_id", "report_id", "entry_id", "line_no", "dimension_type",
        "dimension_id", "attribution_type", "ratio", "amount", "allocation_policy_id",
        "source_locator", "status"
    },
    "management-adjustments.csv": {
        "adjustment_id", "report_id", "period_start", "period_end", "line_id",
        "account_code", "dimension_id", "adjustment_type", "amount", "reason", "policy_id",
        "source_locator", "approved_by", "status", "reverse_on"
    },
    "budgets.csv": {
        "budget_id", "period_start", "period_end", "line_id", "dimension_id",
        "currency", "amount", "source_locator", "status", "approved_by", "approved_at"
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
CATALOG_FEATURE_IDS = {f"O{index}" for index in range(1, 9)}
FEATURE_LIFECYCLE_STATUSES = {
    "PROPOSED", "ENABLED", "DECLINED", "DISABLED", "OUT_OF_SCOPE"
}
FEATURE_RECOMMENDATIONS = {"AI_RECOMMENDED", "OPTIONAL", "NOT_RECOMMENDED"}
FEATURE_PRIORITIES = {"NOW", "NEXT", "LATER", "NOT_SELECTED"}
DEDUP_CLEAR_STATUSES = {"CLEAR", "NOT_DUPLICATE", "REVIEWED_CLEAR", "UNIQUE"}
COMPLETE_STATUSES = {"COMPLETE", "SUFFICIENT", "VERIFIED"}
COMPANY_PURPOSE_STATUSES = {"COMPANY", "CONFIRMED", "CONFIRMED_COMPANY"}
INTAKE_READY_STATUSES = {"OWNER_CONFIRMED", "POSTED", "READY_TO_POST"}
JOURNAL_POSTING_STATUSES = {"POSTED", "READY_TO_POST"}
RESOLVED_STATUSES = {"ANSWERED", "CLOSED", "IMPLEMENTED", "RESOLVED"}


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


def normalized_status(value: str) -> str:
    return (value or "").strip().upper().replace("-", "_").replace(" ", "_")


def boolean_value(value: str) -> bool:
    return normalized_status(value) in {"1", "TRUE", "YES", "Y"}


def markdown_has_substantive_content(path: Path) -> bool:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith(">"):
            continue
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            if cells and cells[0].lower() in {"period", "topic"}:
                continue
            if any(cell for cell in cells):
                return True
            continue
        if re.fullmatch(r"- [A-Za-z /]+:", line):
            continue
        if line not in {"-", "*"}:
            return True
    return False


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


def validate_feature_selection(data, stage: str, state, manifest, report: Report) -> None:
    if not isinstance(data, dict):
        report.error("feature-selection.json: must be an object")
        return

    required_top_level = {
        "schema_version", "catalog_version", "selection_mode", "revision",
        "selection_status", "features", "proposed_sequence",
        "selection_confirmation", "change_history", "updated_at",
    }
    missing = sorted(required_top_level - set(data))
    if missing:
        report.error(f"feature-selection.json: missing fields {', '.join(missing)}")
    if data.get("schema_version") != "1.0":
        report.error("feature-selection.json: schema_version must be '1.0'")
    if not str(data.get("catalog_version", "")).strip():
        report.error("feature-selection.json: catalog_version is required")
    if data.get("selection_mode") != "MULTI":
        report.error("feature-selection.json: selection_mode must be MULTI")

    revision = data.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        report.error("feature-selection.json: revision must be an integer >= 1")
        revision = None

    selection_status = data.get("selection_status")
    if selection_status not in {"DRAFT", "OWNER_CONFIRMED"}:
        report.error("feature-selection.json: invalid selection_status")

    features = data.get("features")
    if not isinstance(features, list):
        report.error("feature-selection.json: features must be an array")
        features = []

    required_feature_fields = {
        "feature_id", "name", "source", "lifecycle_status", "recommendation",
        "priority", "rationale", "basis_source_type", "basis_source_locator",
        "desired_outcome", "inputs", "outputs", "acceptance_criteria",
        "frequency", "dependencies", "professional_review_required",
        "risk_triggers",
    }
    seen_feature_ids: set[str] = set()
    enabled_feature_ids: set[str] = set()
    catalog_feature_ids: set[str] = set()
    disabled_feature_ids: set[str] = set()
    for index, feature in enumerate(features, start=1):
        if not isinstance(feature, dict):
            report.error(f"feature-selection.json: feature #{index} must be an object")
            continue
        missing_fields = sorted(required_feature_fields - set(feature))
        if missing_fields:
            report.error(
                f"feature-selection.json: feature #{index} missing fields {', '.join(missing_fields)}"
            )
        feature_id = str(feature.get("feature_id", "")).strip()
        if not feature_id:
            report.error(f"feature-selection.json: feature #{index} has blank feature_id")
        elif feature_id in seen_feature_ids:
            report.error(f"feature-selection.json: duplicate feature_id {feature_id}")
        seen_feature_ids.add(feature_id)

        source = feature.get("source")
        if source not in {"catalog", "custom"}:
            report.error(f"feature-selection.json: feature {feature_id or index} has invalid source")
        elif source == "catalog":
            catalog_feature_ids.add(feature_id)
            if feature_id not in CATALOG_FEATURE_IDS:
                report.error(f"feature-selection.json: unknown catalog feature_id {feature_id!r}")
        elif not feature_id.startswith("CUST-"):
            report.error(
                f"feature-selection.json: custom feature {feature_id or index} must use CUST- prefix"
            )

        lifecycle_status = feature.get("lifecycle_status")
        if lifecycle_status not in FEATURE_LIFECYCLE_STATUSES:
            report.error(
                f"feature-selection.json: feature {feature_id or index} has invalid lifecycle_status"
            )
        elif lifecycle_status == "ENABLED":
            enabled_feature_ids.add(feature_id)
        elif lifecycle_status == "DISABLED":
            disabled_feature_ids.add(feature_id)

        if feature.get("recommendation") not in FEATURE_RECOMMENDATIONS:
            report.error(
                f"feature-selection.json: feature {feature_id or index} has invalid recommendation"
            )
        if feature.get("priority") not in FEATURE_PRIORITIES:
            report.error(f"feature-selection.json: feature {feature_id or index} has invalid priority")
        if not str(feature.get("name", "")).strip():
            report.error(f"feature-selection.json: feature {feature_id or index} requires name")
        if not str(feature.get("rationale", "")).strip():
            report.error(f"feature-selection.json: feature {feature_id or index} requires rationale")
        for field in (
            "inputs", "outputs", "acceptance_criteria", "dependencies", "risk_triggers"
        ):
            value = feature.get(field)
            if not isinstance(value, list):
                report.error(
                    f"feature-selection.json: feature {feature_id or index} {field} must be an array"
                )
        if not isinstance(feature.get("professional_review_required"), bool):
            report.error(
                f"feature-selection.json: feature {feature_id or index} professional_review_required must be boolean"
            )
        if feature.get("recommendation") == "AI_RECOMMENDED":
            for field in ("basis_source_type", "basis_source_locator"):
                if not str(feature.get(field, "")).strip():
                    report.error(
                        f"feature-selection.json: AI recommendation {feature_id or index} requires {field}"
                    )
        if source == "custom":
            if not str(feature.get("desired_outcome", "")).strip():
                report.error(
                    f"feature-selection.json: custom feature {feature_id or index} requires desired_outcome"
                )
            for field in ("outputs", "acceptance_criteria"):
                value = feature.get(field)
                if isinstance(value, list) and not value:
                    report.error(
                        f"feature-selection.json: custom feature {feature_id or index} requires non-empty {field}"
                    )

    for feature in features:
        if not isinstance(feature, dict):
            continue
        feature_id = str(feature.get("feature_id", "")).strip()
        dependencies = feature.get("dependencies")
        if isinstance(dependencies, list):
            for dependency in dependencies:
                if dependency not in seen_feature_ids:
                    report.error(
                        f"feature-selection.json: feature {feature_id} has unknown dependency {dependency!r}"
                    )
                elif (
                    feature.get("lifecycle_status") == "ENABLED"
                    and dependency not in enabled_feature_ids
                ):
                    report.error(
                        f"feature-selection.json: enabled feature {feature_id} requires enabled dependency {dependency!r}"
                    )

    proposed_sequence = data.get("proposed_sequence")
    if not isinstance(proposed_sequence, list):
        report.error("feature-selection.json: proposed_sequence must be an array")
        proposed_sequence = []
    elif len(proposed_sequence) != len(set(proposed_sequence)):
        report.error("feature-selection.json: proposed_sequence contains duplicates")
    sequence_targets = (
        seen_feature_ids if selection_status == "DRAFT" else enabled_feature_ids
    )
    for feature_id in proposed_sequence:
        if feature_id not in sequence_targets:
            report.error(
                f"feature-selection.json: proposed_sequence item {feature_id!r} is not available for the current status"
            )

    confirmation = data.get("selection_confirmation")
    if not isinstance(confirmation, dict):
        report.error("feature-selection.json: selection_confirmation must be an object")
        confirmation = {}
    else:
        confirmation_required = {
            "status", "revision", "decision_reference", "confirmed_by",
            "confirmed_at", "source_locator",
        }
        missing_confirmation = sorted(confirmation_required - set(confirmation))
        if missing_confirmation:
            report.error(
                "feature-selection.json: selection_confirmation missing fields "
                + ", ".join(missing_confirmation)
            )

    change_history = data.get("change_history")
    if not isinstance(change_history, list):
        report.error("feature-selection.json: change_history must be an array")
        change_history = []
    history_fields = {
        "changed_at", "changed_by", "source_locator", "action", "reason",
        "previous_revision", "new_revision", "feature_ids",
    }
    for index, event in enumerate(change_history, start=1):
        if not isinstance(event, dict):
            report.error(f"feature-selection.json: change_history item {index} must be an object")
            continue
        missing_event = sorted(history_fields - set(event))
        if missing_event:
            report.error(
                f"feature-selection.json: change_history item {index} missing fields {', '.join(missing_event)}"
            )
        for field in ("changed_at", "changed_by", "source_locator", "action", "reason"):
            if not str(event.get(field, "")).strip():
                report.error(
                    f"feature-selection.json: change_history item {index} requires {field}"
                )
        if not isinstance(event.get("feature_ids"), list) or not event.get("feature_ids"):
            report.error(
                f"feature-selection.json: change_history item {index} requires non-empty feature_ids"
            )
        previous_revision = event.get("previous_revision")
        new_revision = event.get("new_revision")
        if (
            not isinstance(previous_revision, int)
            or isinstance(previous_revision, bool)
            or not isinstance(new_revision, int)
            or isinstance(new_revision, bool)
            or new_revision != previous_revision + 1
        ):
            report.error(
                f"feature-selection.json: change_history item {index} revisions must increase by one"
            )
        if revision is not None and isinstance(new_revision, int) and new_revision > revision:
            report.error(
                f"feature-selection.json: change_history item {index} exceeds current revision"
            )

    if revision is not None and revision > 1 and not change_history:
        report.error("feature-selection.json: revision > 1 requires change_history")
    if disabled_feature_ids and not change_history:
        report.error("feature-selection.json: disabled features require change_history")

    if selection_status == "DRAFT":
        report.warning("feature selection is draft; first-use F0 is not owner-confirmed")
        if any(
            isinstance(feature, dict)
            and feature.get("lifecycle_status") in {"ENABLED", "DECLINED", "DISABLED"}
            for feature in features
        ):
            report.error(
                "feature-selection.json: DRAFT cannot treat proposed choices as owner decisions"
            )
        if confirmation.get("status") != "NOT_CONFIRMED" or confirmation.get("revision") != 0:
            report.error("feature-selection.json: DRAFT must use an unconfirmed revision 0 confirmation")
    elif selection_status == "OWNER_CONFIRMED":
        if catalog_feature_ids != CATALOG_FEATURE_IDS:
            missing_catalog = sorted(CATALOG_FEATURE_IDS - catalog_feature_ids)
            extra_catalog = sorted(catalog_feature_ids - CATALOG_FEATURE_IDS)
            detail = []
            if missing_catalog:
                detail.append("missing " + ", ".join(missing_catalog))
            if extra_catalog:
                detail.append("unknown " + ", ".join(extra_catalog))
            report.error(
                "feature-selection.json: confirmed scope must preserve the full O1-O8 menu ("
                + "; ".join(detail)
                + ")"
            )
        if not enabled_feature_ids:
            report.error("feature-selection.json: confirmed scope requires at least one enabled feature")
        if any(
            isinstance(feature, dict) and feature.get("lifecycle_status") == "PROPOSED"
            for feature in features
        ):
            report.error("feature-selection.json: confirmed scope cannot contain PROPOSED features")
        if confirmation.get("status") != "CONFIRMED":
            report.error("feature-selection.json: owner-confirmed scope requires CONFIRMED confirmation")
        if revision is not None and confirmation.get("revision") != revision:
            report.error("feature-selection.json: confirmation revision must match current revision")
        for field in ("decision_reference", "confirmed_by", "confirmed_at", "source_locator"):
            if not str(confirmation.get(field, "")).strip():
                report.error(f"feature-selection.json: confirmed scope requires {field}")

        owner_decision_ids = set()
        if isinstance(state, dict) and isinstance(state.get("owner_confirmed_decisions"), list):
            owner_decision_ids = {
                str(item.get("id", "")).strip()
                for item in state["owner_confirmed_decisions"]
                if isinstance(item, dict)
            }
        if confirmation.get("decision_reference") not in owner_decision_ids:
            report.error(
                "feature-selection.json: decision_reference must match an owner_confirmed_decisions id"
            )
        if isinstance(state, dict) and state.get("feature_selection_revision") != revision:
            report.error(
                "interview-state.json: feature_selection_revision must match confirmed feature revision"
            )

    if isinstance(manifest, dict):
        expected_revision = revision if selection_status == "OWNER_CONFIRMED" else 0
        if manifest.get("feature_selection_revision") != expected_revision:
            report.error("version-manifest.json: feature_selection_revision does not match feature scope")
        if manifest.get("feature_selection_status") != selection_status:
            report.error("version-manifest.json: feature_selection_status does not match feature scope")

    if stage in {"posting", "close"} and selection_status != "OWNER_CONFIRMED":
        report.error(f"{stage} stage requires an owner-confirmed feature selection")


def validate_interview_state(data, stage: str, report: Report) -> None:
    if not isinstance(data, dict):
        report.error("interview-state.json: must be an object")
        return
    if data.get("schema_version") != "1.2":
        report.error("interview-state.json: schema_version must be '1.2'")
    if data.get("mode") not in {"setup", "migrate", "operate", "review"}:
        report.error("interview-state.json: invalid mode")
    planned_modes = data.get("planned_modes")
    if not isinstance(planned_modes, list):
        report.error("interview-state.json: planned_modes must be an array")
    else:
        invalid_modes = sorted(
            mode for mode in planned_modes
            if mode not in {"setup", "migrate", "operate", "review"}
        )
        if invalid_modes:
            report.error(
                "interview-state.json: planned_modes contains invalid values "
                + ", ".join(invalid_modes)
            )
        if len(planned_modes) != len(set(planned_modes)):
            report.error("interview-state.json: planned_modes contains duplicates")
    feature_selection_revision = data.get("feature_selection_revision")
    if (
        not isinstance(feature_selection_revision, int)
        or isinstance(feature_selection_revision, bool)
        or feature_selection_revision < 0
    ):
        report.error("interview-state.json: feature_selection_revision must be an integer >= 0")
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
        "status", "workflow_stage", "current_gate", "feature_selection_revision",
        "feature_selection_status", "management_report_revision",
        "management_report_status", "management_report_ledger_sha256",
        "management_workbook_status", "management_workbook_sha256",
        "management_workbook_chart_ids",
        "output_files", "validation", "generated_at", "updated_at"
    }
    missing = sorted(required - set(data))
    if missing:
        report.error(f"version-manifest.json: missing fields {', '.join(missing)}")
    if data.get("schema_version") != "1.4":
        report.error("version-manifest.json: schema_version must be '1.4'")
    if data.get("skill_version") != "1.4.0":
        report.error("version-manifest.json: skill_version must be '1.4.0'")
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

    workbook_status = str(data.get("management_workbook_status", "")).upper()
    workbook_hash = str(data.get("management_workbook_sha256", "")).lower()
    workbook_chart_ids = data.get("management_workbook_chart_ids")
    workbook_path = pack_dir / "management-dashboard.xlsx"
    if workbook_status not in {"NOT_GENERATED", "GENERATED", "VERIFIED"}:
        report.error("version-manifest.json: invalid management_workbook_status")
    if not isinstance(workbook_chart_ids, list) or len(workbook_chart_ids) != len(set(workbook_chart_ids)):
        report.error("version-manifest.json: management_workbook_chart_ids must be a unique array")
    if workbook_status == "NOT_GENERATED":
        if workbook_hash:
            report.error("version-manifest.json: NOT_GENERATED workbook cannot have a checksum")
        if workbook_path.is_file():
            report.error("version-manifest.json: management-dashboard.xlsx exists but status is NOT_GENERATED")
    elif workbook_status in {"GENERATED", "VERIFIED"}:
        if not workbook_path.is_file():
            report.error("version-manifest.json: generated management workbook is missing")
        elif not re.fullmatch(r"[0-9a-f]{64}", workbook_hash):
            report.error("version-manifest.json: management_workbook_sha256 must be 64 hex characters")
        elif hashlib.sha256(workbook_path.read_bytes()).hexdigest() != workbook_hash:
            report.error("version-manifest.json: management workbook checksum does not match file bytes")
        if not isinstance(outputs, list) or "management-dashboard.xlsx" not in outputs:
            report.error("version-manifest.json: generated workbook must be listed in output_files")
        if stage == "close" and workbook_status != "VERIFIED":
            report.error("version-manifest.json: close requires a generated workbook to be visually VERIFIED")


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


def validate_operational_controls(
    pack_dir: Path,
    stage: str,
    state,
    csv_rows: dict[str, list[dict[str, str]]],
    report: Report,
) -> None:
    if stage not in {"posting", "close"}:
        return

    if not isinstance(state, dict) or not state.get("official_sources_checked"):
        report.error(
            f"{stage} stage requires at least one current official source with applicability recorded"
        )

    professional_items = []
    if isinstance(state, dict) and isinstance(state.get("professional_review_items"), list):
        professional_items = state["professional_review_items"]
    if professional_items:
        report.error(
            f"{stage} stage cannot pass with unresolved professional_review_items"
        )

    evidence_rows = csv_rows.get("evidence-register.csv", [])
    evidence_ids: set[str] = set()
    for row_number, row in enumerate(evidence_rows, start=2):
        document_id = (row.get("document_id") or "").strip()
        if document_id:
            evidence_ids.add(document_id)
        if not (row.get("source_locator") or "").strip():
            report.error(f"evidence-register.csv row {row_number}: source_locator is required")
        if normalized_status(row.get("completeness_status", "")) not in COMPLETE_STATUSES:
            report.error(
                f"evidence-register.csv row {row_number}: completeness_status is not cleared"
            )

    intake_rows = csv_rows.get("transaction-intake.csv", [])
    intake_event_ids: set[str] = set()
    for row_number, row in enumerate(intake_rows, start=2):
        event_id = (row.get("economic_event_id") or "").strip()
        if not event_id:
            report.error(f"transaction-intake.csv row {row_number}: economic_event_id is required")
        else:
            intake_event_ids.add(event_id)
        for field in (
            "transaction_date", "description", "original_currency", "original_amount",
            "document_id",
        ):
            if not (row.get(field) or "").strip():
                report.error(f"transaction-intake.csv row {row_number}: {field} is required")
        document_id = (row.get("document_id") or "").strip()
        if document_id and document_id not in evidence_ids:
            report.error(
                f"transaction-intake.csv row {row_number}: document_id {document_id!r} is missing from evidence-register.csv"
            )
        if normalized_status(row.get("company_purpose_status", "")) not in COMPANY_PURPOSE_STATUSES:
            report.error(
                f"transaction-intake.csv row {row_number}: company_purpose_status is not confirmed"
            )
        if normalized_status(row.get("completeness_status", "")) not in COMPLETE_STATUSES:
            report.error(
                f"transaction-intake.csv row {row_number}: completeness_status is not cleared"
            )
        if normalized_status(row.get("dedup_status", "")) not in DEDUP_CLEAR_STATUSES:
            report.error(
                f"transaction-intake.csv row {row_number}: dedup_status is not cleared"
            )
        if normalized_status(row.get("proposed_status", "")) not in INTAKE_READY_STATUSES:
            report.error(
                f"transaction-intake.csv row {row_number}: proposed_status is not owner-confirmed or ready"
            )

    allowed_journal_statuses = {"POSTED"} if stage == "close" else JOURNAL_POSTING_STATUSES
    journal_rows = csv_rows.get("journal.csv", [])
    for row_number, row in enumerate(journal_rows, start=2):
        event_id = (row.get("economic_event_id") or "").strip()
        document_id = (row.get("document_id") or "").strip()
        policy_id = (row.get("policy_id") or "").strip()
        if not event_id:
            report.error(f"journal.csv row {row_number}: economic_event_id is required")
        elif event_id not in intake_event_ids:
            report.error(
                f"journal.csv row {row_number}: economic_event_id {event_id!r} is missing from transaction-intake.csv"
            )
        if not document_id:
            report.error(f"journal.csv row {row_number}: document_id is required")
        elif document_id not in evidence_ids:
            report.error(
                f"journal.csv row {row_number}: document_id {document_id!r} is missing from evidence-register.csv"
            )
        if not policy_id:
            report.error(f"journal.csv row {row_number}: policy_id is required")
        if not (row.get("approved_by") or "").strip():
            report.error(f"journal.csv row {row_number}: approved_by is required")
        if normalized_status(row.get("posting_status", "")) not in allowed_journal_statuses:
            report.error(
                f"journal.csv row {row_number}: posting_status is not valid for {stage}"
            )

    for row_number, row in enumerate(csv_rows.get("open-items.csv", []), start=2):
        unresolved = normalized_status(row.get("status", "")) not in RESOLVED_STATUSES
        if unresolved and boolean_value(row.get("professional_review_required", "")):
            report.error(
                f"open-items.csv row {row_number}: unresolved professional review blocks {stage}"
            )
        if stage == "close" and unresolved and boolean_value(row.get("blocks_close", "")):
            report.error(
                f"open-items.csv row {row_number}: unresolved blocks_close item prevents close"
            )

    if stage == "close":
        reconciliation_path = pack_dir / "reconciliations.md"
        if not markdown_has_substantive_content(reconciliation_path):
            report.error("reconciliations.md: close requires substantive reconciliation results")

        close_path = pack_dir / "monthly-close-checklist.md"
        try:
            close_text = close_path.read_text(encoding="utf-8")
        except OSError:
            close_text = ""
        if re.search(r"^- \[ \]", close_text, re.MULTILINE):
            report.error("monthly-close-checklist.md: close has unchecked control items")
        if re.search(r"^\s*- Status:\s*`?OPEN`?\s*$", close_text, re.MULTILINE | re.IGNORECASE):
            report.error("monthly-close-checklist.md: status is still OPEN")
        decision_match = re.search(
            r"^\s*- Decision to close or remain open:\s*(.+)$",
            close_text,
            re.MULTILINE | re.IGNORECASE,
        )
        if not decision_match or not decision_match.group(1).strip():
            report.error("monthly-close-checklist.md: close decision is required")


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
        "feature-selection.json",
        "interview-state.json",
        "accounting-policy-register.json",
        "allocation-policy-register.json",
        "management-report-definition.json",
        "management-dashboard-config.json",
        "management-report.json",
        "version-manifest.json",
    ]:
        path = pack_dir / name
        if path.is_file():
            json_data[name] = load_json(path, report)

    policy_data = json_data.get("accounting-policy-register.json")
    if policy_data is not None:
        validate_policy_register(policy_data, report)

    allocation_policy_data = json_data.get("allocation-policy-register.json")

    state = json_data.get("interview-state.json")
    if state is not None:
        validate_interview_state(state, args.stage, report)

    manifest = json_data.get("version-manifest.json")
    if manifest is not None:
        validate_manifest(manifest, pack_dir, args.stage, state, report)

    feature_selection = json_data.get("feature-selection.json")
    if feature_selection is not None:
        validate_feature_selection(
            feature_selection, args.stage, state, manifest, report
        )

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

    validate_operational_controls(pack_dir, args.stage, state, csv_rows, report)

    validate_management_reporting(
        pack_dir=pack_dir,
        stage=args.stage,
        profile=profile,
        feature_selection=feature_selection,
        policy_data=policy_data,
        allocation_policy_data=allocation_policy_data,
        manifest=manifest,
        definition=json_data.get("management-report-definition.json"),
        config=json_data.get("management-dashboard-config.json"),
        management_report=json_data.get("management-report.json"),
        csv_rows=csv_rows,
        report=report,
    )

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
