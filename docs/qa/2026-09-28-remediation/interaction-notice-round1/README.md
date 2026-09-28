# Project interaction notice review-fix evidence

Captured on 2026-09-28 from the isolated Task 3 round-1 source-Electron QA session. The preserved workspace and SQLite database remain at `/tmp/autoflow-task3-round1-qa.UlhnXI`.

## Isolation and identity

- Source renderer: `/Users/zhangtiancheng/Documents/projects/autoflow/apps/desktop/out/renderer/index.html`
- Main PID: `55287`
- Sidecar PID/PPID: `55301` / `55287`
- Sidecar instance: `55287-1790580512419`
- Project: `718795f2-40ae-4167-bb55-bec829df9a82`
- Workflow: `78563c3d-87b1-4c6e-a8d2-8e70324e62b8`
- Automation: `320e22b3-e2b6-4442-9287-088065c9ff6b`

The workspace was copied at `2026-09-28T15:28:15+0800` from the prior dedicated Task 3 workspace. Both source and copy had SQLite SHA-256 `08f06a3b429bcab97a10362461ea491fb6685cb6878c1e8daa6fb52b5bb8189e` before this run. The final copied database SHA-256 is `492a09bfe9eb0e2f5c967590b1870d464e7125184bfed54390cf48bb1046a192`, so the rows below are attributable to this round's copied workspace rather than counted again from the old run.

## Real execution evidence

The independent successful run used batch `2c82d320-47a6-457e-89e6-8dd462f6ce7a`, task `84908701-ce45-4571-8763-d97c02afb4d5`, and run `70bae1a2-f936-455d-86fd-41ac6330f709`. SQLite records one distinct script attempt, one script output, and result `task3-original-result`.

The active-outage run used batch `c05fd0df-484e-4d4d-b5c4-be4e2e018560`, task `9c94e341-2071-447a-a24a-f5c7fa2b54ce`, run `d25462ec-6c04-4bd9-9f21-c7c987ac4762`, and interaction request `c0d1d0be-b921-44c2-a131-b9980a00bdb7`.

Only the verified dedicated sidecar PID `55301` was stopped at `2026-09-28T15:46:32+0800`. While the batch was visibly running, `active-interrupted.png` and `active-interrupted.ax.txt` show `项目交互连接中断，正在查询原请求；未重新执行脚本`. The same PID was continued at `2026-09-28T15:47:12+0800`; `active-recovered.png` and `active-recovered.ax.txt` show the transport notice removed while the actual operation error `交互命令不存在` remains.

The 40-second stop exceeded the backend interaction lifetime. SQLite therefore records this interaction as `expired` and the run as failed. This is evidence for notice recovery and preservation of a real operation error; it is not counted as a successful execution. The deterministic component regression covers the narrower transient request-read recovery and verifies one worker execution.

## Files

- `active-interrupted.png`, `active-interrupted.ax.txt`: actual CUA screenshot and AX tree during the active outage.
- `active-recovered.png`, `active-recovered.ax.txt`: actual CUA screenshot and AX tree after transport recovery.
- `query-round1.sh`: reproducible read-only queries for the two new runs.
- `sqlite-readonly-results.txt`: actual output from the query script.
- `pre-run-db-identity.txt`: source/copy database identities before launching the round-1 app.
- `runtime-identity.txt`: exact renderer, process, project, batch, task and run identities.
- `instance-exit-readonly.txt`: verifies the dedicated main/sidecar exited and the unrelated user app remained running.
- `asset-sha256.txt`: SHA-256 digest for every other archived evidence file.

No external HTTP success was substituted. The unrelated `/Users/zhangtiancheng/Documents/projects/autoflow-android-handoff` app was not controlled or interrupted.
