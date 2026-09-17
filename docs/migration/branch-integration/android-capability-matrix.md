# Android capability integration matrix

Date: 2026-09-17
Status: confirmed by source-tree audit against `codex/android-workflow-handoff@f573a44d`
Target: `codex/integrate-valid-branches-20260917`

| Source capability/path | Decision | Current integration rule | Verification |
| --- | --- | --- | --- |
| `adapters/http/android.py`, `application/android/{devices,management}.py`, `domain/android/`, `providers/android/{management,mac_runtime}.py` | port | Import Android instance discovery, lifecycle, controls, and native runtime behind Android-owned interfaces. | `pytest -q -k android` |
| `android_fleet.py`, `android_fleet_schemas.py`, `application/android/{fleet,console}.py`, `database/android_resources.py` | port | Import persistent fleet and console queues; retain the current database session factory and app lifecycle. | Android contract/unit tests |
| `filesystem/android_paths.py`, `providers/android/stream.py` | port | Keep Android filesystem/runtime path handling isolated from project and Studio paths. | Android runtime and renderer tests |
| `infrastructure/database/android.py` and migrations `0007`–`0010` | already-current | The target already contains the Android migrations plus `0011_merge_android_project_data`; do not replace migration history. Import the repository model only. | migration-head and Android migration tests |
| `desktop/domains/android/` including reference assets | port | Import the Android management UI as an isolated domain and mount it through current guarded navigation. | Android renderer tests and typecheck |
| `bootstrap/android.py`, `bootstrap/android_prepare.py` | replace-with-current-contract | Reuse Android composition helpers, but register them inside current `create_app`, preserving projects, PM4 runtime, proxy runtime, current Studio runtime, quiesce middleware, and shutdown behavior. | app contract tests, OpenAPI check, sidecar shutdown test |
| Idle-device manual console and embedded/native switching | port | Manual sessions claim idle devices through the durable device repository and preserve generation fencing, input sequencing, cleanup, and recovery. | Android handoff unit tests and renderer tests |
| Source M5 workflow takeover, Android workflow worker, and allocation execution | exclude-retired-studio | The source implementation requires the retired M5 document, run repository, scheduler, and worker protocol. The current boundary rejects takeover/allocation with typed errors until a current Studio Android executor exists; it does not report false compatibility. | boundary rejection test plus current workflow tests |
| `App.tsx`, `ApplicationHeader.tsx` | replace-with-current-contract | Add one `android` route/tab to current navigation; preserve project routes, leave guards, workspace reset behavior, and current header styling. | renderer navigation/Android tests |
| Android smoke/compare scripts | port | Import scripts; invoke only `--help` during integration, without starting an emulator or touching user devices. | `python ... --help` |
| historical Android QA images and old Studio screenshots | exclude-retired-studio | They are historical evidence, not executable capability, and include screenshots of the superseded Studio. | source audit only |
| branch changes to old Studio editor/run panels and old workflow worker | exclude-retired-studio | Current Studio runtime, worker protocol, recovery, cancellation, artifacts, and generated API remain authoritative. | full workflow and backend suites |

The source branch is reconciled only after these rows are implemented and verified. A tree-preserving `ours` merge records ancestry without reintroducing excluded files.
