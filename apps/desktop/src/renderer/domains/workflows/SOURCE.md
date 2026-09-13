# WebRPA frontend provenance and boundaries

- Frozen source: `reference/WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb`.
- `source-manifest.json` records 275 retained source files, original paths and SHA-256 hashes. Hashes describe the original file, not the adapted target. License: `LICENSE.WebRPA`.
- The user authorized frontend-first migration with replaceable mock APIs on 2026-09-13. This supersedes the earlier sequencing requirement to finish a real backend before migrating the full frontend.

## Preserved implementation

The original WorkflowEditor, ModuleSidebar, ConfigPanel, Toolbar, graph/block views, grouping/note/subflow geometry, history and clipboard algorithms, specialized node forms, recording generation, Debug UI, logs/data/variables/assets and assistant components live inside AutoFlow's workflows domain. The retained action library has 284 entries after the user-requested desktop/mobile/SAP, office/file, media and bot categories are filtered; this is a frontend configuration count, not a count of implemented executors.

Original encrypted-file and clipboard identifiers remain unchanged for interchange compatibility. Original source API methods and event payload projections remain recognizable. Source `App`/entrypoint, port discovery, remote collaboration transport, publishing/version management and native desktop recorder are not copied as active application services.

## Adaptations

- A separate `studio.html` in the same Electron renderer build isolates the source styles. `styles/autoflow.css` maps the approved AutoFlow palette without redesigning the editor layout.
- `api/transport.ts` is the single injected IO seam. `api/config.ts` currently identifies the explicit mock origin. The real adapter must translate source contracts to generated AutoFlow OpenAPI types, authentication and errors. No page should add a separate fetch client.
- `events.ts` retains source consumers. `api/event-client.ts` replaces Socket.IO transport with HTTP commands and numbered SSE, using `shared/api/events.ts` for parsing. Reconnect replays after the last accepted sequence and never manufactures completion.
- New mock, adapter and integration files follow strict TypeScript and lint. Only manifest-listed legacy TS files retain their original explicit `any` annotations under a scoped lint exception. This is migration debt, not a claim of fully rebuilt source typing.
- Fixed confirmed defects: source pre-operation history could skip the latest edit; imports now reset the history baseline; save responses cannot mark newer content saved; stop failures do not prematurely clear execution; an empty active folder means the default folder.

## Mock semantics

Documents, virtual folders, modules, assets and settings persist in browser-local storage under AutoFlow-specific keys. Running, picking, recording and the event journal are in-memory fixtures. The mock visits the frozen node array to exercise UI events; it does not evaluate conditions, loops, expressions or browser actions. The UI continuously displays this distinction.

File uploads retain bytes (2 MiB per file, explicit failure on limits/quota). Excel parsing, generated backend scripts, model answers and connection probes are fixtures. Credentials retain masked metadata only. Unknown endpoints return 501 and external network targets are rejected; native tools and external integrations require the later backend adapter. Virtual folders are not AutoFlow workspace SQLite storage. No mock records are silently migrated to production.

Validation and remaining integration work: `docs/migration/studio-frontend-mock-validation.md`.
