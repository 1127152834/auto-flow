# I1–I5 final review remediation

- Date: 2026-09-24. Status: **DONE_WITH_CONCERNS**. Confidence: high for the covered software paths.
- Base: `9f9e3ff9` (product base `ef0af03f` plus root-owned QA).
- Commit: `78bf8c92` — `fix(android): fence verification and expose safe maintenance recovery`.
- Scope: 12 owned backend/frontend source and test files; no dependency, migration, public DTO or generated OpenAPI change. Studio dirty files, QA, `.ai` and plans were not staged. Root owns evidence archival and final whole-repository gates.
- Skills followed: systematic-debugging, test-driven-development, writing-good-tests reference, verification-before-completion. Single implementer; no delegated agents.

All log paths below are relative to this scratch directory. Backend commands using `uv run --project apps/backend` and npm commands run at the worktree root unless stated otherwise. RED logs are retained, including intermediate integration failures; no test-only flags were added to production.

## I1 — fence lifecycle verification projections

**Root cause:** `verify_lifecycle_operation` observed a detached device, yielded during runtime inspection, then committed that obsolete whole-device projection. `transition_with_device` only fenced backup restore targets, so another recover and manual claim could be overwritten.

**RED:**

```sh
uv run --project apps/backend pytest apps/backend/tests/integration/test_android_management_operations.py -k old_verification -q
```

`i1-red.log`: 1 failed. Actual SQLite + AndroidManagement recover + claim interleaving used `asyncio.Event`, not sleeps. The assertion found generation 2 instead of 4, idle instead of manual, and owner None instead of new-session.

**Change:** capture the pre-inspection snapshot; after runtime observation acquire the existing runtime lock, re-read and check the exact current operation ID, ownership/control and app/restore isolation. Submit the original expected device to the repository, which rechecks it inside the same SQLite write transaction as the operation transition. A conflict leaves both device and operation untouched. Explicit permanent deletion of an interrupted restore remains verifiable after owned runtime deletion is observed; the restore marker is preserved.

Additional boundary RED/GREEN:

- `i1-isolation-red.log`: `pytest .../test_android_management_operations.py -k pending_isolation -q` produced 2 failed / 3 passed for missing current-operation identity and persisted restore intent without a restored state. Reused `restore_pending` and required the actual operation identity.
- `i1-disposal-red.log`: `pytest .../test_android_management_operations.py -k permanent_disposal -q` produced 1 failed, demonstrating that a blanket restore guard would block safe disposal. The guard now permits only confirmed permanent delete, never start/backup release.

**GREEN:**

```sh
uv run --project apps/backend pytest apps/backend/tests/integration/test_android_management_operations.py apps/backend/tests/contract/test_android_management_operations.py -q
uv run --project apps/backend pytest apps/backend/tests/integration/test_android_management_operations.py apps/backend/tests/integration/test_android_multi_device.py -q
```

`i1-green.log`: initial 39 passed. `i1-isolation-green.log`: 44 passed after isolation coverage. `i1-final-green.log`: 23 passed including the final safe-disposal and real-database bulk verification paths. Current lifecycle success and owned post-delete success remain covered. Existing contract fixtures now reference the real durable operation ID instead of unrelated placeholder IDs.

## I2 — serialize image metadata verification with lifecycle writes

**Root cause:** metadata verification fetched before awaiting the probe and saved the full row without the runtime write lock or lifecycle admission. This reactivated tombstones and overwrote delete state, revision and request receipt.

**RED:**

```sh
uv run --project apps/backend pytest apps/backend/tests/integration/test_android_images_templates.py -k 'metadata_verification or metadata_probe' -q
```

`i2-red.log`: 11 failed. Real SQL resource rows cover unregistered/deleted/delete_pending/delete_blocked/delete_needs_verification with supported and unsupported checks, plus an Event-controlled probe/delete interleaving. Deleted registration became verified and lost deletion facts before the fix.

**Change:** use the existing shared image runtime lock through re-read, state admission, probe and publication. Only registered/verified rows can accept metadata verification. Tombstones and uncertain deletion rows return `ANDROID_IMAGE_STATE_CONFLICT`; restoration of registration still requires explicit register. A concurrent deletion is rejected by the existing lock and can subsequently complete without losing its receipt.

**GREEN:**

```sh
uv run --project apps/backend pytest apps/backend/tests/integration/test_android_images_templates.py apps/backend/tests/unit/test_android_images.py apps/backend/tests/contract/test_android_images.py -q
```

`i2-green.log`: 44 passed. Metadata cannot revive any blocked state; the interleaving ends with unregistered, revision 2, original deleteRequestId intact.

## I3 — keep embedded lease heartbeat active while display reads pause

**Root cause:** the heartbeat used TanStack's default foreground-only interval. Hidden/focus-lost pages stopped the 5-second heartbeat although the server's embedded lease expires after 30 seconds.

**RED:**

```sh
npm test -- --run src/renderer/domains/android/tests/AndroidPage.test.tsx -t 'hidden lease'
```

`i3-red.log`: 1 failed / 37 passed. Root npm forwarding dropped the test filter (with an npm warning), so the full file actually ran. The real AndroidPage and QueryClient under a fake clock emitted **0** extra heartbeats over 35 seconds with focusManager hidden. Network IO and the video canvas are test doubles, not Electron.

**Change:** set `refetchIntervalInBackground: true` only on the heartbeat query. Display queries retain their existing foreground-only intervals and transition/session fencing remains unchanged.

**GREEN:**

```sh
npm --workspace @autoflow/desktop test -- src/renderer/domains/android/tests/AndroidPage.test.tsx -t 'hidden lease'
```

`i3-green.log`: 1 passed. At least six heartbeats over 35 seconds, zero additional app/device-display polls, and input resumes through the same session with no second claim.

**Evidence boundary:** this proves React/TanStack lease behavior only. Electron `backgroundThrottling` remains at its existing default true; no global throttling change was made. Long-hidden/minimized renderer scheduling on actual macOS remains unmeasured while the desktop is locked. This is not a claim that fake-clock coverage proves real Electron long-duration timing.

## I4 — make stopped backups and orphan-backup restore reachable

**Root cause:** the only page path to BackupPanel required ready-device console opening; per-device filtering also hid backups once the source disappeared.

**RED:**

```sh
npm --workspace @autoflow/desktop test -- src/renderer/domains/android/tests/AndroidPage.test.tsx -t 'stopped backup|source device has been deleted'
```

`i4-red.log`: 2 failed, because neither the stopped maintenance entry nor source-independent restore action existed.

**Change:** add a device data-maintenance entry that selects a device without start/session/claim; reuse BackupPanel on that view. The same component with no device filter presents the workspace backup catalogue on the home page. Creation remains device scoped and requires stopped/retained, fresh idle state, no owner/session and no pending restore. The global catalogue can restore an orphan backup without a live source. The existing explicit disk-estimate consent remains false by default and is not inherited from the deleted source.

**GREEN:**

```sh
npm --workspace @autoflow/desktop test -- src/renderer/domains/android/tests/AndroidPage.test.tsx src/renderer/domains/android/tests/ManagementTools.test.tsx src/renderer/domains/android/tests/ManagementOverview.test.tsx
```

`i4-green.log`: 108 passed. Page-level tests create a stopped backup at the current revision with no start/claim, and restore a workspace backup while the device directory is empty. Existing BackupPanel consent, original-request and disk-admission checks remain passing.

## I5 — distinguish current-device recover from historical receipt verification

**Root cause:** the card's current-device “核实状态” action called historical `/operations/{id}/verify`, which correctly returns failed historical operations unchanged and cannot recover an unknown device with no old operation ID.

**RED:**

```sh
npm --workspace @autoflow/desktop test -- src/renderer/domains/android/tests/AndroidPage.test.tsx -t 'recovers current device'
```

`i5-red.log`: 3 failed for failed lifecycle, unknown without operation, and pending-restore device paths.

**Change:** card current-state verification dispatches the existing device `recover` command. OperationHistory continues to call the original operation's verify endpoint with the original request ID. Backend recover, pending app/restore isolation, deletion rules and historical terminal records remain unchanged.

**GREEN:**

```sh
npm --workspace @autoflow/desktop test -- src/renderer/domains/android/tests/AndroidPage.test.tsx src/renderer/domains/android/tests/ManagementOverview.test.tsx
```

`i5-green.log`: 64 passed. Failed/unknown paths become eligible for start/delete after recover; interrupted restore still has no start, disables backup and retains safe deletion. The pre-existing historical receipt verification test still passes. `i5-green-initial.log` preserves the intermediate one-test failure caused by an old unit assertion explicitly expecting the incorrect card `verify` callback; its expectation was corrected to recover after the page regression proved the intended endpoint.

## Final verification

| Command | Actual result | Evidence |
|---|---|---|
| `uv run --project apps/backend pytest apps/backend/tests/unit/test_android*.py apps/backend/tests/integration/test_android*.py apps/backend/tests/contract/test_android*.py -q` | **534 passed, 2 warnings**, 37.86s | `android-backend.log` |
| `npm --workspace @autoflow/desktop test -- src/renderer/domains/android` | **14 files / 199 passed**, 7.76s | `android-frontend.log` |
| `npm run typecheck` | passed | `typecheck.log` |
| ESLint on the five changed frontend source/test files | passed | `eslint.log` |
| Ruff on the seven changed backend source/test files | All checks passed | `ruff-final.log` |
| `npm run openapi:check` | passed, no generated changes | `openapi.log` |
| `git diff --check -- <owned files>` | passed before commit | commit tool output |
| Extra `uv run --project apps/backend mypy` on three changed backend source files | **6 existing diagnostics**, not a clean mypy run | `mypy.log`, baseline evidence below |

The first Android backend run (`android-backend-initial.log`) had 531 passed / 2 failed. Both failures were old bulk verification integration fixtures using in-memory device dictionaries with a real SQL operation repository but **no persisted device row**. The new transaction correctly refused that inconsistent setup. Those two cases now use the real SQL device repository for verification and assert the persisted projection; no production fence was relaxed to satisfy the fixtures. Final Android full-scope rerun passed.

Mypy diagnostics occur on unchanged lines: `images.py:248` nullable catalog inspect and `:276` method-name/type ambiguity; `android_operations.py:164,166,188,190` mixed datetime/string update dictionaries. A scratch export of pre-fix HEAD reproduces the same six diagnostics (`mypy-baseline.log`); that initial isolated-file run additionally emits five import-resolution diagnostics, which are a scratch-layout artifact, not extra product defects. The completed package-layout baseline comparison in `mypy-baseline-package.log` reproduces **exactly the same 6 errors in 2 files**, without the isolated-file import artifacts. It exports the three pre-fix files from `9f9e3ff9` into a temporary copy of the package and runs the same three-file mypy command with that package on MYPYPATH. No unrelated type cleanup was bundled.

Warnings: Starlette's deprecated AnyIO BlockingPortal alias; intentional duplicate AndroidManifest ZIP-entry fixture; Node **26.7.0** localStorage experimental warnings. No Node 22 execution is claimed. Whole-repository backend/frontend, engineering build gates and the real Mac source-delete/backup-restore chain are being run once by root against the frozen candidate; this subtask does not claim their results before completion.

## Remaining evidence and handoff

- Software findings I1–I5 have executable failing-before/passing-after regression evidence and are included in commit `78bf8c92`.
- Actual Electron hidden/minimized long-duration heartbeat, new maintenance UI visual use, GApps/account/network cases and ten-instance scale remain governed by root's real-condition acceptance matrix; no fabricated real-device pass.
- Root should archive these scratch logs/report, reconcile its final full gates and real QA, and perform the final bounded review. Product and test files are frozen after the commit.
