# Open Accounting System Builder

[繁體中文](README.md) | [English](README.en.md)

[![Validate](https://github.com/ChristimCiel/open-accounting-system-builder/actions/workflows/validate.yml/badge.svg)](https://github.com/ChristimCiel/open-accounting-system-builder/actions/workflows/validate.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

An open-source AI Skill that interviews a company owner, explains the accounting implications of the business model, researches the applicable current framework, and builds a company-specific, traceable accounting workflow.

Created and maintained by **Tim Chen**.

> This project helps organize accounting facts, controls, workflows, and questions for professional review. It is not accounting, tax, legal, audit, or filing advice.

## Why this project exists

Small companies often start with a mixed spreadsheet, incomplete evidence, and accounting rules that only one person understands. This Skill helps an AI collaborator turn that situation into a documented system without pretending that one company's policy fits every company.

It separates two layers:

1. The reusable open-source Skill in this repository.
2. A private **Company Accounting Pack** created separately for each company.

Company facts, transactions, account numbers, customer data, and professional review results belong in the private Company Accounting Pack—not in this repository.

## What it does

- Runs progressive interviews in small decision-focused rounds.
- Maps payment, fulfillment, revenue, cost, refund, and platform-settlement events.
- Distinguishes facts, AI proposals, official sources, open questions, and professional decisions.
- Recommends a spreadsheet, accounting system, or hybrid workflow based on actual needs.
- Creates policy, chart-of-accounts, journal, evidence, reconciliation, open-item, close, and version-control templates.
- Requires explicit data and persistence authorization before writing company information.
- Validates structure, required fields, duplicate keys, journal balance, gates, and posting readiness.
- Keeps statutory reporting, tax adjustments, and management views tied to one traceable accounting source.

## Install with Codex

Ask Codex:

```text
Use $skill-installer to install the public GitHub Skill from:

Repository: ChristimCiel/open-accounting-system-builder
Path: skills/company-accounting-system-builder
Ref: main

Inspect SKILL.md and scripts before installation. If a Skill with the same name
already exists, stop and tell me instead of overwriting it. After installation,
tell me that it will be available on my next turn.
```

Then, on the next turn:

```text
Use $company-accounting-system-builder. Do not post transactions yet.
Interview me progressively, explain the accounting implications of my industry,
research the current official framework for my jurisdiction, and build a
company-specific Accounting Pack. Mark anything requiring an accountant, tax
professional, auditor, or lawyer as PROFESSIONAL_DECISION_REQUIRED.
```

The installer places the Skill under the user's Codex Skills directory. Other AI products may be able to read the repository but cannot necessarily install or persist local Skills.

## Manual installation

Copy only this directory into your Codex Skills directory:

```text
skills/company-accounting-system-builder
```

The installed folder name must remain:

```text
company-accounting-system-builder
```

Restart or reload the agent if it does not discover the Skill immediately.

## First-use workflow

The Skill begins with progressive interviews rather than asking the owner to choose accounting accounts immediately:

1. Confirm jurisdiction, legal form, operating stage, goals, data scope, and storage location.
2. Understand products, services, payment, fulfillment, refund, platform, direct-cost, and management workflows.
3. Build an industry accounting map and obtain owner confirmation.
4. Research current official rules, standards versions, and effective dates for the applicable jurisdiction.
5. Diagnose current records and recommend one formal system of record.
6. Build company-specific policy, accounts, evidence, journal, reconciliation, and close workflows.
7. Test representative transactions before allowing formal writes.

High-judgment tax, revenue, shareholder, related-party, cross-border, payroll, inventory, fixed-asset, or similar matters are routed into a professional review pack instead of being presented as final conclusions.

## Repository layout

```text
skills/company-accounting-system-builder/
├── SKILL.md
├── agents/openai.yaml
├── assets/templates/
├── references/
└── scripts/
```

The repository root contains only project governance, validation, release, and contribution files. No real company ledger is included.

## Validation

Run:

```bash
python3 scripts/validate_repository.py
```

To test Company Accounting Pack initialization and onboarding controls:

```bash
python3 skills/company-accounting-system-builder/scripts/init_company_pack.py \
  /path/to/private/accounting-system \
  --authorization-reference "conversation:explicit-user-authorization" \
  --authorized-by "company-owner"

python3 skills/company-accounting-system-builder/scripts/validate_company_pack.py \
  /path/to/private/accounting-system \
  --stage onboarding
```

Passing validation only establishes the listed mechanical controls. It never establishes accounting, tax, legal, audit, or filing correctness.

## Privacy and security

Never commit a generated Company Accounting Pack or real accounting evidence to this repository. Review [SECURITY.md](SECURITY.md) before reporting a vulnerability or suspected data exposure.

## Contributing

Issues and pull requests are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) and keep examples synthetic and de-identified.

## Branding and attribution

**Open Accounting System Builder** is the project name. The Skill's stable technical ID is `company-accounting-system-builder`.

Apache-2.0 permits use, modification, and distribution. The license does not grant permission to imply endorsement by Tim Chen or to use the project name as the name of a materially different product. See [NOTICE](NOTICE) and [LICENSE](LICENSE).

Suggested attribution:

```text
Open Accounting System Builder, created by Tim Chen
https://github.com/ChristimCiel/open-accounting-system-builder
```

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
