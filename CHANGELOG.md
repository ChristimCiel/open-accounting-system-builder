# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use semantic versioning.

## [Unreleased]

## [1.4.0] - 2026-08-31

### Added

- Owner-confirmed chart multi-select with recommended ledger-vs-management P&L columns, positive/negative P&L bridge columns, cost bars, an optional cost doughnut, and dimension-profit columns.
- Native Excel workbook renderer with `Dashboard`, `P&L`, `Cost Analysis`, `Dimension Profit`, `Chart Data`, `Data & Lineage`, and `Checks` sheets.
- Exported-workbook verifier that re-imports XLSX files, counts native chart objects, scans formula errors, inspects key ranges, and renders a visual QA preview.
- Workbook renderer checksum and manifest fields for workbook status, output checksum, and chart IDs.

### Changed

- Management reporting now requires an answered `Q-VISUAL` owner question before close.
- Chart sources use visible formulas linked to the validated report snapshot instead of embedded chart values.
- Company Pack manifest schema is now 1.4 and the Skill version is 1.4.0.

### Security

- Cost pie/doughnut charts are rejected for negative categories, zero totals, fewer than two categories, or an incomplete cost whole.
- A generated workbook cannot be marked `VERIFIED` until post-export import and visual checks are completed; its SHA-256 must match the manifest.

## [1.3.0] - 2026-08-31

### Added

- Structured accrual P&L draft definition with fixed, non-executable report operations.
- Owner dashboard configuration with recommended multi-select O6 modules for profit, cost, data trust, close, cash, dimensions, trends, budgets, reserves, scenarios, and custom needs.
- Management report, dashboard, dimensions, attribution, management-adjustment, and budget templates.
- Structured allocation-policy register and deterministic Traditional Chinese/English Markdown dashboard renderer.
- Management-report validator that recomputes results from the `POSTED` journal, verifies ledger checksums, P&L identities, cost reconciliation, allocation completeness, budget null semantics, negative gross margins, and chart lineage.
- Forward and tamper tests for valid profit, stale reports, hardcoded charts/Markdown, cash-basis misuse, unsupported modules, false professional-review claims, invalid data statuses, and missing-budget misuse.

### Changed

- Expanded the chart of accounts with P&L, cost-function, nature, traceability, behavior, responsibility, allocation, and dimension fields.
- Expanded the journal with explicit functional-currency debit/credit, FX lineage, and management dimensions.
- Added separate, clearly labeled cash, trust, action-item, and management-adjustment views while preserving one formal ledger.
- Renamed the accounting output as a structured accrual P&L draft so owner approval cannot be confused with professional assurance.
- Updated Traditional Chinese and English usage guidance for the owner reporting workflow.

### Security

- Prevented management dashboards from becoming a second ledger or embedding unverified numeric chart datasets.
- Required owner confirmation of reporting choices, source checksums, ledger-recomputed cash, qualified written review evidence, and preserved professional-review boundaries.
- Bound professional-review scope to report identity, revision, period, and ledger checksum; required actual local conclusion bytes, SHA-256, coherent dates, and a company-profile checksum.
- Required owner dashboards to separate ledger accrual, management adjustments, and management-basis amounts; partial reviews cannot set a global professionally reviewed status.

## [1.2.0] - 2026-08-31

### Added

- Mandatory first-use F0 feature selection before accounting interviews, research, sensitive-data access, or file creation.
- Owner-friendly O1–O8 outcome menu with AI preselection, multi-select confirmation, and custom `CUST-` features.
- Versioned `feature-selection.json` in each private Company Accounting Pack.
- Company Pack state and manifest schema 1.2, with an explicit upgrade path from Skill 1.1 packs.
- Structural validation for recommendation/confirmation separation, custom-feature completeness, selection revisions, and manifest/state consistency.

### Changed

- Made Traditional Chinese the default repository README.
- Moved the complete English documentation to `README.en.md` and added language switching links to both versions.
- Updated GitHub Actions to current Node 24-compatible major versions.
- Clarified that fixed safety controls cannot be disabled as optional features.
- Strengthened posting/close validation for current official sources, evidence links, deduplication, approval, unresolved professional review, reconciliation, and close blockers.

## [1.1.0] - 2026-08-31

### Added

- Progressive company-owner interview and industry accounting map.
- Jurisdiction-aware official-source research workflow.
- Separate Company Accounting Pack templates.
- G0–G4 authorization, understanding, conflict, policy, and posting gates.
- Status model for facts, AI proposals, official sources, and professional decisions.
- Company Accounting Pack initialization and staged validation scripts.
- Taiwan jurisdiction navigation with mandatory current-source rechecking.
- Open-source project documentation, attribution, security, and CI validation.

### Security

- Initialization rejects blank persistence authorization.
- Existing invalid authorization metadata requires an explicit repair flag.
- Empty scaffolds cannot pass posting readiness validation.
