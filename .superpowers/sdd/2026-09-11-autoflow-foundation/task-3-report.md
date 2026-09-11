# Task 3 Report: Electron Main, Preload, and Sidecar Supervisor

## RED

- `npm --workspace @autoflow/desktop test -- src/main/sidecar/ready-protocol.test.ts src/main/sidecar/supervisor.test.ts`
  - Passed the supplied readiness and status tests.
- `npm --workspace @autoflow/desktop run typecheck`
  - Failed because `SidecarEvent` used an invalid conditional type, so the `ready` event was not discriminated correctly.

## GREEN

- Replaced the invalid event type with a normal discriminated union.
- Kept readiness parsing strict for the `AUTOFLOW_READY` prefix, JSON payload, `v1` API version, non-empty instance ID, and ports `1..65535`.
- Added development and production sidecar argument handling, generated a per-start token, passed the injected data directory, and handled readiness timeout, malformed readiness, startup errors, unexpected exits, and graceful shutdown.
- Made the Electron `before-quit` handler one-shot and kept preload limited to `getSidecarStatus`, `restartSidecar`, and `getPlatformPaths`.

Validation:

```text
npm --workspace @autoflow/desktop test -- src/main/sidecar/ready-protocol.test.ts src/main/sidecar/supervisor.test.ts
3 tests passed

npm --workspace @autoflow/desktop run typecheck
passed
```

## Deviations

- The Task 3 files were already present in the working tree as untracked files; this implementation completed and corrected that existing slice rather than recreating it.
- Full Electron build validation is deferred until Task 4 creates the renderer entrypoint.
- No WebRPA runtime or integration was added.
