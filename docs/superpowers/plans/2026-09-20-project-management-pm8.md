# PM8 执行卡：完整生命周期、跨重启核验与资源保护

- 日期：2026-09-20
- 工作区：`/Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm8`
- 分支：`codex/project-management-pm8`，起点 `3a57aede`（`codex/architecture-baseline`，含 PM0–PM7）
- 规格：`docs/project-management/design/pm8-lifecycle-recovery.md`（本卡唯一规格来源）
- 契约：`docs/project-management/implementation/api-contracts.md` §3.1/§3.5（已冻结，不新增未列路由）
- 主项目、PM3–PM7 工作区、旧项目只读；顶部导航、统一细网格表格、小圆角、原 gallery 主体布局不变

## 1. 现场核对（2026-09-20）

| 事实 | 证据 |
|---|---|
| PM7 已合并进 `codex/architecture-baseline`（`3a57aede`，快进内容一致）并推送 origin | `git diff codex/project-management-pm7 codex/architecture-baseline` 为空 |
| 生命周期状态与 `closing` 拒绝已存在 | `projects.lifecycle_state`；`project_runs/coordinator.py`、`scheduler.py`、`environments/service.py`、`project_automations/service.py`、`project_excel_inspections.py` 已按 `active/closing` 分流 |
| 影响确认存储已存在且通用 | `project_data_impacts`（project/action/target/digest/expected_revisions/facts_digest/report/expires_at） |
| 生命周期路由、自动化删除路由、资源引用路由**均未实现** | `projects.py` 只有 list/create/get/patch/open/overview/operations；`project_automations.py` 无 impact/delete |
| 退出阻断已有汇总点 | `SettingsRuntimeService.blockers()`；`scheduler.blockers() → project_batches_active`；`main/index.ts` before-quit 调 `studio.closeForQuit()` + `settings.shutdown()` |
| 全局资源删除只查运行时占用，不查项目静态引用 | `application/profiles/service.py:95`（仅 `profile_usage.guard`）；内核/代理/模型同理 |
| 启动核验部分存在 | `app.py`：`excel_exports.startup`、`excel_imports.startup`、`status_batch_coordinator.resume`、`runs.recover_interrupted()`、`project_run_scheduler.startup` |

## 2. 交付包

| 包 | 交付行为 | 主要文件（所有权） | 依赖 |
|---|---|---|---|
| **PM8-A1** 生命周期后端 | `lifecycle-impact`、`archive`、`restore`、`DELETE project` 四个路由；状态机推进与条件判定；影响确认复用；Operation 幂等与恢复 | `adapters/http/projects.py`、`project_schemas.py`、`application/projects/lifecycle.py`(新)、`infrastructure/database/project_lifecycle.py`(新)、`bootstrap/project_http_routes.py` | — |
| **PM8-A2** 自动化删除/解绑 + 环境删除影响对齐 | `GET automations/{id}/impact`、`DELETE automations/{id}`（unlink/deleteOwned）；环境删除影响按契约补齐 blockers/impacts | `adapters/http/project_automations.py`、`application/project_automations/service.py`、`application/environments/service.py` | A1 的 impact 复用 |
| **PM8-A3** 前端生命周期入口 | 目录/头部更多菜单（归档/恢复/永久删除）、`ProjectLifecycleDialog`、`ReferenceImpactPanel`、归档目录与只读态、清理残留展示 | `domains/projects/components/*`、`pages/ProjectDirectoryPage.tsx`、`api.ts`、`types.ts`、`app/navigation.ts` | A1 |
| **PM8-B1** 跨重启核验与残留 | 启动按持久事实核验 Run/文件/发送/生命周期命令；未知保持未知；残留写入 Operation 证据并可重试 | `application/projects/lifecycle.py`、`application/project_runs/*`、`bootstrap/app.py` | A1 |
| **PM8-B2** 残留可见入口 | 任务详情 `cleanup: CleanupSummary` 真实渲染；归档目录清理失败条目与重试入口 | `domains/project-runs/*`、`domains/projects/*` | B1 |
| **PM8-C1** 退出与工作区阻断 | `SettingsRuntimeService.blockers()` 汇总项目侧阻断；退出/切换工作区展示可处理对象 | `application/settings/runtime.py`、`infrastructure/database/settings_runtime.py`、`domains/settings/*`、`main/index.ts` | A1 |
| **PM8-C2** 全局资源引用保护 | Profile/内核/代理/池/模型删除同时检查项目静态引用与活动占用，返回引用清单；前端展示阻断 | `application/profiles/service.py`、`application/kernels/service.py`、`application/proxies/*`、`application/models/service.py`、对应 HTTP 层与前端设置页 | A1 |
| **PM8-F** 集成与阶段验收 | 端到端、截图对照、全量检查、覆盖表与账本、手测方案 | `scripts/qa-project-management-pm8.mjs`、`docs/project-management/implementation/pm8/*` | A/B/C |

## 3. 每包执行方式

1. 先补失败用例（`test_project_lifecycle.py` / `test_project_crash_recovery.py` / `test_project_resource_references.py` / 前端 `.test.tsx`），确认失败。
2. 最小实现，复用既有 impact/Operation/QuiesceGate 机制，不新建第二套框架。
3. 定向测试 → 规格审查 → 工程审查 → 修复复核。
4. 每包独立提交（显式路径，禁止 `git add -A`；`reference/*` 为只读符号链接，不入库）。

## 4. 验收命令

定向（每包）：

```sh
uv run --directory apps/backend pytest tests/integration/test_project_lifecycle.py -q
uv run --directory apps/backend pytest tests/contract/test_projects.py -q
npm --workspace @autoflow/desktop test -- ProjectLifecycleDialog
```

阶段全量（F）：

```sh
uv run --directory apps/backend pytest
uv run --directory apps/backend ruff check .
uv run --directory apps/backend mypy src
npm test
npm run openapi:check
npm run typecheck
npm run lint
npm run build
npm run test:scripts
npm run test:structure
node scripts/qa-project-management-pm8.mjs
git diff --check
```

## 5. 风险与处置

| 风险 | 处置 |
|---|---|
| 删除项目涉及十余张表，漏删导致 FK 残留 | 删除在同一事务按依赖顺序执行；集成测试断言逐表归零且 B 项目不受影响 |
| `closing` 过严会锁死正常收尾 | 收尾白名单显式列在规格 §2.1，并有反例测试（停止/人工/保存仍可用） |
| 归档前置条件依赖多个领域状态 | 条件判定集中在 `project_lifecycle.py` 一处，其它模块只提供只读事实，不复制判断 |
| 资源引用检查引入新的写路径 | 只在既有删除事务内加检查，复用既有 lease/占用查询，不新增后台任务 |
| OpenAPI 生成文件 | 必须 `npm run openapi:generate` 生成，禁止手改 |

## 6. 退出条件

1. PM8-A/B/C 全部真实接入页面，无假按钮。
2. 规格 §6 的自动用例通过；真实 Electron 端到端链通过并留截图。
3. 全量后端/前端检查、OpenAPI、类型、Lint、构建、脚本与结构检查通过。
4. 覆盖表 `PM-04`/`PM-05` 及其它 `complete_acceptance=PM8` 条目状态与证据更新；`.ai` 与会话记录同步。
5. 交付报告固定声明「管理侧通过，真实执行核心接入待验收」；未执行平台如实登记。

**PM8 完成后停在 PM8 验收点，不进入 PM9。**
