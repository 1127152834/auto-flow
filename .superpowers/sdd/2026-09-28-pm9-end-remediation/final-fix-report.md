# Final review consistency fix report

Date: 2026-09-28. Status: DONE for the bounded implementation seat. Confidence: high.

## Result

Both Important findings from the final review at `e49144f2` are fixed in one minimal frontend wave.

1. `ProjectEndConfig` no longer renders a legal non-empty static `recordTargets` array as empty. It displays the exact array as read-only JSON and exposes an explicit clear button that writes an empty array. Unrelated configuration edits preserve the original array and nested storage shape. Dynamic string values continue to use the existing variable-reference input; no JSON string is written back as a target value.
2. `SubflowConfig` now uses the existing `getNodeConfigData` boundary for group eligibility, option display names, and the selected name. A nested-only group is listed, a stale outer `isSubflow: true` cannot override nested `false`, and selection writes the effective nested name through the existing shape-preserving ConfigPanel/store path. Outer labels and stale outer compatibility fields remain unchanged.

No backend, public contract, migration, executor, dependency, document normalization, or new abstraction was added.

## Red/green evidence

Raw subprocess stdout/stderr and the exact command index are in `docs/qa/2026-09-28-remediation/final-review-fix/`.

- Red on reviewed production code plus the new tests: 3 test files failed, exactly 3 new regressions failed, and 66 existing tests passed.
- Immediate green: 3 files and 69 tests passed.
- Related whole files: ProjectEndConfig, node-config-shape, common advanced config, conditional/Subflow branches, and complex structure interactions; 5 files and 133 tests passed.
- Desktop `npm run lint`: exit 0.
- Desktop `npm run typecheck`: exit 0.

The known Node `ExperimentalWarning` for localStorage remains visible in raw Vitest output. It was already deferred by the final review and did not affect pass/fail.

## Scope and limits

Only the two reviewed frontend behaviors, their regressions, direct evidence, this report, and the focused `.ai` session are part of this commit. Existing root QA/docs and unrelated dirty-worktree files were not modified or staged by this implementation seat.

Per the final fix brief, this seat did not run a full frontend suite, build/package, native application, SQLite save/reopen/restart flow, or production End. Root owns those final reruns and native acceptance. AOCI initialization/maintenance and configuration were not touched.
