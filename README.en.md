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

- Starts with an owner-friendly feature menu instead of asking for accounting accounts.
- Preselects an AI-recommended scope that the owner can accept, change as a multi-select, or extend with custom features.
- Separates AI recommendations from owner confirmation and versions later additions, disablements, and priority changes.
- Keeps traceability, deduplication, journal balance, reconciliation, write previews, and professional boundaries mandatory even when optional features are disabled.
- Runs progressive interviews in small decision-focused rounds.
- Maps payment, fulfillment, revenue, cost, refund, and platform-settlement events.
- Distinguishes facts, AI proposals, official sources, open questions, and professional decisions.
- Recommends a spreadsheet, accounting system, or hybrid workflow based on actual needs.
- Creates policy, chart-of-accounts, journal, evidence, reconciliation, open-item, close, and version-control templates.
- Requires explicit data and persistence authorization before writing company information.
- Validates structure, required fields, duplicate keys, journal balance, gates, and posting readiness.
- Keeps statutory reporting, tax adjustments, and management views tied to one traceable accounting source.
- Generates both an accrual-basis profit-and-loss view and an owner dashboard from one double-entry journal containing only `POSTED` lines, without rebuilding the numbers from a second uncontrolled ledger.
- When O6 is enabled, lets the owner separately multi-select dashboard, profit, cost, data-trust, close, and custom management-reporting views.

## Install with Codex

Ask Codex:

```text
Use $skill-installer to install the public GitHub Skill from:

Repository: ChristimCiel/open-accounting-system-builder
Path: skills/company-accounting-system-builder
Ref: v1.3.0

Inspect SKILL.md and scripts before installation. If a Skill with the same name
already exists, stop and tell me instead of overwriting it. After installation,
tell me that it will be available on my next turn.
```

Then, on the next turn:

```text
Use $company-accounting-system-builder. Do not post transactions yet. First show
me an AI-preselected, multi-select feature menu. Let me accept the recommendation,
add or remove several outcomes at once, or define custom features. After I confirm,
interview me progressively and build only the selected parts of my company-specific
Accounting Pack. Mark anything requiring an accountant, tax professional,
auditor, or lawyer as PROFESSIONAL_DECISION_REQUIRED.
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

The first substantive question is always what the owner wants the system to do. The Skill shows eight plain-language outcomes, preselects recommendations from known context, and lets the owner reply with “accept recommendations,” add/remove several IDs at once, or describe a custom feature. AI recommendations do not become owner choices until the owner explicitly confirms them.

The owner can later type `modify features` to add, disable, reorder, or revise custom features. The Skill shows only the proposed differences, and changes take effect only after confirmation.

Before that confirmation, the Skill does not research standards, read sensitive data, create files, or silently choose a mode. After feature selection, it continues with progressive interviews:

1. Confirm feature priority, jurisdiction, legal form, operating stage, data scope, and storage location.
2. Understand products, services, payment, fulfillment, refund, platform, direct-cost, and management workflows.
3. Build an industry accounting map and obtain owner confirmation.
4. Research current official rules, standards versions, and effective dates for the applicable jurisdiction.
5. Diagnose current records and recommend one formal system of record.
6. Build company-specific policy, accounts, evidence, journal, reconciliation, and close workflows.
7. Test representative transactions before allowing formal writes.

High-judgment tax, revenue, shareholder, related-party, cross-border, payroll, inventory, fixed-asset, or similar matters are routed into a professional review pack instead of being presented as final conclusions.

## v1.3 management reporting

Version 1.3 separates the accounting source from the reporting presentation. The structured accrual profit-and-loss draft and the owner-facing dashboard must both be generated from the same `POSTED` journal. Management dimensions, allocations, or reclassifications remain traceable management adjustments and must not rewrite the formal journal.

The owner still multi-selects O1–O8 first. Only after the owner confirms O6 does the Skill expand these separately selectable reporting subfeatures:

- `dashboard`: an owner home screen focused on current profit or loss, available cash, where money is held up, and the next actions.
- `profit`: accrual profit and loss, how much remains from each 100 units of revenue, and period or target comparisons.
- `cost`: operating costs, operating expenses, major changes, and product, project, or channel views.
- `trust`: data cut-off, reconciliation status, estimates, missing evidence, conflicts, and items awaiting professional review.
- `close`: close progress, blockers, owners, and next actions.
- `custom`: owner-defined store, project, product, or other management views proposed by AI and enabled only after owner confirmation.

When the execution environment can create and verify spreadsheets, the primary deliverable is `management-dashboard.xlsx`. Otherwise, the Skill produces readable Markdown plus machine-readable JSON with the same definitions, sources, data-trust indicators, and open actions.

The dashboard must show accrual net income or loss separately from cash movement and available cash; it must never imply that profit means cash has already been collected. These are traceable internal-management outputs. Unless an appropriately qualified professional has provided a written conclusion for a stated scope and date, the Skill must not describe them as statutory financial statements, compliant with an accounting framework, professionally correct or reviewed, or ready for filing.

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
