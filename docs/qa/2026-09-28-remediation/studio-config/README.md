# Task 6 Studio configuration shape evidence

Date: 2026-09-28
Status: implementation verified; packaged native acceptance pending root validation.

## Defect and boundary

The packaged native session proved a namespace split: production Runtime executed `node.data.config`, while Studio displayed and edited same-named fields on outer `node.data`. The preserved source evidence is under `../native-session-VwvJnD/`, including `end-config-before-edit-studio.json`, `end-config-saved-studio.json`, and `end-saved-sqlite.json`.

The repair keeps each document's existing shape:

- A valid nested `config` object is the complete effective runtime configuration. Missing nested keys do not fall back to stale same-named outer fields.
- `moduleType` and `label` remain explicit editor identity fields from outer data.
- Configuration edits update an existing nested object, or remain flat for a flat document.
- Outer node remark `name`, disabled/highlight state, editor metadata, unknown outer fields, unknown nested fields, node metadata, positions, and edges remain in their original namespaces.
- Import, merge, export, and save/load keep the original raw document shape; there is no migration or silent normalization.

## Evidence

- `red.log`: console-result summary showing old behavior fails on nested End display and shared numeric preflight; it is not full stdout.
- `green-frontend.log`: console-result summary for focused whole-file frontend regression, typecheck, lint, and whitespace verification; it is not full stdout.
- `green-backend-runtime.log`: console-result summary for independent existing production Runtime/executor extraction and frozen snapshot checks; it is not full stdout.

The focused regression covers nested End display/edit, nested Open Page save/reload, strict whole-object priority with stale outer fields, flat compatibility, unknown field and metadata preservation, import/merge/export, assistant edits, history/no-op behavior, preflight, variable/config readers, structure copy, and editor interactions.

Root still owns the same-version packaged native validation: edit End configuration in Studio, save, reopen, fully restart, compare SQLite, and execute the real Project End environment-name path. This directory does not claim that pending native acceptance.
