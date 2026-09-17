# Proxy management capability integration matrix

Date: 2026-09-17  
Status: confirmed by source comparison and focused tests  
Sources: `codex/proxy-management@0ad2fd2a`, `codex/proxy-live@17e08705`, `codex/proxy-remote-controls@dc49d882`

| Capability | Decision | Evidence and reason | Verification |
| --- | --- | --- | --- |
| ProxyPanel connection lifecycle and credential handoff | already-current | Every production file introduced by `codex/proxy-management` exists in the current tree. Credential storage remains host-only and renderer access still crosses the typed IPC boundary. | backend contract/runtime tests and desktop IPC test |
| Transactional synchronization and local groups | already-current | The current application and database layers retain the source facade, sync, projection, connection, group, and concurrency behavior. Thirty audited source files are byte-identical; changed files contain later migrations and contracts. | proxy integration and concurrency tests |
| Health probing, usage, IP allowlist, and credential views | already-current | Current HTTP routes and provider adapters expose the original management endpoints with the same redaction boundary. | proxy API, probe, transport, and domain tests |
| Proxy management desktop page | current-newer | The page, hooks, connection/detail/fleet/group components, preview entry point, and API client remain present. Current versions also use the shared table system and later remote controls. | proxy renderer tests, typecheck, and table verifier |
| Remote country/city options and rotation controls | already-current | `codex/proxy-live` and `codex/proxy-remote-controls` are already ancestors of the integration branch. Their persisted options, operation state, remote mapping, schedule controls, and tests are present. | remote-control contract, provider, and renderer tests |
| Historical migration numbering | current-reconciled | Migrations `0002_proxy_management`, `0003_merge_proxy_models`, and `0004_proxy_remote_controls` remain in the active Alembic chain. Later migrations extend that chain without replacing proxy tables. | migration-head checks in release verification |
| Live ProxyPanel account calls | exclude from deterministic verification | Live calls depend on user credentials and an external service. The checked-in redacted fixtures and transport/contract tests cover the integration without reading or changing a live account. | 90 deterministic backend proxy tests |

Focused verification completed with 90 backend tests and 32 desktop tests passing. The historical `codex/proxy-management` branch is reconciled with a tree-preserving merge after this evidence is committed; the two later proxy branches need no reconciliation merge because they are already ancestors.
