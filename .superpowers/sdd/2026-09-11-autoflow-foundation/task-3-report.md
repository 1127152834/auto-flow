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

## Review Fixes

- Electron now prevents the first `before-quit`, stops the supervisor, and calls `app.quit()` after shutdown; the handler is guarded so stop runs once.
- A pending startup is rejected and its timer cleared when restart or shutdown cancels it.
- The supervisor only publishes `ready` after an authenticated loopback `/health` response confirms `status`, `apiVersion`, and `instanceId`.
- Packaged startup requires an explicit sidecar executable path; main resolves it under `process.resourcesPath/sidecar` with the Windows `.exe` suffix.
- Platform child paths use `node:path.join`.

Review-fix validation:

```text
npm --workspace @autoflow/desktop test -- src/main/sidecar/ready-protocol.test.ts src/main/sidecar/supervisor.test.ts src/main/platform/paths.test.ts
7 tests passed

npm --workspace @autoflow/desktop run typecheck
passed
```

## Race Fix

- Added a startup generation token tied to the spawned child.
- Delayed health responses from an expired, stopped, timed-out, or restarted startup can no longer publish `ready` or stop a newer child.
- Added a hanging-health race test that stops the supervisor before releasing the health response.

Race-fix validation:

```text
npm --workspace @autoflow/desktop test -- src/main/sidecar/ready-protocol.test.ts src/main/sidecar/supervisor.test.ts src/main/platform/paths.test.ts
8 tests passed

npm --workspace @autoflow/desktop run typecheck
passed
```

## Deviations

- The Task 3 files were already present in the working tree as untracked files; this implementation completed and corrected that existing slice rather than recreating it.
- Full Electron build validation is deferred until Task 4 creates the renderer entrypoint.
- No WebRPA runtime or integration was added.
