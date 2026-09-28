# PM9 End final UI consistency fix

Date: 2026-09-28. Status: confirmed.

Source: final review of base `e49144f2458a5024ef2ef06d5f8bba75f67c0557`, `.superpowers/sdd/2026-09-28-pm9-end-remediation/final-review-findings.md`, and direct red/green verification in `docs/qa/2026-09-28-remediation/final-review-fix/`.

- Project End now exposes a valid non-empty static `recordTargets` array as a read-only JSON view and provides an explicit clear action that writes `[]`. Unrelated edits preserve the array and nested document shape; it is never converted into the string-only variable-reference contract.
- Subflow configuration now uses `getNodeConfigData` for definition filtering, option names, and the name written after selection. Nested config remains authoritative as one whole object; outer label identity and existing flat/nested storage shapes remain intact.
- New regressions exercise `ProjectEndConfig`, real `ConfigPanel`/store updates, and the actual Subflow select interaction, including nested-only definitions and stale outer conflicts.
- Verification: expected red was 3 failed / 66 passed; fixed related set was 5 files / 133 tests passed; desktop lint and typecheck passed.
- Build, package, native application startup, SQLite replay, production End, full frontend suite, and AOCI maintenance were intentionally left to the root-owned final pass.
