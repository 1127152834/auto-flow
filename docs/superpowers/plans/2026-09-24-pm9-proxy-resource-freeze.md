# PM9 Proxy Resource Freeze Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使旧批次只使用固定代理候选/端点，失效时关闭新领取，并以真实 worker 验证。

**Architecture:** 扩展既有 frozenConfiguration 和资源装配，不新增表或第二执行器。既有代理选择 CAS 与 request_id 继续负责唯一选择；资源失败复用 Batch claim gate/selectionOutcome。凭据按需读取，不进入快照。

**Tech Stack:** Python 3.11、现有 SQLAlchemy/SQLite、FastAPI、Node 验收脚本、CloakBrowser、现有 GitHub Actions。

**Spec:** `docs/superpowers/specs/2026-09-24-pm9-proxy-resource-freeze.md`（proposed，批准后实施）。

## Global Constraints

- 不新增执行器或代理服务，不将密码写入快照/renderer/日志。
- 快照新增 `proxySelection`，版本 `schemaVersion:1`。
- 网络探测和凭据读取在短事务外完成，不能持 SQLite 事务等待网络。
- 即使 continueAfterFailure=true 也不能继续消耗记录。
- 历史 fixed/pool 缺 `proxySelection` 时返回明确资源快照缺失并关闭新领取。
- 现有分支提交/推送/草稿 PR，不合并发布；releaseAccepted=false。

## Review Focus

- 选择后到 credential loader 返回之间端点变化：必须再验，不启用新端点（P1）。
- 同 request_id 已有选择但其成员被移除：拒绝，不漂移到其它候选（P1）。
- malformed/旧快照不能静默重新冻结当前成员，none 不被误伤（P1）。
- continueAfterFailure=true 且另一 Task 已运行：关新领取，保留正在运行者已分配身份（P2）。
- inputEnvironment 只有领取后才知道代理：正确标识代次与 taskEnvironment 来源（P2/P3）。

## P1 固定代理资源快照与正式解析

**Files:**
- Modify: `apps/backend/src/autoflow/application/proxies/groups.py`（在现有选择器增加固定集合限制）。
- Modify: `apps/backend/src/autoflow/bootstrap/proxies.py`（正式冻结/解析装配、凭据后复验）。
- Modify: `apps/backend/src/autoflow/application/workflows/browser_resources.py`（写入/读取快照）。
- Modify: `apps/backend/src/autoflow/bootstrap/workflows.py`, `apps/backend/src/autoflow/bootstrap/app.py`（Studio 与项目共用装配）。
- Test: `apps/backend/tests/unit/test_workflow_browser_resources.py`, `apps/backend/tests/integration/test_proxy_concurrency_review.py`, `apps/backend/tests/contract/test_proxy_runtime.py`。

**Interfaces:**
- Consumes: 既有 Profile.spec、GroupService.get、ProxyRepository.get_projections、credential loader。
- Produces: `freeze_profile_proxy(profile: Profile) -> dict[str, Any]` 与 `resolve_profile(profile: Profile, request_id: str, frozen_proxy: dict[str, Any] | None = None)`；普通独立测试浏览器两参数调用保持原契约，项目/Studio 冻结资源必须提供有效快照。
- `ResolveProxyForProfile.resolve_group(group_id, request_id, *, frozen_candidates=None)`：frozen_candidates 为固定候选 JSON 列表；旧两参数非冻结入口行为保持。

- [ ] 新增 RED：freeze 时 A，池改 B 后同资源第二 acquire 不得选择 B；同 ID 改端点不得使用新端点。使用现有真实 SQLite fixture，不断言模拟选择器结果。
- [ ] 运行 `uv run --directory apps/backend pytest -q tests/unit/test_workflow_browser_resources.py tests/integration/test_proxy_concurrency_review.py tests/contract/test_proxy_runtime.py`，保存失败断言。
- [ ] 在现有代理代码实现版本/白名单/唯一 ID/模式/端点严格校验与候选序列化，字段结构固定如下，不复制 Projection 的健康状态或秘密：
  ```python
  snapshot = {"schemaVersion": 1, "mode": "pool", "proxyId": None,
              "proxyPoolId": group.id, "candidates": candidates}
  # candidate = {proxyId, connectionId, providerId, protocol, host, port}
  ```
- [ ] 正式 freeze 使用覆盖策略后的 Profile，写入 frozenConfiguration.proxySelection；acquire 只传该副本，不从现在的池补全旧快照。none 空集合允许；fixed/pool 缺失或损坏明确失败。
- [ ] 选择器在候选过滤、existing resolution 回放、探测后重读与现有 revision/CAS 提交处维持身份约束；loader 返回后读取一次当前 projection，核对身份/端点/启用/remoteMissing，再构造 worker 代理。
- [ ] 加入并发端点修改、重复 request_id、原候选移除、新协议端点添加、密码字段拒绝、unknown schemaVersion、历史 none/fixed/pool 的断言，运行上述目标文件到 GREEN。
- [ ] 更新规格落地状态和 .ai，提交 P1；尚不宣称 P2 领取契约完成。

## P2 任务分配与资源失败关闭领取

**Files:**
- Modify: `apps/backend/src/autoflow/application/project_runs/resources.py`, `apps/backend/src/autoflow/application/project_runs/coordinator.py`, `apps/backend/src/autoflow/application/project_runs/scheduler.py`。
- Modify: `apps/backend/src/autoflow/application/workflows/dispatcher.py`（只传递结构化资源失败，不改业务失败重试）。
- Test: `apps/backend/tests/integration/test_project_run_start.py`, `apps/backend/tests/integration/test_project_run_data_start.py`, `apps/backend/tests/unit/test_project_run_resources.py`。

**Interfaces:**
- Consumes: P1 proxySelection 与现有 resourceRequest、环境代次解析。
- Produces: 在 existing selectionOutcome 内记录 configurationError/资源原因；claim_gate_state=closed，既有 active Task 不自动撤销。资源异常 details.resourceReason 区分 frozen_source_missing/frozen_source_changed/no_frozen_candidate/credential_unavailable；只由父资源边界产生。

- [ ] RED：两条数据记录、maxTasks>1、continueAfterFailure=true，首 Task 后原候选失效；不能继续领取第二条，记录不被无效任务消耗。
- [ ] RED：第二个 Task 已启动并持有有效代理时，第一个启动失败；关领取但保留在途实际分配。业务普通失败仍按原 continueAfterFailure 策略。
- [ ] 在现有事务前静态检查原候选引用/端点，在实际 launch 再验证；凭据/探测失败发生于 Task 已创建之后时保留失败事实并正常清理，不删 Task。
- [ ] 将确定的资源失败写入既有 gate/selectionOutcome，复用 configurationError UI，不引入 noMatch/busy 假状态；源码形态如下，实际提交仍调用现有短事务/版本检查：
  ```python
  batch.claim_gate_state = "closed"
  batch.selection_outcome = {"status": "configurationError", "issues": issues}
  ```
- [ ] inputEnvironment 在已选择/预约的环境代次上冻结默认代理，标明 taskEnvironment 来源；显式批次 override 保持批次冻结。补改变环境代次与代理覆盖的两种断言。
- [ ] 运行对应三个目标文件和现有 scheduler/dispatcher 回归；检查旧快照恢复没有读取今天的成员，资源清理失败仍隔离。
- [ ] 更新 .ai/文档并提交 P2；如果现有公开 selectionOutcome DTO 确需扩展，先改其既有 schema，再运行 `npm run openapi:generate`，不维护第二套类型。

## P3 真实运行与发行候选验证

**Files:**
- Test: `apps/backend/tests/integration/test_project_batch_real_cloakbrowser.py`（正式 bootstrap、真实 worker、受控本地代理；供应商/凭据 fixture 明确标记）。
- Modify: `scripts/project-runtime-smoke.mjs`（复用人工屏障/公开命令，前提是受控代理 fixture 不触发真实外部副作用）。
- Evidence: `docs/project-management/implementation/pm9/resource-freeze-follow-through.json`, `coverage.json`, `verification.json`, `.ai/knowledge/2026-09-24-pm9-resource-freeze.md`。

**Interfaces:**
- Consumes: P1/P2 正式装配、批次 gate、可查询 Task/Run 结果。
- Produces: 相同候选源码的源运行/打包/三平台分层报告，不复制旧候选通过结论。

- [ ] 源真实 worker：A/B 本地代理记录实际到达请求；旧批次不使用后来加入 B，不使用 A 新端点；fresh batch 可使用明确新集合。捕获 selection IDs、Task/Run 和实际连接目标，日志不含认证头。
- [ ] 反例：所有原候选不可用，continueAfterFailure=true 仍停止新领取，不直连；旧命令重放不换代理；输入环境默认源在正确代次解析。
- [ ] 在打包受控 workspace 复验可完成部分。只有能安全预置合成投影/专用测试凭据时才运行对应完整代理链，并清理本次拥有的凭据；没有授权时明确保留该层，不用生产外部账号替代。
- [ ] 候选稳定后运行 backend 全量/ruff/mypy、前端相关/typecheck/lint/build、OpenAPI/script 检查、必要打包回归，再触发一次三平台最终候选。
- [ ] 逐条更新 ENV-05/XE-A20/XE-C02 的实际断言和缺口；完整条件未闭合保持partial/planned，不批量升级 verified。推送草稿 PR。

## 自审

快照/端点/凭据后竞争对应P1；旧快照与回放对应P1；关闭领取/在途事实/输入环境时间点对应P2；受控真实网络与打包外部限制对应P3。上述新增内部接口都在P1定义，P2/P3仅消费；不引入第二执行器或新数据库表。等待方案确认期间继续已授权 Profile 验收与现有 CI。
