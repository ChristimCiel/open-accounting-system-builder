# Security Policy

## Supported version

Security fixes are applied to the latest release on the `main` branch.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository when available. Do not open a public issue containing credentials, financial records, personal data, company identifiers, bank details, account numbers, card numbers, customer information, employee information, or exploitable security details.

Include:

- the affected version and file;
- a minimal reproduction using synthetic data;
- the expected and observed behavior;
- potential impact; and
- a suggested mitigation, if known.

## Data exposure

This repository must never contain a real Company Accounting Pack or real accounting evidence. If sensitive data is accidentally committed:

1. Stop sharing or cloning the affected revision.
2. Revoke or rotate any exposed credential immediately.
3. Treat the Git history, forks, caches, and existing clones as potentially exposed.
4. Follow GitHub's sensitive-data removal process.

Deleting a file in a later commit does not remove it from Git history.

## Trust boundary

Installers and users should inspect `SKILL.md` and executable scripts before installation. The Skill requires explicit persistence authorization and uses staged validation, but these controls do not replace operating-system permissions, access controls, backups, professional review, or human approval.
