# Studio nested configuration shape repair

- Date: 2026-09-28
- Status: confirmed implementation; packaged native acceptance pending
- Scope: PM9 remediation Task 6 / UI-03
- Sources: production `WorkflowRuntime` extraction in `apps/backend/src/autoflow/application/workflows/runtime.py`; packaged evidence in `docs/qa/2026-09-28-remediation/native-session-VwvJnD/`; focused red/green logs in `docs/qa/2026-09-28-remediation/studio-config/`

## Confirmed finding

The API accepts both flat node data and nested `node.data.config`. Production Runtime treats a valid nested config mapping as the complete configuration object and otherwise uses flat data. Studio previously read and wrote only flat data, so nested documents displayed defaults and edits could be shadowed by the unchanged nested object at execution time.

## Implemented boundary

`getNodeConfigData` exposes the same whole-object priority as Runtime and overlays only outer `moduleType` and `label` for editor identity. It does not merge missing nested configuration keys from outer data. `patchNodeConfigData` and the store's config-specific update actions preserve an existing nested namespace and preserve flat documents as flat.

The configuration panel and shared configuration consumers use that boundary. Outer editor metadata such as node remark `name`, disabled/highlight state, dimensions, and node identity stays outer. Raw import, merge, export, save/load, revision, and operation behavior is unchanged. No database migration and no backend production change were introduced.

## Verification

- Red: 1 file failed, 2 failed / 2 passed, proving nested End display and nested numeric preflight were broken.
- Green: 17 files passed, 230 tests passed.
- Static: desktop typecheck and workflow lint passed; `git diff --check` passed.
- Independent production boundary: 2 backend Runtime/snapshot tests passed in 0.41s.

The package build and native edit/save/reopen/restart/real Project End run remain assigned to the root remediation task.
