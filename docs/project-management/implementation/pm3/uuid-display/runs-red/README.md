# Run UUID E2E pre-fix evidence

Status: expected failure on 2026-09-15 against the isolated temporary build identified by `UUID_SOURCE_HEAD=07988c1`.

The real Electron/FastAPI/SQLite flow created a project and automation through the UI, launched a batch with two tasks, and reached the batch detail page. The UUID audit then failed on the known batch ID in both `document.body.innerText` and a `title` attribute. The screenshot also records the old task and run identity presentation.

`run.log` contains the assertion report and no runtime token. This RED evidence must be superseded by the same scenario passing against the stabilized run UI; its failure assertion must not be removed or bypassed.
