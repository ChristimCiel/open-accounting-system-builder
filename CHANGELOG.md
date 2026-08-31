# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use semantic versioning.

## [Unreleased]

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
