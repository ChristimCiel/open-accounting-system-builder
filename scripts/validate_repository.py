#!/usr/bin/env python3
"""Validate the public repository and exercise safe onboarding gates."""

from __future__ import annotations

import ast
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "company-accounting-system-builder"
REQUIRED_ROOT_FILES = {
    "README.md",
    "README.en.md",
    "LICENSE",
    "NOTICE",
    "CITATION.cff",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "DISCLAIMER.md",
    "SECURITY.md",
    ".gitignore",
    ".github/workflows/validate.yml",
}
REQUIRED_SKILL_PATHS = {
    "SKILL.md",
    "agents/openai.yaml",
    "scripts/init_company_pack.py",
    "scripts/validate_company_pack.py",
    "references/onboarding-interview.md",
    "references/feature-customization.md",
    "references/standards-research.md",
    "references/deliverable-contract.md",
    "assets/templates/interview-state.json",
    "assets/templates/feature-selection.json",
    "assets/templates/version-manifest.json",
}
FORBIDDEN_SUFFIXES = {".xlsx", ".xls", ".pdf", ".pem", ".key", ".p12", ".zip"}


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


def main() -> int:
    errors: list[str] = []

    for relative in sorted(REQUIRED_ROOT_FILES):
        if not (ROOT / relative).is_file():
            errors.append(f"missing repository file: {relative}")
    for relative in sorted(REQUIRED_SKILL_PATHS):
        if not (SKILL / relative).is_file():
            errors.append(f"missing skill file: {relative}")

    for path in ROOT.rglob("*"):
        if ".git" in path.parts:
            continue
        if path.is_symlink():
            errors.append(f"symlink is not allowed in release source: {path.relative_to(ROOT)}")
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden release file type: {path.relative_to(ROOT)}")

    skill_md = SKILL / "SKILL.md"
    if skill_md.is_file():
        text = skill_md.read_text(encoding="utf-8")
        frontmatter = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        if not frontmatter:
            errors.append("SKILL.md has invalid YAML frontmatter delimiters")
        else:
            header = frontmatter.group(1)
            for expected in (
                "name: company-accounting-system-builder",
                'version: "1.2.0"',
                'author: "Tim Chen"',
                'license: "Apache-2.0"',
            ):
                if expected not in header:
                    errors.append(f"SKILL.md frontmatter missing {expected!r}")
            if not re.search(r"^description:\s*\S", header, re.MULTILINE):
                errors.append("SKILL.md frontmatter has no description")

        if re.search(r"/Users/|[A-Za-z]:\\Users\\", text):
            errors.append("SKILL.md contains a local user path")

    readme_zh = ROOT / "README.md"
    readme_en = ROOT / "README.en.md"
    if readme_zh.is_file() and "[English](README.en.md)" not in readme_zh.read_text(encoding="utf-8"):
        errors.append("README.md is missing the English language link")
    if readme_en.is_file() and "[繁體中文](README.md)" not in readme_en.read_text(encoding="utf-8"):
        errors.append("README.en.md is missing the Traditional Chinese language link")

    for path in SKILL.rglob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid JSON {path.relative_to(ROOT)}: {exc}")

    for path in SKILL.rglob("*.csv"):
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                headers = next(csv.reader(handle), [])
            if not headers or any(not value.strip() for value in headers):
                errors.append(f"invalid CSV header: {path.relative_to(ROOT)}")
        except OSError as exc:
            errors.append(f"unreadable CSV {path.relative_to(ROOT)}: {exc}")

    for path in SKILL.rglob("*.py"):
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as exc:
            errors.append(f"invalid Python {path.relative_to(ROOT)}: {exc}")

    init_script = SKILL / "scripts" / "init_company_pack.py"
    validate_script = SKILL / "scripts" / "validate_company_pack.py"
    if init_script.is_file() and validate_script.is_file():
        with tempfile.TemporaryDirectory(prefix="open-accounting-system-builder-") as temp:
            temp_root = Path(temp)
            rejected_pack = temp_root / "rejected-pack"
            blank_auth = run([
                sys.executable,
                str(init_script),
                str(rejected_pack),
                "--authorization-reference",
                "   ",
                "--authorized-by",
                "ci",
            ])
            if blank_auth.returncode == 0 or rejected_pack.exists():
                errors.append("blank authorization was not rejected before file creation")

            pack = temp_root / "accounting-system"
            initialized = run([
                sys.executable,
                str(init_script),
                str(pack),
                "--authorization-reference",
                "ci:synthetic-explicit-authorization",
                "--authorized-by",
                "github-actions",
            ])
            if initialized.returncode != 0:
                errors.append(f"authorized initialization failed: {initialized.stderr.strip()}")
            else:
                onboarding = run([
                    sys.executable,
                    str(validate_script),
                    str(pack),
                    "--stage",
                    "onboarding",
                ])
                if onboarding.returncode != 0:
                    errors.append(f"onboarding validation failed: {onboarding.stdout.strip()}")
                if "NOT READY FOR POSTING OR CLOSE" not in onboarding.stdout:
                    errors.append("onboarding output does not state posting/close is not ready")
                if "first-use F0 is not owner-confirmed" not in onboarding.stdout:
                    errors.append("blank onboarding does not state feature selection is unconfirmed")

                invalid_draft_pack = temp_root / "invalid-draft-feature-pack"
                shutil.copytree(pack, invalid_draft_pack)
                invalid_feature_path = invalid_draft_pack / "feature-selection.json"
                invalid_feature = json.loads(invalid_feature_path.read_text(encoding="utf-8"))
                invalid_feature["features"] = [{
                    "feature_id": "O1",
                    "name": "Understand industry accounting",
                    "source": "catalog",
                    "lifecycle_status": "ENABLED",
                    "recommendation": "AI_RECOMMENDED",
                    "priority": "NOW",
                    "rationale": "Synthetic recommendation for validation.",
                    "basis_source_type": "synthetic_test",
                    "basis_source_locator": "ci:F0-draft",
                    "desired_outcome": "An industry accounting map.",
                    "inputs": [],
                    "outputs": ["industry-accounting-map.md"],
                    "acceptance_criteria": ["Owner can verify the business lifecycle."],
                    "frequency": "once_then_on_change",
                    "dependencies": [],
                    "professional_review_required": False,
                    "risk_triggers": [],
                }]
                invalid_feature_path.write_text(
                    json.dumps(invalid_feature, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                invalid_draft = run([
                    sys.executable,
                    str(validate_script),
                    str(invalid_draft_pack),
                    "--stage",
                    "onboarding",
                ])
                if invalid_draft.returncode == 0:
                    errors.append("draft feature recommendation incorrectly became an enabled owner choice")

                confirmed_pack = temp_root / "confirmed-multi-select-pack"
                shutil.copytree(pack, confirmed_pack)
                confirmed_feature_path = confirmed_pack / "feature-selection.json"
                confirmed_feature = json.loads(
                    confirmed_feature_path.read_text(encoding="utf-8")
                )
                feature_names = {
                    "O1": "Understand industry accounting",
                    "O2": "Diagnose current records",
                    "O3": "Build internal accounting rules",
                    "O4": "Migrate existing records",
                    "O5": "Operate daily bookkeeping",
                    "O6": "Reconcile and close",
                    "O7": "Prepare professional handoff",
                    "O8": "Automate and integrate",
                }
                confirmed_feature["selection_status"] = "OWNER_CONFIRMED"
                confirmed_feature["features"] = []
                for feature_id, name in feature_names.items():
                    recommended = feature_id in {"O1", "O2"}
                    enabled = feature_id in {"O1", "O2", "O6"}
                    confirmed_feature["features"].append({
                        "feature_id": feature_id,
                        "name": name,
                        "source": "catalog",
                        "lifecycle_status": "ENABLED" if enabled else "DECLINED",
                        "recommendation": "AI_RECOMMENDED" if recommended else "OPTIONAL",
                        "priority": "NOW" if enabled else "NOT_SELECTED",
                        "rationale": "Synthetic F0 selection for repository validation.",
                        "basis_source_type": "synthetic_test" if recommended else "",
                        "basis_source_locator": "ci:F0-confirmed" if recommended else "",
                        "desired_outcome": name,
                        "inputs": [],
                        "outputs": [name],
                        "acceptance_criteria": ["Owner confirms the requested outcome."],
                        "frequency": "configured_during_onboarding",
                        "dependencies": [],
                        "professional_review_required": feature_id == "O7",
                        "risk_triggers": [],
                    })
                confirmed_feature["proposed_sequence"] = ["O1", "O2", "O6"]
                confirmed_feature["selection_confirmation"] = {
                    "status": "CONFIRMED",
                    "revision": 1,
                    "decision_reference": "DEC-F0-001",
                    "confirmed_by": "synthetic-owner",
                    "confirmed_at": "2026-08-31T00:00:00+00:00",
                    "source_locator": "ci:F0-confirmed",
                }
                confirmed_feature["updated_at"] = "2026-08-31T00:00:00+00:00"
                confirmed_feature_path.write_text(
                    json.dumps(confirmed_feature, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

                confirmed_state_path = confirmed_pack / "interview-state.json"
                confirmed_state = json.loads(
                    confirmed_state_path.read_text(encoding="utf-8")
                )
                confirmed_state["planned_modes"] = ["setup"]
                confirmed_state["feature_selection_revision"] = 1
                confirmed_state["owner_confirmed_decisions"].append({
                    "id": "DEC-F0-001",
                    "status": "FACT",
                    "statement": "Owner confirmed O1, O2, and O6 and declined the other catalog outcomes.",
                    "source_type": "explicit_user_confirmation",
                    "source_locator": "ci:F0-confirmed",
                    "confirmed_by": "synthetic-owner",
                    "confirmed_at": "2026-08-31T00:00:00+00:00",
                    "affects": ["feature-selection.json"],
                })
                confirmed_state_path.write_text(
                    json.dumps(confirmed_state, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

                confirmed_manifest_path = confirmed_pack / "version-manifest.json"
                confirmed_manifest = json.loads(
                    confirmed_manifest_path.read_text(encoding="utf-8")
                )
                confirmed_manifest["feature_selection_revision"] = 1
                confirmed_manifest["feature_selection_status"] = "OWNER_CONFIRMED"
                confirmed_manifest_path.write_text(
                    json.dumps(confirmed_manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

                confirmed_multi_select = run([
                    sys.executable,
                    str(validate_script),
                    str(confirmed_pack),
                    "--stage",
                    "onboarding",
                ])
                if confirmed_multi_select.returncode != 0:
                    errors.append(
                        "owner-confirmed multi-select feature scope failed: "
                        + confirmed_multi_select.stdout.strip()
                    )

                bypass_pack = temp_root / "feature-disable-bypass-pack"
                shutil.copytree(confirmed_pack, bypass_pack)
                bypass_state_path = bypass_pack / "interview-state.json"
                bypass_state = json.loads(bypass_state_path.read_text(encoding="utf-8"))
                bypass_state["workflow_stage"] = "posting"
                bypass_state["readiness"] = "READY_FOR_POSTING"
                bypass_state["current_gate"] = "G4"
                for gate in ("G0", "G1", "G2", "G3", "G4"):
                    bypass_state["gates"][gate] = {
                        "status": "CONFIRMED",
                        "confirmed_by": "synthetic-owner",
                        "confirmed_at": "2026-08-31T00:02:00+00:00",
                        "evidence": ["ci:synthetic-gate"],
                    }
                bypass_state["confirmed_facts"].append({
                    "id": "FACT-READY-001",
                    "status": "FACT",
                    "statement": "Synthetic company identity and system of record are confirmed.",
                    "source_type": "synthetic_test",
                    "source_locator": "ci:posting-bypass",
                    "confirmed_by": "synthetic-owner",
                    "confirmed_at": "2026-08-31T00:02:00+00:00",
                    "affects": ["posting"],
                })
                bypass_state["professional_review_items"].append({
                    "id": "PRO-UNRESOLVED-001",
                    "status": "PROFESSIONAL_DECISION_REQUIRED",
                    "statement": "Synthetic unresolved tax treatment.",
                    "source_type": "synthetic_test",
                    "source_locator": "ci:posting-bypass",
                    "confirmed_by": "",
                    "confirmed_at": "",
                    "affects": ["posting"],
                })
                bypass_state_path.write_text(
                    json.dumps(bypass_state, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

                bypass_profile_path = bypass_pack / "company-profile.json"
                bypass_profile = json.loads(bypass_profile_path.read_text(encoding="utf-8"))
                bypass_profile.update({
                    "jurisdictions": ["TW"],
                    "legal_form": "company",
                    "functional_currency": "TWD",
                    "accounting_system_of_record": "synthetic-ledger",
                })
                bypass_profile_path.write_text(
                    json.dumps(bypass_profile, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

                bypass_manifest_path = bypass_pack / "version-manifest.json"
                bypass_manifest = json.loads(bypass_manifest_path.read_text(encoding="utf-8"))
                bypass_manifest.update({
                    "status": "READY_FOR_POSTING",
                    "workflow_stage": "posting",
                    "current_gate": "G4",
                    "system_of_record": "synthetic-ledger",
                })
                bypass_manifest["validation"]["stage"] = "posting"
                bypass_manifest_path.write_text(
                    json.dumps(bypass_manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

                (bypass_pack / "chart-of-accounts.csv").write_text(
                    "account_code,account_name,account_type,normal_balance,scope,do_not_use_for,review_status,effective_from,active\n"
                    "1000,Synthetic cash,asset,debit,synthetic,,owner_confirmed,2026-08-31,true\n"
                    "5000,Synthetic expense,expense,debit,synthetic,,owner_confirmed,2026-08-31,true\n",
                    encoding="utf-8",
                )
                bypass_policy_path = bypass_pack / "accounting-policy-register.json"
                bypass_policy = json.loads(bypass_policy_path.read_text(encoding="utf-8"))
                bypass_policy["policies"] = [{
                    "policy_id": "POL-SYNTH-001",
                    "statement": "Synthetic policy used only to exercise validator gates.",
                    "scope": ["synthetic"],
                    "rationale": "Repository validation.",
                    "evidence_or_source": ["ci:posting-bypass"],
                    "assumptions": [],
                    "status": "owner_confirmed",
                    "decision_owner": "synthetic-owner",
                    "effective_from": "2026-08-31",
                    "supersedes": "",
                    "review_due": "2026-09-30",
                }]
                bypass_policy_path.write_text(
                    json.dumps(bypass_policy, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

                synthetic_rows = {
                    "evidence-register.csv": {
                        "document_id": "DOC-UNSAFE-001",
                        "document_type": "synthetic",
                        "source_locator": "",
                        "document_date": "2026-08-31",
                        "economic_event_id": "EV-UNSAFE-001",
                        "completeness_status": "MISSING",
                        "sensitivity_class": "INTERNAL",
                    },
                    "transaction-intake.csv": {
                        "intake_id": "INT-UNSAFE-001",
                        "economic_event_id": "EV-UNSAFE-001",
                        "transaction_date": "2026-08-31",
                        "description": "Synthetic unsafe transaction",
                        "original_currency": "TWD",
                        "original_amount": "100",
                        "document_id": "DOC-UNSAFE-001",
                        "company_purpose_status": "UNKNOWN",
                        "completeness_status": "MISSING",
                        "dedup_status": "UNCHECKED",
                        "proposed_status": "DRAFT",
                    },
                }
                for csv_name, row in synthetic_rows.items():
                    csv_path = bypass_pack / csv_name
                    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                        fieldnames = next(csv.reader(handle))
                    with csv_path.open("w", encoding="utf-8", newline="") as handle:
                        writer = csv.DictWriter(handle, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerow(row)

                journal_path = bypass_pack / "journal.csv"
                with journal_path.open("r", encoding="utf-8-sig", newline="") as handle:
                    journal_fields = next(csv.reader(handle))
                with journal_path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=journal_fields)
                    writer.writeheader()
                    for line_no, account_code, debit, credit in (
                        ("1", "5000", "100", ""),
                        ("2", "1000", "", "100"),
                    ):
                        writer.writerow({
                            "entry_id": "JE-UNSAFE-001",
                            "line_no": line_no,
                            "entry_date": "2026-08-31",
                            "economic_event_id": "EV-UNSAFE-001",
                            "account_code": account_code,
                            "debit": debit,
                            "credit": credit,
                            "currency": "TWD",
                            "document_id": "DOC-UNSAFE-001",
                            "policy_id": "POL-SYNTH-001",
                            "posting_status": "DRAFT",
                            "prepared_by": "synthetic-preparer",
                            "approved_by": "",
                        })

                bypass_validation = run([
                    sys.executable,
                    str(validate_script),
                    str(bypass_pack),
                    "--stage",
                    "posting",
                ])
                if bypass_validation.returncode == 0:
                    errors.append("disabled optional features bypassed fixed posting controls")
                for expected_control in (
                    "requires at least one current official source",
                    "cannot pass with unresolved professional_review_items",
                    "source_locator is required",
                    "dedup_status is not cleared",
                    "posting_status is not valid for posting",
                ):
                    if expected_control not in bypass_validation.stdout:
                        errors.append(
                            f"posting bypass test did not enforce control: {expected_control}"
                        )

                custom_pack = temp_root / "custom-feature-pack"
                shutil.copytree(confirmed_pack, custom_pack)
                custom_feature_path = custom_pack / "feature-selection.json"
                custom_feature = json.loads(custom_feature_path.read_text(encoding="utf-8"))
                custom_feature["revision"] = 2
                custom_feature["selection_confirmation"] = {
                    "status": "CONFIRMED",
                    "revision": 2,
                    "decision_reference": "DEC-F0-002",
                    "confirmed_by": "synthetic-owner",
                    "confirmed_at": "2026-08-31T00:01:00+00:00",
                    "source_locator": "ci:F0-custom-confirmed",
                }
                custom_feature["change_history"] = [{
                    "changed_at": "2026-08-31T00:01:00+00:00",
                    "changed_by": "synthetic-owner",
                    "source_locator": "ci:F0-custom-confirmed",
                    "action": "ADD_CUSTOM_FEATURE",
                    "reason": "Owner requested store-level profitability.",
                    "previous_revision": 1,
                    "new_revision": 2,
                    "feature_ids": ["CUST-STORE-PROFIT"],
                }]
                custom_feature["features"].append({
                    "feature_id": "CUST-STORE-PROFIT",
                    "name": "Store-level profit view",
                    "source": "custom",
                    "lifecycle_status": "ENABLED",
                    "recommendation": "OPTIONAL",
                    "priority": "NEXT",
                    "rationale": "Synthetic owner-added feature.",
                    "basis_source_type": "explicit_user_confirmation",
                    "basis_source_locator": "ci:F0-confirmed",
                    "desired_outcome": "Compare profit by store.",
                    "inputs": ["store", "revenue", "direct_cost"],
                    "outputs": ["store profit report"],
                    "acceptance_criteria": ["Each transaction maps to a store or an open item."],
                    "frequency": "monthly",
                    "dependencies": ["O6"],
                    "professional_review_required": False,
                    "risk_triggers": ["shared cost allocation"],
                })
                custom_feature["proposed_sequence"] = ["O1", "O2", "O6", "CUST-STORE-PROFIT"]
                custom_feature_path.write_text(
                    json.dumps(custom_feature, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                custom_state_path = custom_pack / "interview-state.json"
                custom_state = json.loads(custom_state_path.read_text(encoding="utf-8"))
                custom_state["feature_selection_revision"] = 2
                custom_state["owner_confirmed_decisions"].append({
                    "id": "DEC-F0-002",
                    "status": "FACT",
                    "statement": "Owner added the custom store-level profit feature.",
                    "source_type": "explicit_user_confirmation",
                    "source_locator": "ci:F0-custom-confirmed",
                    "confirmed_by": "synthetic-owner",
                    "confirmed_at": "2026-08-31T00:01:00+00:00",
                    "affects": ["feature-selection.json"],
                })
                custom_state_path.write_text(
                    json.dumps(custom_state, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                custom_manifest_path = custom_pack / "version-manifest.json"
                custom_manifest = json.loads(custom_manifest_path.read_text(encoding="utf-8"))
                custom_manifest["feature_selection_revision"] = 2
                custom_manifest_path.write_text(
                    json.dumps(custom_manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                custom_feature_validation = run([
                    sys.executable,
                    str(validate_script),
                    str(custom_pack),
                    "--stage",
                    "onboarding",
                ])
                if custom_feature_validation.returncode != 0:
                    errors.append(
                        "valid custom feature failed: "
                        + custom_feature_validation.stdout.strip()
                    )

                invalid_custom_pack = temp_root / "invalid-custom-feature-pack"
                shutil.copytree(custom_pack, invalid_custom_pack)
                invalid_custom_path = invalid_custom_pack / "feature-selection.json"
                invalid_custom = json.loads(invalid_custom_path.read_text(encoding="utf-8"))
                invalid_custom["features"][-1]["acceptance_criteria"] = []
                invalid_custom_path.write_text(
                    json.dumps(invalid_custom, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                invalid_custom_validation = run([
                    sys.executable,
                    str(validate_script),
                    str(invalid_custom_pack),
                    "--stage",
                    "onboarding",
                ])
                if invalid_custom_validation.returncode == 0:
                    errors.append("incomplete custom feature incorrectly passed validation")

                posting = run([
                    sys.executable,
                    str(validate_script),
                    str(pack),
                    "--stage",
                    "posting",
                ])
                if posting.returncode == 0:
                    errors.append("empty scaffold incorrectly passed posting validation")

    if errors:
        print("Repository validation failed:")
        for error in errors:
            print(f"  ERROR: {error}")
        return 1

    print("Repository validation passed.")
    print("Scope: package structure and mechanical controls only; no professional conclusion.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
