#!/usr/bin/env python3
"""Validate the public repository and exercise safe onboarding gates."""

from __future__ import annotations

import ast
import csv
import json
import re
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
    "references/standards-research.md",
    "references/deliverable-contract.md",
    "assets/templates/interview-state.json",
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
                'version: "1.1.0"',
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
