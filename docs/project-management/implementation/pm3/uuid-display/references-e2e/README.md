# Unavailable resource reference E2E evidence

Status: passed on 2026-09-15 with real Electron, FastAPI, and an isolated SQLite workspace.

The project was created through the UI. Workflows were created through the production `WorkflowService`, and automation fixtures containing canonical but unavailable resource UUIDs were saved through the public automation HTTP write contract. No database rows were edited directly.

The screenshots cover the fixed environment message and expanded Select options for an unavailable model provider, fixed proxy, and browser profile. The automated audit checked visible text, `title`, `placeholder`, `aria-label`, and `aria-description` against every known internal UUID and its eligible eight-character prefix. Each resource uses a semantic unavailable-reference label, with no ID fallback.

`result.json` is copied unchanged and retains the original temporary evidence path and source hashes. `run.log` contains the structured result only and does not contain a runtime token. Force-stop confirmation remains outside this scenario.
