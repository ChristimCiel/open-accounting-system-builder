# Open Accounting System Builder

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

## Privacy

Never commit a generated Company Accounting Pack or real accounting evidence to this repository. Review [SECURITY.md](SECURITY.md) before reporting a vulnerability or suspected data exposure.

## Contributing

Issues and pull requests are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) and keep examples synthetic and de-identified.

## Branding and attribution

**Open Accounting System Builder** is the project name. The Skill's stable technical ID is `company-accounting-system-builder`.

Apache-2.0 permits use, modification, and distribution. The license does not grant permission to imply endorsement by Tim Chen or to use the project name as the name of a materially different product. See [NOTICE](NOTICE) and [LICENSE](LICENSE).

If you find this project useful, attribution can be given as:

```text
Open Accounting System Builder, created by Tim Chen
https://github.com/ChristimCiel/open-accounting-system-builder
```

## 中文快速說明

這是一個由 **Tim Chen** 建立及維護的開源 AI Skill。它會先逐步訪談公司負責人、理解產業與商業模式，再協助建立公司專屬的會計政策、科目、憑證、分錄、對帳、月結與專業覆核流程。

共享 Repo 只保存方法與空白模板；每家公司產生的 Company Accounting Pack 必須另外私密保存。Skill 不會把老闆的確認誤當成會計師、記帳士、稅務或法律專業結論。

安裝後使用：

```text
請使用 $company-accounting-system-builder。先不要直接入帳；請逐步訪談我，建立產業會計地圖、適用準則、現況診斷與公司專屬 Accounting Pack。所有需要專業人士決定的事項都標記為 PROFESSIONAL_DECISION_REQUIRED。
```

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
