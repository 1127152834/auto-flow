# Data UUID E2E evidence

Status: passed on 2026-09-15 with real Electron, FastAPI, and an isolated SQLite workspace.

The system-identity table, fields, status, and record were created through the UI. The record title is `温室光照笔记`; a separate business field named `外部参考` contains a UUID. Screenshots 11–15 verify that the record list, detail title, edit title, status view, and delete target use the business title while the internal system record key remains absent from perceptible UI.

The field-identity table was created through the real Excel inspection, field mapping, identity mapping, and import services. Screenshots 21–23 verify that the UUID selected by the user as the business identity remains visible.

`result.json` is copied unchanged from the isolated run and retains the original temporary evidence path plus source and bundle hashes. `run.log` contains the structured result only and contains no runtime token. The automated audit checked visible text, `title`, `placeholder`, `aria-label`, and `aria-description`; it intentionally did not inspect DOM values, links, hashes, or `data-*` attributes.

The data scenario does not cover force-stop confirmation or unavailable resource references; those remain listed in `result.json` for the run scenario and resource-state evidence.
