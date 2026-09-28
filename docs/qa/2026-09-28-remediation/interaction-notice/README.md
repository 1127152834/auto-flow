# Project interaction notice recovery evidence

Captured on 2026-09-28 from the isolated Task 3 source-Electron QA session. These files contain read-only evidence only; they do not replace the preserved SQLite database.

## Preserved source

- QA workspace: `/tmp/autoflow-task3-qa.j6AbYM`
- SQLite: `/tmp/autoflow-task3-qa.j6AbYM/data/autoflow.sqlite3`
- SQLite SHA-256 at 2026-09-28T14:45:53+0800: `08f06a3b429bcab97a10362461ea491fb6685cb6878c1e8daa6fb52b5bb8189e`
- Main PID during QA: `56848`
- Sidecar PID during QA: `56855`, PPID `56848`
- Sidecar instance: `56848-1790577093419`
- Verified stop window: sidecar was `T+` by `2026-09-28T14:38:22+0800`
- Resume: `2026-09-28T14:38:45+0800`

## Durable identities

- Project: `718795f2-40ae-4167-bb55-bec829df9a82`
- Workflow: `78563c3d-87b1-4c6e-a8d2-8e70324e62b8`
- Automation: `320e22b3-e2b6-4442-9287-088065c9ff6b`
- Batch: `bc3cd2d2-d62f-49c8-ac1c-64b6460300bf`
- Task: `1b7823b4-6930-4ede-98a0-0e3e460297da`
- Run: `d6befbcf-cdc3-4303-b9e4-c9f2dc28eae2`
- Run request: `4b0b3fe9-7dfd-4822-b40a-e67562e96e92`
- Interaction request: `1304189d-8e0e-40e9-946e-ac2b91f5275a`
- Script node visit: `855f2ae6-d1cd-4715-89fe-dba53c78c6ea`

## Files

- `query-interaction-notice.sh`: reproducible `sqlite3 -readonly` queries. Pass a different database path as argument 1 if the preserved workspace is moved.
- `sqlite-readonly-results.txt`: actual output from that script against the preserved database.
- `instance-exit-readonly.txt`: read-only process, directory, SQLite presence and checksum verification after the isolated app exited.

No CUA screenshot or AX dump was saved as a filesystem artifact during the live run. None is reconstructed here. The live CUA observations remain recorded in the Task 3 execution transcript and the task report describes them.
