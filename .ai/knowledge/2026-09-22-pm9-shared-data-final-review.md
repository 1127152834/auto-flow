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

9afe3be5 首次全量后端为 1 failed / 3427 passed / 67 skipped / 740.91 秒。唯一失败是旧规则仍期望系统身份 notImplemented；按 R3 已批准契约改为显式列必须存在，缺列拒绝，普通列/未知策略拒绝不变。当前生产源码不因旧断言改变；新完整回归接续。

35628831527 在两台 Mac 的 ruff check . 阶段失败，5 项测试导入格式 I001；本机先前仅检查 src，范围不足。改为完全相同门禁并修正导入布局，ruff check . 通过，非 import AST 无变化。取消余下旧矩阵，新候选重跑原三平台；不冒充原生功能失败或通过。

最终本机后端 3440 passed / 67 skipped / 2 warnings / 772.39 秒，覆盖三项审查修复。d75297fb 仅整理测试导入，生产源码与该完整运行一致；全目录 ruff 及 Windows 平台 mypy(407) 通过。当前原生矩阵 35629585683 固定 d75297fb。

2026-09-22 原生跟进（confirmed，来源 Actions 35629585683）：Windows 全后端 1 failed/3429 passed/77 skipped，唯一旧测试将 SQLite 准备、执行与终结唤醒合计限制为 1 秒。改为先证明调度器等待，再证明真实 Core 终结通知和批次完成，30 秒兜底不改；34 passed/20.23 秒。临时副本禁用 subscribe_idle 后准确失败于 terminal notification 断言，不计作产品失败。ARM 全后端通过、全前端 1 failed/5468 passed；HTTP 状态仍在读取时 findByRole 默认 1 秒超时。受控 1100ms 状态延迟重现同一失败，按真实 HTTP 阶段等待控件，保留 starts=1/closes=0 和服务端最终 picking 状态断言。修正仅在 PM9 工作区测试文件，生产 Studio 源码与主工作区均未改。Intel 旧候选继续运行，失败平台在测试提交后重跑。

HTTP 延迟反例由 1 failed/1 passed 变为 4 passed/3.66 秒（原文件与临时延迟副本），临时副本已移除；正式命令/生命周期两文件 20 passed/2.09 秒。所有互斥、最终状态和错误恢复断言保留。

D1（已批准）在当前候选 5d1f4608：安全来源业务 Scalar 的 Sheets/XLSX 物化保留原值，记录快照派生 validationIssues，工作流投影按授权字段过滤；身份/unsafe Scalar/人工写入严格。134 项相关后端、11 项 UI、mypy407、Ruff、OpenAPI、typecheck 通过。真实浏览器过滤命中 0 项，未声称 worker 证据；打包/实网/三平台 D1 仍待新候选。


2026-09-22 D1 候选更新（confirmed）：生产候选 ae347de9f5fc1922efa7c4af99c0e606e6bde26a 已推送，三平台 Actions 35638303073 正在运行；native probe 与 worker probe 由工作流跳过，不计为证据。D1 本机 134 后端、11 UI、mypy407、Ruff、OpenAPI、typecheck 通过；真实 worker、打包完整链、实网授权与实机安装仍待外部条件。

2026-09-22 D1 review RED→GREEN（confirmed）：独立审查发现 Excel 身份字段错误回退、Excel/Sheets 缺失值物化、Sheets 坏身份半批发布；均已在共享源验证入口修复。身份字段业务校验现在拒绝导入，缺失字段不写入 values，Sheets 先完整预校验后再 ingest。D1 相关四文件 138 passed/2 warnings，Ruff 与 mypy 407 通过；需要对 post-review SHA 重新运行三平台 CI。UI 诊断为字段列表后的聚合面板，保留为 Minor 表达差异。
2026-09-22 D1 post-review candidate ae347de9f5fc1922efa7c4af99c0e606e6bde26a pushed; Actions 35677887974 manually dispatched for all three platforms and is queued. No release acceptance is inferred while it runs.
本机补充真实 worker（当前 post-review 源码）：data-response-loss 1 passed/28 deselected（10.46s）；data-schema/data-delete-field/data-old-candidate 4 passed/25 deselected（56.60s）。这些证明现有 PM9 HTTP/SQLite/CloakBrowser 场景，未扩写为 D1 坏值专门准入。
