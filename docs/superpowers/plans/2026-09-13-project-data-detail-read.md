# Project Data Detail Read Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build the read-only table detail page with scoped loading, server-side record querying, five real tabs, record detail, and leave protection for filter drafts.

**Architecture:** `DataTableDetailPage` owns one committed table scope and constructs the existing table, catalog, and record API clients from it. TanStack Query owns cancellation and caching; every query key contains workspace, instance, project, table, generation, and the relevant applied query/page so stale responses cannot enter the current scope. `RecordFilterEditor` remains the only query draft owner; the page stores only applied query and page number.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, existing StreamingApiClient, Radix Tabs/Modal, project-data API clients.

**Spec:** `docs/superpowers/plans/2026-09-13-project-management-pm2.md` section C2b

## Global Constraints

- Create only `apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.tsx` and its adjacent test.
- Do not modify App, routes, generated types, shared components, editors, or backend code.
- All record filtering, ordering, and pagination run through `recordsApi.list`; the page performs no local business filtering.
- The page exposes no create, edit, delete, import, export, or status-write action.
- Query identity includes workspace, instance, project, table, generation, applied filter/order, and page.
- Dirty filter drafts survive reconnects within the same workspace/project/table and block navigation through `registerLeaveGuard`; project/table changes reset them.

---

### Task 1: Freeze the page contract and scoped loading

**Files:**
- Create: `apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.test.tsx`
- Create: `apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.tsx`

**Interfaces:**
- Consumes: `createProjectDataApi(client, projectId)`, `createDataCatalogApi(client, scope)`, `createRecordsApi(client, scope)`.
- Produces: `DataTableDetailPageProps` with `workspaceKey`, `instanceId`, `projectId`, `tableId`, `tab`, `client`, `disabled`, `readonly`, `onBack`, `onTabChange`, and `registerLeaveGuard`.

- [x] Write a failing test that resolves table A after switching to table B and asserts A never renders.
- [x] Run `npm test -- --run src/renderer/domains/project-data/pages/DataTableDetailPage.test.tsx` and verify the missing component failure.
- [x] Implement TanStack Query scoped loading, retry, and the five controlled Tabs.
- [x] Run the test and verify the scoped header and navigation pass.

### Task 2: Load catalog and records from the current generation

**Files:**
- Modify: `apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.test.tsx`
- Modify: `apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.tsx`

**Interfaces:**
- Consumes: `DataRecordsTable`, `RecordFilterEditor`, `RecordQuery`, and table `datasetGeneration`.
- Produces: an applied-query state whose raw `filter` and `orderBy` are passed once to `recordsApi.list`.

- [x] Add failing tests for table → catalog → record request order, explicit Apply, pagination, refresh errors retaining the last page, and generation change clearing the old query/page.
- [x] Implement generation-scoped catalog and record queries whose query functions consume TanStack Query AbortSignals.
- [x] Render `DataRecordsTable` without mutation callbacks and wire retry, detail open, and server page changes.
- [x] Run the tests and verify no stale generation fields, statuses, records, or query survive.

### Task 3: Render factual tabs and record detail

**Files:**
- Modify: `apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.test.tsx`
- Modify: `apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.tsx`

**Interfaces:**
- Consumes: generated `DataTableView`, `DataFieldView`, `DataStatusView`, and `DataRecordView`.
- Produces: read-only field/status/source/settings sections and a record detail Modal loaded through `recordsApi.get(recordKey, signal)`.

- [x] Add failing tests for field flags, status color/revision, source identity/sync facts, settings metadata, and a real record detail request preserving missing/null/date/readability.
- [x] Implement factual lists and description blocks without invented counts or unavailable controls.
- [x] Implement record detail loading, retry/error state, TanStack Query cancellation, and readonly value rendering.
- [x] Run the tests and verify every displayed fact comes from generated DTO fields.

### Task 4: Protect dirty filters and verify the slice

**Files:**
- Modify: `apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.test.tsx`
- Modify: `apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.tsx`

**Interfaces:**
- Consumes: `RecordFilterEditor.onDirtyChange`.
- Produces: `registerLeaveGuard(guard | null)` where the guard returns whether navigation may proceed.

- [x] Add failing tests proving a dirty filter registers a guard, cancellation preserves the draft, reconnect preserves it, and workspace/project/table changes reset it.
- [x] Implement a committed leave guard for the parent navigation owner and an internal generation-change confirmation.
- [x] Run the page test, then `npm run typecheck`, targeted ESLint, and `git diff --check`.
- [x] Confirm the rendered page contains no mutation buttons and report the exported props to the parent integrator.

验收记录：C2b独立审查及最终606测试/真实读取场景见 `../../project-management/implementation/pm2-directory-deletions-verification.json`。仅本执行卡读取范围完成。
