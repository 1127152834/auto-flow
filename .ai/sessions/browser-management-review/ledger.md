# SDD ledger — plan: docs/superpowers/plans/2026-09-12-browser-management.md

## Preparation

BASE at execution start: `1b18a587a11afabac5f44cd5806278cfe9612a05`.

| Tasks / shared artifact | Producer → consumer | Finding and ruling |
|---|---|---|
| 1 → 8/9/10 | shared UI primitives → domain components | Existing uncommitted UI draft is not a stable API. Task 1 must preserve only tested primitives and task 11 removes replaced draft after integration. |
| 2 → 3/6 | DB/session/models → profile/kernel adapters | Existing backend has no business storage. Task 2 owns migration and AppPaths; later tasks consume ports, not ORM. |
| 4 → 5/6 | CloakBrowser provider → worker/API | Wrapper is platform-specific and global-cache based. Task 5 isolates one worker and staging directory; task 4 must not expose wrapper types. |
| 3 → 8/9/11 | Profile HTTP contract → generated client/forms/page | Generate OpenAPI only after route work; frontend must not hand-write wire DTOs. |
| 5 → 7/10 | operation/SSE → hooks/components | SSE must send initial snapshot and token-authenticated fetch; cancellation is a real terminal transition. |
| 6 → 10 | kernel HTTP/preload → embedded manager dialog | No independent kernel route; reveal accepts a validated KernelRef, never an arbitrary path. |
| 11 → 12 | live page → smoke/package | Packaging only after real API/page integration; no mock-only completion claim. |

| Task | Self-consistency scan |
|---|---|
| 1 | Tests cover focus, busy dialogs, toast and field errors produced by the listed files. |
| 2 | Tests cover validation and empty database migration; repository owns schema. |
| 3 | Fake installed-kernel lookup supplies the dependency until task 6; endpoints and safe deletion align. |
| 4 | Provider test values match `windows-x64`/`darwin-arm64`/`darwin-x64` and locked wrapper. |
| 5 | Test worker is isolated from production and exercises cancel/cleanup/SSE state. |
| 6 | API and IPC signatures align with task 5 operations and task 10 dialog. |
| 7 | Generated types and query/event cache depend on task 3/6 routes; no manual DTO duplication. |
| 8 | UI values convert to ProfileWrite; component owns only form semantics. |
| 9 | Dialog tests use the task 1 primitives and task 7 hooks. |
| 10 | Kernel dialog consumes task 6 API and returns focus/draft to task 9 form. |
| 11 | Page integrates tasks 7–10 and removes the old draft only after tests. |
| 12 | Smoke commands exercise the exact final paths and platform packaging. |

Rulings:
- Ruling: execute in the existing user checkout and protect uncommitted unrelated work — the user authorized implementation in `/Users/zhangtiancheng/Documents/projects/autoflow`, while concurrent scaffold/UI work is present; the cost of resetting it is destructive loss, so tasks touch only their ownership paths and the coordinator stages selectively.
- Ruling: treat the generated prototype as visual reference only where it conflicts with verified old behavior — generated image contains decorative/incorrect values and a form section rail; the old source and approved interaction document are authoritative, so implementation uses the latter.

Task 1: fix round 1/5 (busy guard, nested focus, toast motion; ProxyPanel finding ruled concurrent/out-of-scope; commits c2d9d7d..d69ddfb)
Task 1: fix round 2/5 (nested focus/Escape and toast exit; commits d69ddfb..03ec55a)
Task 1: complete (commits c2d9d7d..03ec55a, review clean; ProxyPanel finding was concurrent BASE-range content and ruled out)

Task 2: complete (commits 1278291..f1c9e05, final rereview PASS; backend 46 passed, ruff/mypy/diff clean)

Ruling: Task 3 may extend profiles domain ports and database repository lifecycle methods omitted by Task 2; service must not directly access ORM.
Ruling: Reuse proxy-management shared CredentialStore commit 4c3ab92 during Task 4 after review; kernel work must not create a second platform credential store.

Task 3: complete (commits fdda052..a807583, review PASS; backend 73 passed, ruff/mypy/diff clean)
Ruling: Profile deletion usage safety covers AutoFlow OS lock protocol and known Chromium markers; arbitrary noncooperating external file readers cannot be detected portably and are not claimed to be detected.

Task 4: complete (commits a0e3fb2..7296105, review PASS; backend 111 passed, ruff/mypy/strict scope/lock clean)
Ruling: Shared credentials a4b881f, dependencies 1887527, SQLite FK 2b38549 and PyInstaller Alembic resources cadc83c were serially integrated by coordinator; reviewer scopes exclude these unrelated-to-task4 provider changes.

Ruling: Proxy-management user requested early integration coordination via thread 01a09147-21a9-7f22-b78d-dbb091353ebb. Stable handoff is codex/proxy-management@0ad2fd2 in ../autoflow-proxy-management; schedule shared-boundary integration after Task 5 review and before Task 6, preserving in-flight bootstrap and existing Vite dirty content. Read docs/migration/proxy-management-status.md before integrating; do not overwrite App/bootstrap/generated/lock. Full business/UI integration remains coordinated with that authorized task.

Task 5: complete (commits 183b40d..ecfa3b2, final rereview PASS; backend 153 passed, ruff/mypy clean)
Ruling: Task 5 may extract the existing profile OS lock into minimal ExclusiveFileLock shared with kernel ownership; profile guard behavior and tests preserved.

Proxy integration checkpoint: complete (c860922, independent review PASS; backend207/desktop47/script7, type/lint/build/OpenAPI/migration/frozen+Electron smoke passed locally).
Ruling: Task6 may add supervised catalog/license worker RPC bridge and minimally adapt LicenseProvider async interfaces; Task5 delivered worker protocol but parent only exposed download supervision. All wrapper calls remain isolated.

Fix-round audit: Task2 used 2/5 rounds (e3ac989, f1c9e05); Task3 used 1/5 (a807583); Task4 used 1/5 (7296105); Task5 used 2/5 (a2921d2, ecfa3b2). All closed with independent PASS.
Task 6: fix round 1/5 started — License download/logout race; incomplete trash restoration; concurrent default-row initialization. No UI/client task started before API review closure.

Task 6: fix round 2/5 — map download license-gate contention to KERNEL_BUSY; logout contention remains LICENSE_IN_USE.
Ruling: A download overlapping an unfinished logout may be rejected immediately; only downloads after a completed logout must observe missing credentials. The plan does not require waiting for concurrent logout. Reviewer accepted this and retained only the download busy-code finding.

Task 6: complete (589b8bd..b45ca84, final review PASS; backend231/desktop55/scripts7, type/lint/build/OpenAPI clean).
Frontend dependencies: f8d55f8 added TanStack Query/RHF/Zod/resolvers serially; typecheck passed, preserve Proxy ApiClient compatibility in Task7.

Task7 dependency repair: register independent BrowserApiError/BrowserErrorEnvelope for existing camelCase browser wire; keep Proxy snake_case ApiError intact, regenerate and normalize client access.
Model integration coordination: user explicitly authorized codex/model-management merge via peer 01a09186-46a2-71b0-b225-09b547a33c9b. Peer owns independent ../autoflow-merge-models candidate9009285 (parents b45ca84+fe3672a); main checkout update waits Task7 commit and independent PASS, then explicit window. Do not cherry-pick their candidate. Preserve SIDECAR_UNAUTHORIZED/epoch recovery and model entry ModelManagementPage({api:ModelApi,instanceId}); Task11 unifies session QueryClient with Task7 ApiProvider rather than nesting duplicate query providers.

Ruling: User explicitly requested parallel sub-agent development, and the approved plan specifies Tasks9/10 may run in parallel with integration owned by coordinator. After Task8, dispatch these two implementations concurrently in nonoverlapping profiles/kernels component paths, overriding the skill's generic serial-implementer guideline (its stated reason is file conflicts). Freeze shared types/props first and keep integration edits with coordinator; review each independently. Tasks8/10 do not overlap because Task10 waits for Task8 dependency.

Task 7: complete (06153ca..4a91407, independent rereview PASS; desktop76/type/lint/build/OpenAPI; backend contracts21). One fix round for proxy remote timeout compatibility.
Model peer window OPEN after Task7 PASS: peer 01a09186-46a2-71b0-b225-09b547a33c9b will fast-forward its validated candidate2ae2648 and preserve dirty file contents; no local shared writes until completion notice.

Model integration checkpoint: peer completed fast-forward to f095d49; original20 dirty/untracked file bytes preserved by SHA256, Vite content identical and now committed as part of validated model Tailwind config. Peer evidence backend304/frontend128/scripts7/OpenAPI/type/lint/build/dev+packaged Electron pass. Main dependencies synced; own npm metadata-only lock churn discarded after inspection. Shared window CLOSED/released; begin Task8 in profiles-only paths.

Settings/dashboard peer 01a0920a-732d-7661-a057-7f7ab7ecca8f is user-authorized direct-baseline implementation. It owns shared App/main/preload/ApiProvider/types/bootstrap/generated until stable checkpoint; browser Tasks8/9/10 remain domain-component-only. Task11 will only wire BrowserManagementPage into its browser slot and verify drafts/recovery, not replace the shared shell. External settings lint eventNames finding reported to its owner, never attributed to Task8.

Task 8: complete (fe9a182..5d6e4cf, independent PASS; profiles53/type/targetlint/build). One fix round preserved viewport null and matched URL authority syntax. Frozen field props use manage click event; dialog layer adapts selectedKernel/trigger.
Tasks 9/10: concurrent implementation window opened under user-requested parallelism, nonoverlapping profiles vs kernels component paths, shared integrations reserved for coordinator/Task11. Settings peer retains shared shell ownership.

Settings/dashboard checkpoint: a829fea released shared ownership. App ApiProvider browser slot is placeholder, client prop preserves authenticated request handling; session.workspaceKey remount only on actual workspace switch; same-workspace reconnection keeps tree mounted. Task11 minimal integration now unblocked after Tasks9/10 reviews.

Task12 exploratory packaging evidence (before UI integration): backend PyInstaller build passed macOS26.4.1 arm64/Python3.11.13. Frozen sidecar fetched real catalog (wrapper0.5.9, no catalogError), downloaded and installed public145.0.7632.109.2 (147384149 archive bytes, installed367270152 bytes). Isolated evidence `/var/folders/8g/sq3srr71063c083rpkd32k380000gn/T/autoflow-real-kernel-9lctnbha/validation-evidence.json`; operation63e1732c-8b4e-4797-90e6-a9f1979c92dc completed, no License supplied. Final desktop integration/reveal/cancel/CI still pending. Local HTTP preflight uses trust_env=False to bypass environment proxy on loopback; initial502 was test-client routing, not backend failure.

Task12 additional real frozen evidence: requested public142.0.7444.175, observed one child worker while downloading, cancel API returned cancelled, worker PID no longer existed, operation staging removed, sidecar health remainedok. Evidence same isolateddir/cancellation-evidence.json.

Task12 red packaging proof: frozen sidecar with PYTHONTZPATH empty rejects a valid Asia/Shanghai profile timezone with422 VALIDATION_ERROR; artifact lacks tzdata. Same isolated data/evidence timezone-before-evidence.json. Requires explicit tzdata collection and frozen smoke with system zoneinfo disabled. No profile was created.

Task10 fix round1/5: preserve release channel identity; prevent stale HTTP queued response from overwriting SSE terminal cache; disable second download during active operation. Ruling: extend Task10 ownership minimally to kernels/hooks.ts and targeted hook tests for shared transport cache ordering — the UI consumes this already-reviewed Task7 producer but integration uncovered real ordering gap; existing public APIs remain unchanged. Include trivial .gitkeep removal with fix.

Task9 fix round1/5: backendviewportJson422 must remain visible/focusable in browser/preset/custom modes. Authorize minimal EnvironmentFields error presentation if necessary while preserving Task8 nullviewport semantics; no App/shared changes.

Ruling: start Task12 backend packaging/smoke preparation while Tasks9/10 fix domain components — validated backend APIs already stable and tzdata failure is independent of page integration; Task12 final desktop acceptance and completion still wait Task11. Task12 owns spec/scripts/CI/docs only, Tasks9/10 own disjoint domainUI; coordinator performs actual final UI checks.

Task9 complete (525d559..d829c6f; round1 independent ADDRESSED/PASS, focus/viewports2files15tests + profiles69/type/lint/build). Task10 round1 fix2216fa6 submitted, independent rereview pending.

Task10 fix round2/5: dualchannel/same-idterminal/activeguard/.gitkeep addressed; remaining list-order bug old snapshot omits newer POST operation id, clearsbusy. Backend retains complete operation history and no deletion; retain cached-only ids ordered after older incoming snapshot, preserving latestoperation display. Task12 independent checkpointc84037f passed source/frozenworker+CRUD with PYTHONTZPATH empty (tzdata fixed), scripts9/backendtarget21/ruff/mypy; finaldesktop dependsTask11.

Task10 complete (2b7e000..2a8dfd5; round2 independent PASS, kernels24/type/lint/build). Task11 unblocked: integrate peer stableApp slot and fullbrowserpage, offlineportal/reconnect and nestedoverlay assembly permitted as outlined in brief; Task12 continues scripts/packaging only.

Task11 complete (ba7096c..d1e4b9a; independent PASS, 7files49targeted/45files259frontend/type/lint/build). Actual Electron CUA validation and screenshots committed47ecb98; Task12 development desktop CRUD/1024+1280 geometry PASS reported, packaging/full checks in progress.

Task12 complete (c84037f+b5e2832; independent PASS, backend311/frontend259/scripts9/type/lint/OpenAPI/build/source+frozen sidecar/dev+packaged Electron). Windows/macIntel results remain unknown, correctly documented pending CI; this does not block local implementation delivery.
Task12 minor (deferred to final review): validation doc claims worker progress assertion, script only asserts completion; correct wording or add meaningful assertion. Existing upstream pytest/build warnings documented, not introduced here; defer dependency cleanup.
Final broad review in progress at b5e2832: Important candidates SSE graceful shutdown waits until SIGKILL; active download controls disappear after catalog failure. Wait complete list then one unified fix wave.

Final broad review complete: 2 Important (SSE shutdown/operation-only cancellation controls), 3 Minor (name conflict association/offline uncertain outcome/worker smoke wording). One unified final-fix implementation dispatched at dd86e72 to browser_final_fix (gpt-6-astra), with actual SSE process regression and catalog-loss UI regression required. Existing upstream warnings deferred to dependency maintenance.

Ruling: add a hidden host-token-authenticated cooperative shutdown endpoint and bounded server drain/host stop budget — Windows process termination cannot provide POSIX graceful SIGTERM semantics, and renderer SSE can remain connected during app quit; reuse existing private host protocol and retain hard-stop fallback. Cost if wrong: internal lifecycle interface and stop timing must be revised; renderer must never gain shutdown authority. Agent must validate actual cleanup budget and real SSE+active-worker process exit.

Final fix validation update: backend315/frontend265/scripts9 passed; source/frozen sidecar and development Electron application-quit pass, package:dir built. Windows HTTP response-loss now retains cooperative stop budget instead of immediate process termination. Observed bounded Uvicorn SSE drain logs ERROR/CancelledError despite code0/worker cleanup; record transparently for targeted rereview, no log filtering. Final packaged retest pending.

Final fix complete (dd86e72..3df5609): independent targeted PASS, I1/I2/M1/M2/M3 all ADDRESSED, no new Critical/Important. Reviewer real combined shutdown: two RPC workers plus one download worker, all ignoring TERM and actually started, SSE held open; code0 in7.382s, 3PIDs gone, RPC caches/staging removed, operation cancelled.
Final minor (deferred): bounded Uvicorn drain logs ERROR/CancelledError and in-flight cancelled RPCs may return500 during requested shutdown; normal exit and cleanup verified, not a running-state failure. Existing upstream warnings remain documented.
Finish: repository is normal checkout (.git == git-common-dir), codex/architecture-baseline retained at user-requested directory; no branch integration or remote publication required by this implementation request. All unrelated automation edits preserved. Root structure checks3passed; production final checks315backend/265frontend/9scripts plus type/lint/OpenAPI/build/source+packaged smoke in final-fix report.
