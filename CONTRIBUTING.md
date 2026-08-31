# Contributing

Thank you for helping improve Open Accounting System Builder.

## Ground rules

- Use only synthetic or fully de-identified examples.
- Never submit real company ledgers, evidence, identifiers, account details, customer data, employee data, credentials, or private professional advice.
- Preserve the distinction between internal workflow proposals and professional accounting, tax, legal, audit, or filing conclusions.
- Do not hard-code time-sensitive laws, rates, thresholds, deadlines, or standards without a current official source, checked date, applicability conditions, and recheck trigger.
- Keep the shared Skill separate from company-specific Company Accounting Packs.
- Do not weaken authorization, posting, reconciliation, or version gates without an explained safety rationale and tests.

## Proposing a change

1. Open an issue describing the user problem and jurisdiction, if relevant.
2. Create a focused branch.
3. Make the smallest change that solves the demonstrated problem.
4. Update references and templates only when the workflow needs them.
5. Add or update a realistic acceptance scenario.
6. Run repository validation.
7. Open a pull request explaining behavior, risks, evidence, and compatibility.

## Validation

```bash
python3 scripts/validate_repository.py
```

Changes to initialization or validation scripts should also demonstrate:

- blank authorization is rejected before file creation;
- invalid existing authorization is not silently preserved or replaced;
- onboarding scaffolds state that they are not ready for posting;
- posting validation fails when required gates or master-data fields are missing; and
- balanced and unbalanced journal fixtures behave as expected.

## License of contributions

Unless explicitly stated otherwise, contributions submitted for inclusion are licensed under Apache-2.0, as described in the repository license.
