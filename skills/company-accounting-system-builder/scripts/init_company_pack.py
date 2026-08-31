#!/usr/bin/env python3
"""Initialize a Company Accounting Pack without overwriting existing files."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


MARKDOWN_SKELETONS = {
    "industry-accounting-map.md": """# Industry Accounting Map

## Business model confirmed by owner

## Revenue and fulfillment lifecycles

## Direct costs and operating expenses

## Payment channels and reconciliations

## Common evidence

## Management metrics

## Open questions and professional decisions
""",
    "applicable-framework.md": """# Applicable Framework

> Record facts, provisional conclusions, status, official sources, checked dates, conditions, and professional review requirements separately.

| Topic | User facts | Provisional conclusion | Status | Official source | Checked on | Conditions / exceptions | Professional confirmation | Recheck trigger |
|---|---|---|---|---|---|---|---|---|
""",
    "system-recommendation.md": """# System Recommendation

## Recommended system of record

## Why it fits now

## Required controls

## Tradeoffs

## Upgrade triggers

## Assumptions and open questions
""",
    "reconciliations.md": """# Reconciliations

| Period | Source A | Source B | Difference | Cause | Owner | Next action | Due date | Blocks close | Status |
|---|---|---:|---:|---:|---|---|---|---|---|
""",
    "change-log.md": """# Change Log

| Changed at | Version | Changed by | Reviewed by | Before | After | Reason | Source | Effective date | Retrospective impact |
|---|---|---|---|---|---|---|---|---|---|
""",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a Company Accounting Pack from sanitized templates."
    )
    parser.add_argument("output_dir", help="Authorized output directory")
    parser.add_argument(
        "--authorization-reference",
        required=True,
        help="Traceable user or outer-instruction reference authorizing this directory and persistence scope",
    )
    parser.add_argument(
        "--authorized-by",
        default="user",
        help="Role or identifier that granted persistence authorization (default: user)",
    )
    parser.add_argument(
        "--repair-authorization",
        action="store_true",
        help="After review, replace invalid authorization metadata in an existing state file",
    )
    args = parser.parse_args()

    authorization_reference = args.authorization_reference.strip()
    authorized_by = args.authorized_by.strip()
    if not authorization_reference:
        parser.error("--authorization-reference must not be blank")
    if not authorized_by:
        parser.error("--authorized-by must not be blank")

    output_dir = Path(args.output_dir).expanduser().resolve()
    template_dir = Path(__file__).resolve().parents[1] / "assets" / "templates"

    state_path = output_dir / "interview-state.json"
    repair_existing_state = False
    if state_path.is_file():
        try:
            existing_state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"existing interview-state.json is unreadable: {exc}")
        existing_auth = existing_state.get("persistence_authorization")
        valid_existing_auth = (
            isinstance(existing_auth, dict)
            and existing_auth.get("status") == "GRANTED"
            and all(
                str(existing_auth.get(field, "")).strip()
                for field in ("source_type", "source_locator", "authorized_by", "authorized_at")
            )
            and isinstance(existing_auth.get("scope"), list)
            and bool(existing_auth.get("scope"))
        )
        if not valid_existing_auth and not args.repair_authorization:
            parser.error(
                "existing interview-state.json has invalid authorization metadata; "
                "review it, then rerun with --repair-authorization to replace only that metadata"
            )
        repair_existing_state = not valid_existing_auth and args.repair_authorization

    output_dir.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    skipped: list[Path] = []

    for source in sorted(template_dir.iterdir()):
        if not source.is_file():
            continue
        target = output_dir / source.name
        if target.exists():
            skipped.append(target)
            continue
        shutil.copy2(source, target)
        created.append(target)

    for name, content in MARKDOWN_SKELETONS.items():
        target = output_dir / name
        if target.exists():
            skipped.append(target)
            continue
        target.write_text(content, encoding="utf-8")
        created.append(target)

    created_names = {path.name for path in created}
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    if "interview-state.json" in created_names or repair_existing_state:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["persistence_authorization"] = {
            "status": "GRANTED",
            "source_type": "explicit_user_or_outer_instruction",
            "source_locator": authorization_reference,
            "scope": [f"initialize_company_pack:{output_dir}"],
            "authorized_by": authorized_by,
            "authorized_at": now,
        }
        state["updated_at"] = now
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    manifest_path = output_dir / "version-manifest.json"
    if "version-manifest.json" in created_names:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["generated_at"] = now
        manifest["updated_at"] = now
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    print(f"Company Accounting Pack: {output_dir}")
    print(f"Created: {len(created)}")
    for path in created:
        print(f"  + {path.name}")
    print(f"Preserved existing: {len(skipped)}")
    for path in skipped:
        print(f"  = {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
