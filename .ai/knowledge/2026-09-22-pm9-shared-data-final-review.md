# PM9 C/R 整批独立审查

日期：2026-09-22。状态：confirmed（审查发现与 RED）；最终回归进行中。来源：一次 fresh-context 只读独立审查，e71785da..9afe3be5，以及实际 HTTP/SQLite 反例。

3 项 Important、0 Critical、0 Minor；全部接受并在一轮修复中处理。详见 docs/project-management/implementation/pm9/shared-data-final-review.json。UUID 类型归一化、未知写核验归属、来源身份坏观察传播均复现后修复，不添加新执行器。

完整前端在 9afe3be5 为 5469 passed / 409 files / 198.85 秒，前端之后未改。初次后端完整回归仍针对修复前候选，后续用新完整运行验证最终代码。

## 执行裁定完整记录

Task 1: Ruling: persist identity verification on binding plus per-record SyncRecordMarkRow identity evidence; a nullable migration leaves old bindings unverified until a complete pull. Reuse marks with merged JSON to preserve outbound facts. Column coordinate plus observed header is the conservative initial namespace; moved/renamed identity requires explicit repair, not guessed adoption. Cost: extra pull/repair after source edits, but no accidental concurrent claim.
Task 2: Ruling: a workflow-created local record reserves its verified public identity before it exists remotely; only the create transaction may skip remote membership. New public locks still arbitrate duplicates; no remote append is implied. Cost: a local created row is not runnable by another task until it is proven present remotely.
Task 2: Ruling: use latest compatible peer scan for source membership and capture the binding peer set. Rebinding/removing a peer forces a fresh local pull, so deleting a peer cannot erase known bad identity evidence. Archived stale peers need not all pull before a newer valid scan is useful. Cost: extra pull when peer bindings change.
Task 4: Ruling: C3 real worker tests jointly provide C4 recovery evidence; reuse the completed 29-case run plus latest 3-case independent-status run, do not rerun identical workers only for task numbering. Full backend found exactly four stale pm08 head expectations (3345 pass/63 skip); corrected four pass and C3 14-test gate pass. Native matrix will provide the single green full-suite run. Cost: local aggregate evidence is explicitly mixed runs.
Task 4: Native matrix 35597323657 started at frozen 21f8bb1e; branch pushed and draft PR updated. Still pending, not complete. Ruling: continue R1 implementation while C4 native CI runs on its immutable commit; preserve both source scopes and revisit results before final completion. Cost: C4 failures may interrupt R1 for a targeted fix.
Task 6: Ruling: DataSchemaService currently rejects omitted fields and has no delete implementation; extend its explicit complete candidate with removedFieldIds rather than inventing a separate deletion executor. The worker constructs exactly one removal from the current full schema, and shared commit checks all dependencies in its caller-owned transaction. Management candidates without removals preserve their contract. Cost: shared schema regression required.
Task 4: Windows full backend/frontend passed, real worker step 13 failed/5 passed with worker lost; ARM full job passed. Ruling: use a bounded existing-workflow probe to collect payload-free protocol phase/exit diagnostics before choosing a fix; do not blindly rerun the full matrix. R3 implementation may continue independently while native diagnosis runs.
Task 9: started at 9d145a14, corrected R3 listing interleaved as 0ff31a3d. Ruling: append the column at the current grid end, keep generation/epoch and field identities unchanged, queue present values via existing intent rows with confirmed column dependencies. Use the existing DataImpactRow protocol with a dedicated compatible-extension action, since rebind impact intentionally blocks active Task leases and replaces the dataset. Cost: extra owned-column metadata check during sync; real Google remains external evidence.
Final: Ruling: Google live OAuth/UUID/column operations remain external acceptance — controlled transport cannot prove live authorization — cost: production service behavior remains unaccepted.
Final: Ruling: current packaged complete Sheets and physical installation/signing remain external — existing platform package smoke does not exercise complete real Google chain — cost: release stays blocked.
Final: Ruling: Windows Job/venv behavior requires current native Actions matrix — local review plus previous native hash is insufficient — cost: new native regression may require another scoped fix.
Final: Ruling: M1–M3, cross-process human recovery and all Studio admission remain excluded — explicit authorization boundary — cost: those actual capabilities remain missing.
Final: Ruling: unchanged pre-base S1–S5 keep earlier review scope — inspect C/R intersections only — cost: earlier evidence is not a new whole historical audit.
Final: Ruling: indistinguishable external row motion and remote read/write interleaving keep approved fail-closed/evidence limits — do not invent an unapproved remote transactional protocol — cost: external collaborators can invalidate source assumptions between requests; full release does not claim atomic external edits.
Final: Ruling: generated and historical evidence text relies on source contract, generator checks and exact commit-scoped reports — no manual word-by-word generated audit — cost: report scope must remain explicit and generator gates must pass.

134 项相关完整回归通过（132.41 秒），包含全部三项审查修复、原身份恢复、共享领取、旧 schema 删除、同步恢复与契约。ruff/mypy(407) 与生成检查通过。最终完整后端与当前三平台矩阵尚待执行。
