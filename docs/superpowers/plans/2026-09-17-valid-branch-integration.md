# Valid Branch Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate every still-valid side-branch capability into `codex/architecture-baseline` without restoring superseded Studio code or disturbing the current uncommitted worktree.

**Architecture:** Protect the dirty checkout on a dedicated branch, then perform the integration in a clean linked worktree. Merge PM4 as the primary capability line; transplant and test the valid portions of Android, UI controls, tables, and proxy management; then record semantic reconciliation merges so reviewed branches become ancestors without reintroducing discarded files.

**Tech Stack:** Git worktrees and merge commits, Python 3.11/uv/pytest/Alembic/FastAPI, Node.js 22/npm/Electron/Vite/React/Vitest, generated OpenAPI TypeScript client.

**Spec:** `docs/superpowers/specs/2026-09-17-valid-branch-integration-design.md`

## Global Constraints

- Target branch is `codex/architecture-baseline`; integration work happens on `codex/integrate-valid-branches-20260917`.
- Preserve every tracked modification and untracked file in the current checkout byte-for-byte on `codex/pre-branch-integration-wip-20260917`.
- Do not restore the retired Studio, the old M1–M6 workflow model, or either archived checkpoint.
- Current Studio runtime, current migration history, current OpenAPI routes, workspace isolation, credential boundaries, leases, CAS, cancellation, and command recovery are authoritative.
- Do not rewrite or force-push existing source branches.
- Do not update the target branch or GitHub until the final verification matrix passes.
- Use existing dependencies and project patterns; add no integration framework or generic abstraction.

---

### Task 1: Protect the dirty checkout and create the integration worktree

**Files:**
- Verify only: all modified and untracked paths reported by `git status --short`
- Create worktree: `/Users/zhangtiancheng/Documents/projects/autoflow-branch-integration-20260917`

**Interfaces:**
- Consumes: `codex/architecture-baseline@95063572` and the existing dirty working tree.
- Produces: protected branch `codex/pre-branch-integration-wip-20260917`, clean integration branch `codex/integrate-valid-branches-20260917`, and recorded before/after hashes.

- [ ] **Step 1: Record the dirty checkout fingerprints**

Run:

```bash
git status --porcelain=v1 -z | shasum -a 256
git diff --binary | shasum -a 256
git ls-files --others --exclude-standard -z | xargs -0 shasum -a 256 | shasum -a 256
```

Save the three hashes in the task log outside the repository. The first fingerprints the path/status set, the second the tracked content delta, and the third all untracked file contents.

- [ ] **Step 2: Move the dirty checkout onto the protection branch**

Run:

```bash
git switch -c codex/pre-branch-integration-wip-20260917
```

Expected: branch creation succeeds without modifying the index or working files.

- [ ] **Step 3: Recompute all three fingerprints**

Run the Step 1 commands again. Expected: all three hashes exactly match Step 1. If any differs, stop without creating the integration worktree.

- [ ] **Step 4: Create the clean linked worktree**

Run from the original checkout:

```bash
git worktree add -b codex/integrate-valid-branches-20260917 /Users/zhangtiancheng/Documents/projects/autoflow-branch-integration-20260917 codex/architecture-baseline
```

Expected: the new worktree is on `codex/integrate-valid-branches-20260917` at `95063572` and `git status --short` is empty.

- [ ] **Step 5: Reuse installed dependency stores and establish the baseline**

Run in the integration worktree:

```bash
npm install
uv sync --directory apps/backend --locked
npm run test:structure
npm run typecheck
npm run openapi:check
uv run --directory apps/backend pytest tests/integration/test_migration_heads.py
```

Expected: all commands exit 0. A baseline failure blocks branch integration and must be reported before proceeding.

### Task 2: Merge PM3/PM4 while preserving the current Studio runtime

**Files:**
- Merge: `codex/project-management-pm4`
- Resolve: `apps/backend/src/autoflow/adapters/http/errors.py`
- Resolve: `apps/backend/src/autoflow/application/workflows/runtime.py`
- Resolve: `apps/backend/src/autoflow/bootstrap/app.py`
- Resolve: `apps/backend/src/autoflow/bootstrap/workflow_worker.py`
- Resolve: `apps/backend/src/autoflow/bootstrap/workflows.py`
- Resolve: `apps/backend/src/autoflow/infrastructure/database/migrations/env.py`
- Resolve: `apps/backend/src/autoflow/infrastructure/database/workflows.py`
- Resolve: `apps/backend/src/autoflow/infrastructure/process/browser_processes.py`
- Resolve: `apps/backend/src/autoflow/infrastructure/process/workflow_worker.py`
- Resolve: `apps/backend/src/autoflow/providers/browser/workflow_worker.py`
- Resolve: `apps/desktop/src/renderer/domains/workflows/components/BlockFlowView.tsx`
- Resolve: `apps/desktop/src/renderer/domains/workflows/components/DataTable.tsx`
- Resolve: `apps/desktop/src/renderer/domains/workflows/components/DebugBar.tsx`
- Resolve: `apps/desktop/src/renderer/domains/workflows/components/GlobalConfigDialog.tsx`
- Resolve: `apps/desktop/src/renderer/domains/workflows/components/LogPanel.tsx`
- Regenerate: `apps/desktop/src/renderer/shared/api/generated.ts`
- Test: `apps/backend/tests/contract/test_project_automations.py`
- Test: `apps/backend/tests/contract/test_project_runs.py`
- Test: `apps/backend/tests/integration/test_project_run_dispatch.py`
- Test: `apps/backend/tests/integration/test_project_data_scheduler.py`
- Test: `apps/backend/tests/integration/test_migration_heads.py`
- Test: `apps/desktop/src/renderer/domains/project-automations/**/*.test.ts*`
- Test: `apps/desktop/src/renderer/domains/project-runs/**/*.test.ts*`

**Interfaces:**
- Consumes: current `WorkflowRuntime`, worker/bootstrap composition, project and project-data contracts from the target branch, plus PM4 project automation/run/data models.
- Produces: PM4 project automation, batch, task, lease, data-write, and scheduling capabilities bound to the current workflow runtime; a two-parent PM4 merge commit.

- [ ] **Step 1: Start the PM4 merge without committing**

```bash
git merge --no-ff --no-commit codex/project-management-pm4
git diff --name-only --diff-filter=U
```

Expected: the unresolved list matches the known runtime, migration, fixture, generated-client, and Studio-component conflict families. Any unrelated conflict is added to the audit before editing.

- [ ] **Step 2: Preserve current workflow/runtime files as the starting side**

Use `git checkout --ours` for the current runtime, worker-process, browser-provider, old workflow fixture, and current Studio component conflicts listed above. Then inspect PM4 callers with:

```bash
rg -n "project_run|ProjectRun|dispatch|prepared_content|WorkflowRuntime" apps/backend/src apps/backend/tests
```

Adapt only the project-facing calls that fail against current signatures. Do not restore old worker or editor implementations.

- [ ] **Step 3: Resolve project-domain and migration composition**

Keep PM4 project automation/run/data modules and routes. Resolve `bootstrap/app.py` by registering both current Studio routes and PM4 project routes. Resolve migration conflicts by preserving every historical revision and adding a merge revision only when `uv run --directory apps/backend alembic heads` reports more than one unexplained head.

- [ ] **Step 4: Regenerate the client instead of merging generated text**

```bash
npm run openapi:generate
npm run openapi:check
```

Expected: both commands exit 0 and `generated.ts` contains routes present in the final FastAPI application.

- [ ] **Step 5: Run PM4 backend characterization tests**

```bash
uv run --directory apps/backend pytest \
  tests/contract/test_project_automations.py \
  tests/contract/test_project_runs.py \
  tests/integration/test_project_run_dispatch.py \
  tests/integration/test_project_data_scheduler.py \
  tests/integration/test_migration_heads.py -q
```

Expected: all pass. If a test exposes a current-runtime integration gap, add one focused regression to the nearest existing test file, verify it fails, implement the adapter, then verify it passes.

- [ ] **Step 6: Run PM4 desktop tests and compile checks**

```bash
npm test -- --run apps/desktop/src/renderer/domains/project-automations apps/desktop/src/renderer/domains/project-runs apps/desktop/src/renderer/domains/project-data
npm run typecheck
npm run build
```

Expected: all commands exit 0.

- [ ] **Step 7: Verify merge ancestry and commit**

```bash
git diff --check
git status --short
git commit -m "merge: integrate PM4 project execution capabilities"
git merge-base --is-ancestor codex/project-management-pm3 HEAD
git merge-base --is-ancestor codex/project-management-pm4 HEAD
git merge-base --is-ancestor codex/project-management-pm5 HEAD
```

Expected: commit succeeds and all three ancestry checks exit 0.

### Task 3: Port Android management without restoring the retired Studio

**Files:**
- Import from branch: `apps/backend/src/autoflow/adapters/http/android.py`
- Import from branch: `apps/backend/src/autoflow/application/android/`
- Import from branch: `apps/backend/src/autoflow/domain/android/`
- Import from branch: `apps/backend/src/autoflow/infrastructure/database/android*.py`
- Import from branch: `apps/backend/src/autoflow/providers/android/`
- Import from branch: `apps/desktop/src/renderer/domains/android/`
- Modify: `apps/backend/src/autoflow/bootstrap/app.py`
- Modify: `apps/backend/src/autoflow/bootstrap/schema_export.py`
- Modify: `apps/desktop/src/renderer/app/App.tsx`
- Modify: `apps/desktop/src/renderer/app/ApplicationHeader.tsx`
- Create: `docs/migration/branch-integration/android-capability-matrix.md`
- Test: Android tests under `apps/backend/tests/{unit,contract,integration}/`
- Test: `apps/desktop/src/renderer/domains/android/tests/`

**Interfaces:**
- Consumes: current workflow run/manual-input lifecycle and current navigation/API client.
- Produces: Android instance management and manual takeover using current contracts; a tree-preserving reconciliation merge with `codex/android-workflow-handoff`.

- [ ] **Step 1: Write the Android capability matrix**

List every Android backend module, renderer entry, shared integration point, and old workflow file changed by `codex/android-workflow-handoff`. Mark each as `port`, `already-current`, `replace-with-current-contract`, or `exclude-retired-studio`, with a one-sentence reason and verification command.

- [ ] **Step 2: Import isolated Android modules**

Use `git restore --source=codex/android-workflow-handoff --` only for Android-owned directories and Android-specific tests/scripts. Do not restore any file listed as a modify/delete Studio conflict in the design spec.

- [ ] **Step 3: Add a failing current-contract test for manual takeover**

In the nearest Android application or contract test, assert that takeover accepts the current run identity and returns the current manual-action envelope without importing old `workflow_schemas.py`. Run that single test and confirm it fails because the current adapter is missing.

- [ ] **Step 4: Bind Android routes and UI to current contracts**

Register Android routes in current bootstrap composition, map takeover through current workflow run/application services, and add navigation without replacing `App.tsx` or `ApplicationHeader.tsx`. Regenerate OpenAPI types.

- [ ] **Step 5: Verify Android behavior**

```bash
uv run --directory apps/backend pytest -q -k android
npm test -- --run apps/desktop/src/renderer/domains/android
npm run typecheck
npm run openapi:check
python scripts/smoke-android-management.py --help
python scripts/smoke-android-handoff.py --help
```

Expected: tests and checks exit 0; smoke scripts parse their documented arguments without starting an unapproved external runtime.

- [ ] **Step 6: Commit the Android port**

```bash
git add apps/backend apps/desktop scripts docs/migration/branch-integration/android-capability-matrix.md
git diff --cached --check
git commit -m "feat(android): reconcile management and manual takeover"
```

- [ ] **Step 7: Record a tree-preserving Android reconciliation merge**

```bash
before=$(git rev-parse HEAD)
git merge -s ours --no-ff codex/android-workflow-handoff -m "merge: reconcile android workflow handoff branch"
git diff --exit-code "$before" HEAD
git merge-base --is-ancestor codex/android-workflow-handoff HEAD
```

Expected: tree diff is empty and ancestry check exits 0.

### Task 4: Reconcile shared UI controls and the global table system

**Files:**
- Audit/import: `apps/desktop/src/renderer/shared/components/ui/`
- Audit/import: `apps/desktop/src/renderer/shared/components/{Drawer,FieldGroup,FormField,Modal,State,Toaster}.tsx`
- Audit/import: `apps/desktop/src/renderer/styles/{controls,tokens,tables}.css`
- Audit/import: `apps/desktop/src/renderer/domains/project-data/components/DataRecordsTable.tsx`
- Audit/import: `apps/desktop/src/renderer/domains/project-data/components/DataStatusTable.tsx`
- Audit/import: `apps/desktop/src/renderer/domains/workflows/components/DataTable.tsx`
- Audit/import: `apps/desktop/src/renderer/domains/workflows/styles/table-system.css`
- Create: `docs/migration/branch-integration/ui-table-capability-matrix.md`
- Test: colocated shared UI and table tests
- Test: `scripts/verify-table-system.mjs`

**Interfaces:**
- Consumes: PM4 renderer tree and current Studio component contracts.
- Produces: only missing shared-control and fine-grid table behavior, plus tree-preserving reconciliation merges for `codex/ui-controls-plan` and `codex/global-table-system`.

- [ ] **Step 1: Build the UI/table capability matrix**

Compare source-branch and current files using `git diff --no-index` or `git diff <branch> -- <path>`. Record for each shared component/table primitive whether current code is newer, equivalent, missing, or behaviorally incomplete. Exclude old UI Lab production entry points and historical screenshot-only changes.

- [ ] **Step 2: Add focused failing tests for each real gap**

Use the existing colocated tests. Each imported behavior gets one assertion that fails on the current tree: focus restoration/overlay containment for controls, or density/fixed-column/query-toolbar semantics for tables. Run each test file before implementation and record the expected failure.

- [ ] **Step 3: Port the smallest current-compatible implementation**

Copy only the primitive or rule required by the failing test. Update current callers through their existing props and types; do not replace current pages with the old branch versions and do not add a second overlay/table abstraction.

- [ ] **Step 4: Verify controls and tables**

```bash
npm test -- --run apps/desktop/src/renderer/shared/components apps/desktop/src/renderer/domains/project-data apps/desktop/src/renderer/domains/workflows/tests/data-table.test.tsx
npm run typecheck
npm run lint
node scripts/verify-table-system.mjs
```

Expected: all commands exit 0.

- [ ] **Step 5: Commit the current-compatible UI/table port**

```bash
git add apps/desktop scripts docs/migration/branch-integration/ui-table-capability-matrix.md
git diff --cached --check
git commit -m "feat(ui): reconcile shared controls and table system"
```

- [ ] **Step 6: Record tree-preserving reconciliation merges**

For each branch, record `before=$(git rev-parse HEAD)`, run an `ours` merge, require `git diff --exit-code "$before" HEAD`, and require the ancestry check:

```bash
git merge -s ours --no-ff codex/ui-controls-plan -m "merge: reconcile unified UI controls branch"
git merge-base --is-ancestor codex/ui-controls-plan HEAD
git merge -s ours --no-ff codex/global-table-system -m "merge: reconcile global table system branch"
git merge-base --is-ancestor codex/global-table-system HEAD
```

### Task 5: Audit and reconcile proxy management

**Files:**
- Audit: `apps/backend/src/autoflow/application/proxies/`
- Audit: `apps/backend/src/autoflow/domain/proxies/`
- Audit: `apps/backend/src/autoflow/providers/proxy/`
- Audit: `apps/desktop/src/renderer/domains/proxies/`
- Create: `docs/migration/branch-integration/proxy-capability-matrix.md`
- Test: proxy backend and desktop tests

**Interfaces:**
- Consumes: current proxy implementation including remote locations and rotation controls.
- Produces: evidence for every source-branch capability, any focused gap fixes, and a tree-preserving reconciliation merge with `codex/proxy-management`.

- [ ] **Step 1: Build and verify the proxy capability matrix**

Record connection CRUD, credentials, copy IPC, health probe, foreign keys, optimistic concurrency, transactional sync, local groups, ProxyPanel mapping, packaging, and renderer coverage. Cite a current file and test for each covered item.

- [ ] **Step 2: Run the current proxy suite**

```bash
uv run --directory apps/backend pytest -q \
  tests/contract/test_proxy_api.py \
  tests/contract/test_proxy_runtime.py \
  tests/integration/test_proxy_management.py \
  tests/integration/test_proxy_concurrency_review.py \
  tests/unit/test_proxy_domain.py \
  tests/unit/test_proxy_probe.py \
  tests/unit/test_proxypanel_transport.py
npm test -- --run apps/desktop/src/renderer/domains/proxies
```

Expected: all pass. A matrix row without code/test evidence becomes a focused red-green fix before reconciliation.

- [ ] **Step 3: Commit the matrix and any verified gap fixes**

```bash
git add apps/backend apps/desktop docs/migration/branch-integration/proxy-capability-matrix.md
git diff --cached --check
git commit -m "docs(proxy): reconcile proxy management capabilities"
```

- [ ] **Step 4: Record the tree-preserving proxy reconciliation merge**

```bash
before=$(git rev-parse HEAD)
git merge -s ours --no-ff codex/proxy-management -m "merge: reconcile proxy management branch"
git diff --exit-code "$before" HEAD
git merge-base --is-ancestor codex/proxy-management HEAD
```

Expected: tree diff is empty and ancestry check exits 0.

### Task 6: Record exclusions and integrated branch state

**Files:**
- Modify: `.ai/memory/project-context.md`
- Create: `.ai/decisions/2026-09-17-valid-branch-integration.md`
- Create: `docs/migration/branch-integration/README.md`

**Interfaces:**
- Consumes: the four capability matrices and final commit graph.
- Produces: a stable record of included, superseded, and intentionally excluded branches.

- [ ] **Step 1: Write the integration decision**

Record exact source tips, integration/reconciliation commits, conflict policies, test commands, and the reasons `m6-unfinished-checkpoint-20260913` and `studio-before-removal-20260913` remain outside the target branch.

- [ ] **Step 2: Add machine-checkable ancestry assertions to the README**

Document these checks and their expected statuses:

```bash
for b in codex/project-management-pm3 codex/project-management-pm4 codex/project-management-pm5 codex/android-workflow-handoff codex/global-table-system codex/ui-controls-plan codex/proxy-management; do git merge-base --is-ancestor "$b" HEAD; done
for b in codex/m6-unfinished-checkpoint-20260913 codex/studio-before-removal-20260913; do ! git merge-base --is-ancestor "$b" HEAD; done
```

- [ ] **Step 3: Commit integration records**

```bash
git add .ai/memory/project-context.md .ai/decisions/2026-09-17-valid-branch-integration.md docs/migration/branch-integration
git diff --cached --check
git commit -m "docs: record valid branch integration"
```

### Task 7: Run the full release-quality verification matrix

**Files:**
- Verify: repository-wide code, migrations, generated API, scripts, and Electron startup
- Create: `docs/migration/branch-integration/verification.md`

**Interfaces:**
- Consumes: completed integration branch.
- Produces: fresh command evidence sufficient to fast-forward the target branch.

- [ ] **Step 1: Run backend and migration verification**

```bash
uv run --directory apps/backend pytest
uv run --directory apps/backend alembic heads
uv run --directory apps/backend pytest -q \
  tests/integration/test_migration_heads.py \
  tests/integration/test_merged_model_migrations.py \
  tests/integration/test_project_migration.py \
  tests/integration/test_project_data_migrations.py \
  tests/integration/test_studio_migration_compatibility.py
```

Expected: pytest has zero failures; Alembic reports one explained head; the migration tests upgrade task-owned temporary databases through the final head. Do not run a migration command against the user's application database.

- [ ] **Step 2: Run frontend and repository verification**

```bash
npm test
npm run typecheck
npm run lint
npm run build
npm run test:structure
npm run test:scripts
npm run openapi:check
```

Expected: every command exits 0.

- [ ] **Step 3: Run desktop/sidecar and applicable domain smoke tests**

```bash
npm run smoke:sidecar
npm run smoke:desktop
node scripts/verify-table-system.mjs
```

Run PM4 and Android smoke scripts only in their documented isolated/test modes. Do not start an external Android runtime, modify real project data, or use real credentials without a task-owned fixture.

- [ ] **Step 4: Verify graph and worktree invariants**

Run the ancestry checks from Task 6, confirm `git status --short` is empty in the integration worktree, and recompute all three fingerprints in the protected original checkout. Expected: valid branches are ancestors, excluded checkpoints are not, integration worktree is clean, and protected hashes match Task 1.

- [ ] **Step 5: Record fresh evidence and commit**

Write command, timestamp, exit code, test count, OS/architecture, and any explicitly unrun hardware/manual checks to `verification.md`.

```bash
git add docs/migration/branch-integration/verification.md
git diff --cached --check
git commit -m "test: verify valid branch integration"
```

### Task 8: Fast-forward the target branch and push GitHub

**Files:**
- Update ref: `codex/architecture-baseline`
- Push: `origin/codex/architecture-baseline`

**Interfaces:**
- Consumes: clean, fully verified `codex/integrate-valid-branches-20260917`.
- Produces: local and remote target branch at the verified commit, while the dirty checkout remains on its protection branch.

- [ ] **Step 1: Confirm fast-forward eligibility**

```bash
git merge-base --is-ancestor codex/architecture-baseline codex/integrate-valid-branches-20260917
git status --short
```

Expected: ancestry succeeds and the integration worktree is clean.

- [ ] **Step 2: Fast-forward the target ref**

From a worktree where neither command touches the protected files:

```bash
git branch -f codex/architecture-baseline codex/integrate-valid-branches-20260917
```

Expected: target and integration branch resolve to the same commit.

- [ ] **Step 3: Push without force and verify remote hashes**

```bash
git push origin codex/architecture-baseline
git rev-parse codex/architecture-baseline
git ls-remote origin refs/heads/codex/architecture-baseline
```

Expected: push succeeds and local/remote hashes match.

- [ ] **Step 4: Report the protected WIP separately**

Report the protection branch, original checkout path, unchanged fingerprints, integrated source branches, excluded checkpoint branches, final target hash, remote URL, all verification results, and any hardware/manual limitations.
