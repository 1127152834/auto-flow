# PM3 实施计划：自动化配置与首个真实参数批次

> **For Codex:** REQUIRED SUB-SKILL: Use Superpowers `executing-plans` to execute this plan task by task. Use `verification-before-completion` before each milestone completion claim.

**Goal:** 在项目中完成自动化配置、Studio 工作流关联、参数批次、真实 CloakBrowser 执行、运行记录、停止与故障恢复的前后端闭环。

**Architecture:** 选择性恢复归档的工作流执行核心并适配当前后端契约；Studio/core 唯一拥有 WorkflowDocument、PreparedContent、CoreRun 和 RunEvent，项目模块只拥有 Automation、Batch、Task 和 TaskInputSnapshot，并通过 application port 在同一数据库工作单元中原子创建 Task 与 queued CoreRun。Manager 与 Studio 共用工作流文档和 sidecar，不复制工作流、执行器或运行状态。

**Tech Stack:** Python 3.11、FastAPI、Pydantic、SQLAlchemy 2、Alembic、SQLite、CloakBrowser、React 19、TypeScript、TanStack Query、React Hook Form、Zod、shadcn/Radix、Tailwind、Vitest、pytest、Electron/CDP。

**Design:** [PM3 设计规格](../specs/2026-09-14-project-management-pm3-design.md)

## 0. 执行规则与当前基线

工作目录固定为 `/Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm3`，分支固定为 `codex/project-management-pm3`。计划起点为 `73a6c71`；开工前允许主线产生新提交，但不得把主目录未提交文件复制进来。需要同步主线时先记录差异，再选择性 cherry-pick 已提交变更。

当前唯一 Alembic head 已实测为 `0009_merge_project_data`。本计划新增迁移顺序固定为：

```text
0009_merge_project_data
  → 0010_workflow_runtime_contracts
  → pm03_project_automations
  → pm04_project_runs
```

若执行时已出现新的已提交迁移，停止创建上述文件，先由集成人重算顺序并更新本计划；不得改写已有 revision 或制造隐式双 head。

执行边界：

- 只恢复 `codex/studio-before-removal-20260913` 中本计划列出的工作流文件；不整包 checkout。
- 当前 Studio 前端源码优先，归档前端只作为真实 transport 和运行组件行为参考。
- PM3 不实现项目数据领取/写入、持久环境、人工处理、Sheets、统计和项目生命周期。
- 每个任务按 RED → GREEN → 定向回归 → 规格检查 → 工程检查 → 独立提交执行。
- 任何 E2E 脚本只写入带 PM3 专用标记的临时工作区，不修改用户业务目录。

---

## Milestone PM3-B0：补齐缺失视觉基准

### Task 1：生成自动化详情和启动弹窗图稿

**Files:**

- Create: `docs/prototype/project-management-pm3/automation-detail-overview.png`
- Create: `docs/prototype/project-management-pm3/automation-detail-inputs.png`
- Create: `docs/prototype/project-management-pm3/automation-detail-resources.png`
- Create: `docs/prototype/project-management-pm3/automation-detail-run-policy.png`
- Create: `docs/prototype/project-management-pm3/batch-start-dialog.png`
- Create: `docs/prototype/project-management-pm3/interactions.md`

- [x] **Step 1: 固定画板内容。** 只读参考主目录 `docs/references/project-management-prototypes-2026-09-13` 中的自动化列表、运行记录画板和现有顶部导航；在 `interactions.md` 列出四页签字段、启动弹窗、正常/校验/保存中/冲突/资源缺失状态。明确全局导航只使用顶部导航。参考目录当前未提交，不复制或修改其文件。
- [x] **Step 2: 使用 `imagegen` 生成五张 1440×1024 高保真 PNG。** 四张详情图共用相同内容框架，只切换活动页签；启动弹窗必须叠加在自动化详情上。不得输出 HTML 或加入侧栏。
- [x] **Step 3: 做原型自审。** 逐张核对暖灰背景、黏土棕、小圆角、细网格、字段完整性、按钮位置和 200% 缩放可实现性。`interactions.md` 记录原型与功能规格的每项对应关系。
- [x] **Step 4: 提交视觉基准。**

```bash
git add docs/prototype/project-management-pm3
git commit -m "docs(pm3): add automation detail and launch prototypes"
```

**Gate:** 用户确认图稿后才进入自动化详情页面实现；后端核心任务可以先行，但不得用未确认的页面布局代替图稿。

---

## Milestone PM3.0：恢复并改造真实执行核心

### Task 2：恢复工作流文档领域和持久化

**Files:**

- Restore and adapt: `apps/backend/src/autoflow/domain/workflows/models.py`
- Restore and adapt: `apps/backend/src/autoflow/domain/workflows/references.py`
- Restore and adapt: `apps/backend/src/autoflow/domain/workflows/validation.py`
- Restore and adapt: `apps/backend/src/autoflow/domain/workflows/control_values.py`
- Restore and adapt: `apps/backend/src/autoflow/domain/workflows/control.py`
- Restore and adapt: `apps/backend/src/autoflow/domain/workflows/catalog.py`
- Restore and adapt: `apps/backend/src/autoflow/domain/workflows/run_validation.py`
- Restore and adapt: `apps/backend/src/autoflow/application/workflows/service.py`
- Restore and adapt: `apps/backend/src/autoflow/infrastructure/database/workflows.py`
- Modify: `apps/backend/src/autoflow/infrastructure/database/models.py`
- Restore and adapt tests: `apps/backend/tests/fixtures/workflows.py`
- Restore and adapt tests: `apps/backend/tests/unit/test_workflow_drafts.py`
- Restore and adapt tests: `apps/backend/tests/unit/test_workflow_control.py`
- Restore and adapt tests: `apps/backend/tests/unit/test_workflow_run_validation.py`
- Restore and adapt tests: `apps/backend/tests/integration/test_workflow_repository.py`

- [ ] **Step 1: 恢复测试并确认 RED。** 从归档逐文件复制测试内容后，删除对旧 bootstrap 和旧错误 envelope 的假设，增加：文档 UUID、CAS、同内容不增修订、布尔 `true` 与数字 `1` 不等价、当前冻结节点目录外节点不可运行。

```bash
uv run --directory apps/backend pytest tests/unit/test_workflow_drafts.py tests/unit/test_workflow_control.py tests/unit/test_workflow_run_validation.py tests/integration/test_workflow_repository.py -q
```

预期：因为当前工作流领域和仓储不存在而失败。

- [ ] **Step 2: 从归档选择性恢复领域算法。** 保留纯校验、引用替换和控制流编译；把可执行节点目录限制为当前服务端明确支持的基础网页链。未知或仅前端展示的节点返回 `WORKFLOW_NOT_RUNNABLE`。
- [ ] **Step 3: 恢复文档服务和仓储。** 复用现有 `workflow_documents` 表；服务只接收当前文档和 expected revision，不写 Run。所有 JSON 编码使用 `allow_nan=False`，错误改为当前领域错误形状。
- [ ] **Step 4: 运行定向测试并修复。**

```bash
uv run --directory apps/backend pytest tests/unit/test_workflow_drafts.py tests/unit/test_workflow_control.py tests/unit/test_workflow_run_validation.py tests/integration/test_workflow_repository.py -q
uv run --directory apps/backend ruff check src/autoflow/domain/workflows src/autoflow/application/workflows/service.py src/autoflow/infrastructure/database/workflows.py
uv run --directory apps/backend mypy src/autoflow/domain/workflows src/autoflow/application/workflows/service.py
```

- [ ] **Step 5: 提交。**

```bash
git add apps/backend/src/autoflow/domain/workflows apps/backend/src/autoflow/application/workflows/service.py apps/backend/src/autoflow/infrastructure/database/workflows.py apps/backend/src/autoflow/infrastructure/database/models.py apps/backend/tests/fixtures/workflows.py apps/backend/tests/unit/test_workflow_drafts.py apps/backend/tests/unit/test_workflow_control.py apps/backend/tests/unit/test_workflow_run_validation.py apps/backend/tests/integration/test_workflow_repository.py
git commit -m "feat(workflows): restore document validation and persistence"
```

### Task 3：建立 PreparedContent 与 CoreRun v2 持久契约

**Files:**

- Create: `apps/backend/src/autoflow/domain/workflows/runtime.py`
- Create: `apps/backend/src/autoflow/application/workflows/runtime.py`
- Create: `apps/backend/src/autoflow/infrastructure/database/workflow_runtime.py`
- Create: `apps/backend/src/autoflow/infrastructure/database/workflow_runtime_models.py`
- Create: `apps/backend/src/autoflow/infrastructure/database/migrations/versions/0010_workflow_runtime_contracts.py`
- Modify: `apps/backend/src/autoflow/infrastructure/database/migrations/env.py`
- Create: `apps/backend/tests/unit/test_workflow_runtime.py`
- Create: `apps/backend/tests/integration/test_workflow_runtime_repository.py`
- Create: `apps/backend/tests/integration/test_workflow_runtime_migration.py`

- [ ] **Step 1: 写状态机和幂等 RED 测试。** 覆盖 `runRequestId` 唯一、PreparedContent 不可变、queued 创建、合法转换、终态不可逆、旧 `executionGeneration` 拒绝、RunEvent 单调 sequence 和重复事件不重复提交。
- [ ] **Step 2: 写迁移 RED 测试。** 从空库和包含 0005–0008 旧运行样例的数据库升级；验证旧表数据保留、PreparedContent 可回溯、项目/浏览器/代理/模型/PM2 表不变。
- [ ] **Step 3: 实现领域对象和 port。** `prepare_run(..., uow)` 只向调用者工作单元登记 queued CoreRun；`dispatch_run/query_run/cancel_run/force_stop` 使用明确 CAS。不得在 port 内提交。
- [ ] **Step 4: 实现迁移。** 新建 `workflow_prepared_contents`；为 `workflow_runs` 增加规范身份、状态、修订、执行代次、资源请求和 prepared content 引用。旧 payload 按确定映射回填；无法证明的旧活动运行统一迁成 `interrupted`，不自动重放。
- [ ] **Step 5: 实现仓储和数据库工作单元适配。** 同一 SQLAlchemy Session 可以由项目协调器传入；独立 Studio 启动则由 core application service 创建短工作单元。
- [ ] **Step 6: 验证。**

```bash
uv run --directory apps/backend pytest tests/unit/test_workflow_runtime.py tests/integration/test_workflow_runtime_repository.py tests/integration/test_workflow_runtime_migration.py -q
uv run --directory apps/backend alembic -c src/autoflow/infrastructure/database/alembic.ini heads
```

预期：唯一 head 为 `0010_workflow_runtime_contracts`。

- [ ] **Step 7: 提交。**

```bash
git add apps/backend/src/autoflow/domain/workflows/runtime.py apps/backend/src/autoflow/application/workflows/runtime.py apps/backend/src/autoflow/infrastructure/database/workflow_runtime.py apps/backend/src/autoflow/infrastructure/database/workflow_runtime_models.py apps/backend/src/autoflow/infrastructure/database/migrations apps/backend/tests/unit/test_workflow_runtime.py apps/backend/tests/integration/test_workflow_runtime_repository.py apps/backend/tests/integration/test_workflow_runtime_migration.py
git commit -m "feat(workflows): add immutable prepared content and core runs"
```

### Task 4：恢复 CloakBrowser worker 与真实执行

**Files:**

- Restore and adapt: `apps/backend/src/autoflow/application/workflows/browser_resources.py`
- Restore and adapt: `apps/backend/src/autoflow/application/workflows/execution.py`
- Create: `apps/backend/src/autoflow/application/workflows/dispatcher.py`
- Restore and adapt: `apps/backend/src/autoflow/bootstrap/workflow_worker.py`
- Restore and adapt: `apps/backend/src/autoflow/infrastructure/process/workflow_worker.py`
- Restore and adapt: `apps/backend/src/autoflow/providers/browser/workflow_executor.py`
- Restore and adapt: `apps/backend/src/autoflow/providers/browser/workflow_locator.py`
- Restore and adapt: `apps/backend/src/autoflow/providers/browser/workflow_worker.py`
- Restore and adapt: `apps/backend/tests/fixtures/workflow-page.html`
- Restore and adapt: `apps/backend/tests/fixtures/workflow_runs.py`
- Restore and adapt: `apps/backend/tests/unit/test_workflow_worker.py`
- Create: `apps/backend/tests/integration/test_workflow_dispatch.py`
- Modify: `apps/backend/tests/integration/test_sidecar_shutdown.py`

- [ ] **Step 1: 写 worker 生命周期 RED 测试。** 覆盖页面导航、输入、点击、文本读取、事件顺序、节点失败回收、普通停止后无新网页动作、worker 失联、sidecar 退出不遗留进程。
- [ ] **Step 2: 恢复进程协议和网页执行器。** 只恢复 PM3 fixture 使用的基础网页节点及其公共依赖；浏览器会话必须从 Profile、已安装 CloakBrowser 内核和代理服务解析，不能启动通用 Playwright 浏览器。
- [ ] **Step 3: 实现 dispatcher。** queued Run 通过 CAS 取得当前执行代次，创建 worker 后进入 running；容量固定 1。进程输出先验证 runId 和 generation，再持久化事件。
- [ ] **Step 4: 实现停止与清理。** 普通停止发取消并等待清理；强停撤销 generation、杀 worker、关闭 CloakBrowser，再写明确终态或 `reconciling`。清理失败不得显示成功。
- [ ] **Step 5: 验证。**

```bash
uv run --directory apps/backend pytest tests/unit/test_workflow_worker.py tests/integration/test_workflow_dispatch.py tests/integration/test_sidecar_shutdown.py -q
```

- [ ] **Step 6: 提交。**

```bash
git add apps/backend/src/autoflow/application/workflows apps/backend/src/autoflow/bootstrap/workflow_worker.py apps/backend/src/autoflow/infrastructure/process/workflow_worker.py apps/backend/src/autoflow/providers/browser apps/backend/tests/fixtures/workflow-page.html apps/backend/tests/fixtures/workflow_runs.py apps/backend/tests/unit/test_workflow_worker.py apps/backend/tests/integration/test_workflow_dispatch.py apps/backend/tests/integration/test_sidecar_shutdown.py
git commit -m "feat(workflows): execute core runs through CloakBrowser workers"
```

### Task 5：接入 core HTTP、SSE、OpenAPI 和 Studio transport

**Files:**

- Restore and adapt: `apps/backend/src/autoflow/adapters/http/workflow_schemas.py`
- Restore and adapt: `apps/backend/src/autoflow/adapters/http/workflows.py`
- Restore and adapt: `apps/backend/src/autoflow/adapters/http/workflow_run_schemas.py`
- Restore and adapt: `apps/backend/src/autoflow/adapters/http/workflow_runs.py`
- Restore and adapt: `apps/backend/src/autoflow/adapters/events/workflows.py`
- Modify: `apps/backend/src/autoflow/bootstrap/http_routes.py`
- Modify: `apps/backend/src/autoflow/bootstrap/app.py`
- Modify: `apps/backend/src/autoflow/adapters/http/workflow_studio_openapi.py`
- Modify: `apps/desktop/src/renderer/domains/workflows/api.ts`
- Modify: `apps/desktop/src/renderer/domains/workflows/events.ts`
- Create: `apps/desktop/src/renderer/domains/workflows/runtime-api.ts`
- Create: `apps/desktop/src/renderer/domains/workflows/runtime-api.test.ts`
- Restore and adapt: `apps/backend/tests/contract/test_workflows.py`
- Restore and adapt: `apps/backend/tests/contract/test_workflow_runs.py`
- Create: `apps/backend/tests/contract/test_workflow_events.py`

- [ ] **Step 1: 写 contract RED 测试。** 验证认证、错误 envelope、camelCase、服务端读取文档、Run 快照、事件补读、SSE 断线续订、停止 202 和不存在资源 404。
- [ ] **Step 2: 安装真实 router。** `workflow_studio_openapi.py` 不再单独冒充业务接口；schema 由真实 handler 引用。Studio 直接运行只允许传 `workflowId/expectedRevision/profileId/parameters`，不允许以请求体替换服务端文档。
- [ ] **Step 3: 改造当前 Studio transport。** 保持现有 API facade 和事件 Store，替换 Mock workflow/run 路径；结果不明保留当前画布和运行态，通过原 runId 查询。
- [ ] **Step 4: 生成客户端类型。**

```bash
npm run openapi:generate
npm run openapi:check
```

- [ ] **Step 5: 验证 core。**

```bash
uv run --directory apps/backend pytest tests/contract/test_workflows.py tests/contract/test_workflow_runs.py tests/contract/test_workflow_events.py -q
npm --workspace @autoflow/desktop test -- src/renderer/domains/workflows/runtime-api.test.ts
npm run typecheck
```

- [ ] **Step 6: 提交。**

```bash
git add apps/backend/src/autoflow/adapters/http/workflow_schemas.py apps/backend/src/autoflow/adapters/http/workflows.py apps/backend/src/autoflow/adapters/http/workflow_run_schemas.py apps/backend/src/autoflow/adapters/http/workflow_runs.py apps/backend/src/autoflow/adapters/http/workflow_studio_openapi.py apps/backend/src/autoflow/adapters/events/workflows.py apps/backend/src/autoflow/bootstrap/http_routes.py apps/backend/src/autoflow/bootstrap/app.py apps/desktop/src/renderer/domains/workflows/api.ts apps/desktop/src/renderer/domains/workflows/events.ts apps/desktop/src/renderer/domains/workflows/runtime-api.ts apps/desktop/src/renderer/domains/workflows/runtime-api.test.ts apps/desktop/src/renderer/shared/api/generated.ts apps/backend/tests/contract/test_workflows.py apps/backend/tests/contract/test_workflow_runs.py apps/backend/tests/contract/test_workflow_events.py
git commit -m "feat(studio): connect workflow documents and real run events"
```

### Task 6：PM3.0 真实最小链验收

**Files:**

- Create: `apps/desktop/tests/fixtures/project-management/index.html`
- Create: `scripts/qa-workflow-runtime-pm3.mjs`
- Create: `scripts/qa-workflow-runtime-pm3.test.mjs`
- Create: `docs/project-management/implementation/pm3/core-verification.json`

- [ ] **Step 1: 创建 fixture。** 页面提供文本输入、提交按钮、提交计数、延时按钮、结果区和 `localStorage` 登录态，所有状态可从页面 DOM 读取。
- [ ] **Step 2: 写 QA 脚本 RED。** 启动隔离 sidecar 与 Electron，使用 UI 在 Studio 保存基础链并运行；断言输入值、一次提交、读取结果、Run 终态、日志序号和 CloakBrowser 清理。
- [ ] **Step 3: 修复真实集成问题，直到脚本通过。** 不允许在 QA 脚本中直接伪造成功事件或调用 worker 私有函数。
- [ ] **Step 4: 运行 PM3.0 门槛。**

```bash
node --test scripts/qa-workflow-runtime-pm3.test.mjs
node scripts/qa-workflow-runtime-pm3.mjs
uv run --directory apps/backend pytest tests/unit/test_workflow_*.py tests/integration/test_workflow_*.py tests/contract/test_workflow*.py -q
npm run openapi:check
npm run typecheck
npm run lint
npm run build
git diff --check
```

- [ ] **Step 5: 写入实际证据并提交。** `core-verification.json` 只记录实际运行的平台、命令、提交、fixture 结果和未执行项。

```bash
git add apps/desktop/tests/fixtures/project-management scripts/qa-workflow-runtime-pm3.mjs scripts/qa-workflow-runtime-pm3.test.mjs docs/project-management/implementation/pm3/core-verification.json
git commit -m "test(pm3): verify the real workflow execution core"
```

**PM3.0 Exit:** 工作流保存和最小网页链真实通过；停止后无后续网页动作；进程重启不自动重放；CoreRun 状态、事件和浏览器清理可查询。

---

## Milestone PM3.1：项目自动化管理

### Task 7：实现 Automation 领域、迁移和仓储

**Files:**

- Create: `apps/backend/src/autoflow/domain/project_automations/models.py`
- Create: `apps/backend/src/autoflow/domain/project_automations/rules.py`
- Create: `apps/backend/src/autoflow/domain/project_automations/ports.py`
- Create: `apps/backend/src/autoflow/application/project_automations/service.py`
- Create: `apps/backend/src/autoflow/infrastructure/database/project_automation_models.py`
- Create: `apps/backend/src/autoflow/infrastructure/database/project_automations.py`
- Create: `apps/backend/src/autoflow/infrastructure/database/migrations/versions/pm03_project_automations.py`
- Modify: `apps/backend/src/autoflow/infrastructure/database/migrations/env.py`
- Create: `apps/backend/tests/unit/test_project_automation_rules.py`
- Create: `apps/backend/tests/integration/test_project_automation_repository.py`
- Create: `apps/backend/tests/integration/test_project_automation_migration.py`

- [ ] **Step 1: 写 RED 测试。** 覆盖 Unicode 名称、稳定 parameter/input ID、一个 workflowId 只能绑定一个 Automation、CAS、同内容不推进修订和归档只读。删除及影响查询留到 PM8。
- [ ] **Step 2: 实现模型和规则。** 严格区分省略/null/空字符串、字符串/数字/布尔参数。保存允许未来 inputPlan；validation projection 把非空 inputPlan 标记为 PM4 blocker。
- [ ] **Step 3: 实现仓储和迁移。** `project_automations` 保存聚合 JSON 和可索引摘要；workflow 外键使用 RESTRICT。创建、更新和 ProjectOperation 在同一短事务提交。
- [ ] **Step 4: 验证唯一 head。**

```bash
uv run --directory apps/backend pytest tests/unit/test_project_automation_rules.py tests/integration/test_project_automation_repository.py tests/integration/test_project_automation_migration.py -q
uv run --directory apps/backend alembic -c src/autoflow/infrastructure/database/alembic.ini heads
```

预期：唯一 head 为 `pm03_project_automations`。

- [ ] **Step 5: 提交。**

```bash
git add apps/backend/src/autoflow/domain/project_automations apps/backend/src/autoflow/application/project_automations apps/backend/src/autoflow/infrastructure/database/project_automation_models.py apps/backend/src/autoflow/infrastructure/database/project_automations.py apps/backend/src/autoflow/infrastructure/database/migrations/env.py apps/backend/src/autoflow/infrastructure/database/migrations/versions/pm03_project_automations.py apps/backend/tests/unit/test_project_automation_rules.py apps/backend/tests/integration/test_project_automation_repository.py apps/backend/tests/integration/test_project_automation_migration.py
git commit -m "feat(projects): persist project automation configurations"
```

### Task 8：实现 Automation HTTP 与生成类型

**Files:**

- Create: `apps/backend/src/autoflow/adapters/http/project_automation_schemas.py`
- Create: `apps/backend/src/autoflow/adapters/http/project_automations.py`
- Modify: `apps/backend/src/autoflow/bootstrap/project_http_routes.py`
- Modify: `apps/backend/src/autoflow/bootstrap/app.py`
- Modify: `apps/backend/src/autoflow/application/projects/service.py`
- Create: `apps/backend/tests/contract/test_project_automations.py`
- Modify: `apps/backend/tests/contract/test_schema_export.py`
- Modify: `apps/desktop/src/renderer/shared/api/generated.ts`

- [ ] **Step 1: 写 HTTP RED 测试。** 覆盖目录搜索/排序/分页、详情、创建、聚合更新、validation、错误 envelope、项目归属和幂等恢复；验证 PM3 OpenAPI 没有提前发布删除接口。
- [ ] **Step 2: 实现真实 handler。** 路由只包含已实现的目录、详情、创建、更新和 validation；所有父路径重新校验项目。更新使用 `expectedManagementRevision`，持久命令使用 `Idempotency-Key`。
- [ ] **Step 3: 更新 capability。** `automations` 暂保持 `notImplemented`，直到 PM3.1 前端和 PM3.2 真实启动均完成；后端额外返回内部装配状态供最终门槛切换。
- [ ] **Step 4: 生成类型并验证。**

```bash
uv run --directory apps/backend pytest tests/contract/test_project_automations.py tests/contract/test_schema_export.py -q
npm run openapi:generate
npm run openapi:check
```

- [ ] **Step 5: 提交。**

```bash
git add apps/backend/src/autoflow/adapters/http/project_automation_schemas.py apps/backend/src/autoflow/adapters/http/project_automations.py apps/backend/src/autoflow/bootstrap apps/backend/src/autoflow/application/projects/service.py apps/backend/tests/contract/test_project_automations.py apps/backend/tests/contract/test_schema_export.py apps/desktop/src/renderer/shared/api/generated.ts
git commit -m "feat(projects): expose project automation contracts"
```

### Task 9：先构建自动化领域组件

**Files:**

- Create: `apps/desktop/src/renderer/domains/project-automations/types.ts`
- Create: `apps/desktop/src/renderer/domains/project-automations/form-schema.ts`
- Create: `apps/desktop/src/renderer/domains/project-automations/form-schema.test.ts`
- Create: `apps/desktop/src/renderer/domains/project-automations/api.ts`
- Create: `apps/desktop/src/renderer/domains/project-automations/api.test.ts`
- Create: `apps/desktop/src/renderer/domains/project-automations/components/AutomationDirectory.tsx`
- Create: `apps/desktop/src/renderer/domains/project-automations/components/AutomationDirectory.test.tsx`
- Create: `apps/desktop/src/renderer/domains/project-automations/components/AutomationEditor.tsx`
- Create: `apps/desktop/src/renderer/domains/project-automations/components/AutomationEditor.test.tsx`
- Create: `apps/desktop/src/renderer/domains/project-automations/components/AutomationValidation.tsx`
- Create: `apps/desktop/src/renderer/domains/project-automations/components/ParameterEditor.tsx`
- Create: `apps/desktop/src/renderer/domains/project-automations/components/InputPlanEditor.tsx`
- Create: `apps/desktop/src/renderer/domains/project-automations/components/ResourcePolicyEditor.tsx`
- Create: `apps/desktop/src/renderer/domains/project-automations/components/RunPolicyEditor.tsx`

- [ ] **Step 1: 写组件 RED 测试。** 覆盖 gallery 的自动化目录状态、更多菜单、四页签单一草稿、错误页签计数、未保存保护、CAS 冲突、资源缺失和 PM4 输入 blocker；更多菜单不得出现尚未交付的删除动作。
- [ ] **Step 2: 实现 API 恢复逻辑。** 创建/保存/删除结果不明时先按原 Idempotency-Key 查询 Operation；旧工作区或实例响应不能关闭当前编辑器。
- [ ] **Step 3: 实现组件。** 复用 shared controls、细网格和小圆角；组件只接收数据与回调，不自行读取全局 runtime。四页签共享 React Hook Form，参数 ID 和输入 ID 不随重命名变化。
- [ ] **Step 4: 验证。**

```bash
npm --workspace @autoflow/desktop test -- src/renderer/domains/project-automations
npm run typecheck
npm run lint
```

- [ ] **Step 5: 提交。**

```bash
git add apps/desktop/src/renderer/domains/project-automations
git commit -m "feat(projects): build automation management components"
```

### Task 10：组装自动化页面与 Studio 项目上下文

**Files:**

- Create: `apps/desktop/src/renderer/domains/project-automations/pages/AutomationDirectoryPage.tsx`
- Create: `apps/desktop/src/renderer/domains/project-automations/pages/AutomationDirectoryPage.test.tsx`
- Create: `apps/desktop/src/renderer/domains/project-automations/pages/AutomationDetailPage.tsx`
- Create: `apps/desktop/src/renderer/domains/project-automations/pages/AutomationDetailPage.test.tsx`
- Create: `apps/desktop/src/renderer/domains/project-automations/hooks.ts`
- Create: `apps/desktop/src/renderer/domains/project-automations/index.ts`
- Modify: `apps/desktop/src/renderer/domains/projects/pages/ProjectsWorkspace.tsx`
- Modify: `apps/desktop/src/renderer/domains/projects/components/ProjectCapabilityState.tsx`
- Modify: `apps/desktop/src/renderer/app/App.projects.test.tsx`
- Modify: `apps/desktop/src/shared/automation-studio.ts`
- Modify: `apps/desktop/src/preload/index.ts`
- Modify: `apps/desktop/src/preload/index.test.ts`
- Modify: `apps/desktop/src/main/ipc/automation-studio.ts`
- Modify: `apps/desktop/src/main/ipc/automation-studio.test.ts`

- [ ] **Step 1: 写页面和 IPC RED 测试。** 覆盖 `#/projects/{projectId}/automations` 和详情路由、返回恢复、创建后进入详情、编辑后页头更新、归档只读、工作区切换清理，以及 `OpenStudioRequest` 作用域验证。
- [ ] **Step 2: 扩展 Studio bridge。** Manager 传 `workflowId/projectContext`；主进程验证主 frame、当前工作区和已存在 workflowId，并在 Studio URL/query 中只传不敏感身份。Studio 恢复项目返回入口。
- [ ] **Step 3: 组装真实页面。** 严格对照自动化 gallery 和 PM3-B0；顶部导航替代原型侧栏，主体结构不自行重排。页面通过 TanStack Query 使用真实后端。
- [ ] **Step 4: 验证。**

```bash
npm --workspace @autoflow/desktop test -- src/renderer/domains/project-automations src/renderer/app/App.projects.test.tsx src/main/ipc/automation-studio.test.ts src/preload/index.test.ts
npm run typecheck
npm run lint
```

- [ ] **Step 5: 提交。**

```bash
git add apps/desktop/src/renderer/domains/project-automations apps/desktop/src/renderer/domains/projects apps/desktop/src/renderer/app/App.projects.test.tsx apps/desktop/src/shared/automation-studio.ts apps/desktop/src/preload apps/desktop/src/main/ipc/automation-studio.ts apps/desktop/src/main/ipc/automation-studio.test.ts
git commit -m "feat(projects): add automation pages and Studio context"
```

**PM3.1 Exit:** 自动化目录、四页签配置和 Studio 关联真实可用；全部适用页面状态对照原型；自动化 capability 仍不宣称可运行。

---

## Milestone PM3.2：参数批次与原子启动

### Task 11：实现 Batch、Task 和快照持久化

**Files:**

- Create: `apps/backend/src/autoflow/domain/project_runs/models.py`
- Create: `apps/backend/src/autoflow/domain/project_runs/rules.py`
- Create: `apps/backend/src/autoflow/domain/project_runs/ports.py`
- Create: `apps/backend/src/autoflow/application/project_runs/coordinator.py`
- Create: `apps/backend/src/autoflow/application/project_runs/projections.py`
- Create: `apps/backend/src/autoflow/infrastructure/database/project_run_models.py`
- Create: `apps/backend/src/autoflow/infrastructure/database/project_runs.py`
- Create: `apps/backend/src/autoflow/infrastructure/database/migrations/versions/pm04_project_runs.py`
- Modify: `apps/backend/src/autoflow/infrastructure/database/migrations/env.py`
- Create: `apps/backend/tests/unit/test_project_run_rules.py`
- Create: `apps/backend/tests/integration/test_project_run_start.py`
- Create: `apps/backend/tests/integration/test_project_run_migration.py`

- [ ] **Step 1: 写原子性 RED 测试。** 覆盖参数严格类型、最终 `maxTasks` 1–100、并发固定 1、同键重发、异载荷冲突、Task/Snapshot/queued CoreRun/Operation 同时存在、任一步故障全部回滚。
- [ ] **Step 2: 实现项目运行对象。** PM3 `inputs=[]`；每个 Task 参数独立冻结。Batch 状态使用 PM0 状态集合，Task 只投影 CoreRun。
- [ ] **Step 3: 实现共享 UoW。** `ProjectRunCoordinator` 打开一次 Session，调用 Automation repository 和 `CoreRunPort.prepare_run(..., uow)`；port 不 commit。提交后 dispatcher 才运行。
- [ ] **Step 4: 实现迁移和仓储。** 新表保存 Batch、Task、TaskInputSnapshot；外键连接 Automation 和 CoreRun，删除策略为 RESTRICT。迁移升级不改变 PM1/PM2 事实。
- [ ] **Step 5: 验证。**

```bash
uv run --directory apps/backend pytest tests/unit/test_project_run_rules.py tests/integration/test_project_run_start.py tests/integration/test_project_run_migration.py -q
uv run --directory apps/backend alembic -c src/autoflow/infrastructure/database/alembic.ini heads
```

预期：唯一 head 为 `pm04_project_runs`。

- [ ] **Step 6: 提交。**

```bash
git add apps/backend/src/autoflow/domain/project_runs apps/backend/src/autoflow/application/project_runs apps/backend/src/autoflow/infrastructure/database/project_run_models.py apps/backend/src/autoflow/infrastructure/database/project_runs.py apps/backend/src/autoflow/infrastructure/database/migrations/env.py apps/backend/src/autoflow/infrastructure/database/migrations/versions/pm04_project_runs.py apps/backend/tests/unit/test_project_run_rules.py apps/backend/tests/integration/test_project_run_start.py apps/backend/tests/integration/test_project_run_migration.py
git commit -m "feat(projects): create parameter batches atomically"
```

### Task 12：实现批次 HTTP、调度和 Operation 恢复

**Files:**

- Create: `apps/backend/src/autoflow/adapters/http/project_run_schemas.py`
- Create: `apps/backend/src/autoflow/adapters/http/project_runs.py`
- Modify: `apps/backend/src/autoflow/bootstrap/project_http_routes.py`
- Modify: `apps/backend/src/autoflow/bootstrap/app.py`
- Modify: `apps/backend/src/autoflow/application/settings/runtime.py`
- Create: `apps/backend/tests/contract/test_project_runs.py`
- Create: `apps/backend/tests/integration/test_project_run_dispatch.py`
- Create: `apps/backend/tests/integration/test_project_crash_recovery.py`
- Modify: `apps/backend/tests/contract/test_projects.py`
- Modify: `apps/desktop/src/renderer/shared/api/generated.ts`

- [ ] **Step 1: 写 HTTP 和调度 RED 测试。** 覆盖启动 202、Operation 查询、响应丢失、串行多 Task、派发失败、资源缺失、capacity 429、项目 closing/归档、两个工作区隔离。
- [ ] **Step 2: 实现路由与调度。** 首次接受返回 Operation；后台协调器按 Batch 顺序派发 queued Task，失败按 `continueAfterFailure` 决定是否继续。当前 PM3 不执行数据领取。
- [ ] **Step 3: 接入 QuiesceGate。** queued/running/stopping/reconciling Run 参与退出和工作区切换 blocker；服务重启先查询事实，不重放 running 网页动作。
- [ ] **Step 4: 生成类型并验证。**

```bash
uv run --directory apps/backend pytest tests/contract/test_project_runs.py tests/integration/test_project_run_dispatch.py tests/integration/test_project_crash_recovery.py tests/contract/test_projects.py -q
npm run openapi:generate
npm run openapi:check
```

- [ ] **Step 5: 提交。**

```bash
git add apps/backend/src/autoflow/adapters/http/project_run_schemas.py apps/backend/src/autoflow/adapters/http/project_runs.py apps/backend/src/autoflow/bootstrap apps/backend/src/autoflow/application/settings/runtime.py apps/backend/tests/contract/test_project_runs.py apps/backend/tests/integration/test_project_run_dispatch.py apps/backend/tests/integration/test_project_crash_recovery.py apps/backend/tests/contract/test_projects.py apps/desktop/src/renderer/shared/api/generated.ts
git commit -m "feat(projects): dispatch and recover parameter batches"
```

### Task 13：构建启动弹窗和批次状态组件

**Files:**

- Create: `apps/desktop/src/renderer/domains/project-runs/types.ts`
- Create: `apps/desktop/src/renderer/domains/project-runs/api.ts`
- Create: `apps/desktop/src/renderer/domains/project-runs/api.test.ts`
- Create: `apps/desktop/src/renderer/domains/project-runs/start-schema.ts`
- Create: `apps/desktop/src/renderer/domains/project-runs/start-schema.test.ts`
- Create: `apps/desktop/src/renderer/domains/project-runs/components/BatchStartDialog.tsx`
- Create: `apps/desktop/src/renderer/domains/project-runs/components/BatchStartDialog.test.tsx`
- Create: `apps/desktop/src/renderer/domains/project-runs/components/BatchStatus.tsx`
- Create: `apps/desktop/src/renderer/domains/project-runs/hooks.ts`

- [ ] **Step 1: 写组件 RED 测试。** 覆盖参数必填/类型、false/0/空字符串、资源 override、任务数、双击、保存中禁用、422 定位、409 保留输入、504/网络丢失查询原 Operation。
- [ ] **Step 2: 实现 API 与表单。** 只有点击“开始运行”才创建批次；关闭弹窗保留当前会话草稿，工作区切换清除。旧实例响应不能 Toast 当前项目。
- [ ] **Step 3: 对照 B0 实现组件。** 使用 shared Dialog/Form/Select/Input，默认焦点在首个参数或开始按钮；提交期间禁止 Escape 和遮罩关闭。
- [ ] **Step 4: 验证并提交。**

```bash
npm --workspace @autoflow/desktop test -- src/renderer/domains/project-runs
npm run typecheck
npm run lint
git add apps/desktop/src/renderer/domains/project-runs
git commit -m "feat(projects): add recoverable batch launch controls"
```

**PM3.2 Exit:** UI 启动产生真实 Batch/Task/CoreRun；双击和响应丢失不重复；多任务按容量串行；事务失败无孤立对象。

---

## Milestone PM3.3：运行记录、停止和恢复

### Task 14：实现项目运行查询投影和停止命令

**Files:**

- Modify: `apps/backend/src/autoflow/application/project_runs/projections.py`
- Modify: `apps/backend/src/autoflow/application/project_runs/coordinator.py`
- Modify: `apps/backend/src/autoflow/infrastructure/database/project_runs.py`
- Modify: `apps/backend/src/autoflow/adapters/http/project_runs.py`
- Modify: `apps/backend/src/autoflow/adapters/http/project_run_schemas.py`
- Create: `apps/backend/tests/integration/test_project_run_queries.py`
- Create: `apps/backend/tests/integration/test_project_run_stop.py`
- Modify: `apps/backend/tests/contract/test_project_runs.py`

- [ ] **Step 1: 写查询/停止 RED 测试。** 覆盖 Batch 目录、Task 目录、详情、节点 attempts、日志补读、artifact 元数据、普通停止、强停、终态竞争和项目归属。
- [ ] **Step 2: 实现查询投影。** 每次读取由 Task identity 联结 CoreRun；不复制或重算 core 终态。日志缺口从持久事件补读，不能用当前快照跳过。
- [ ] **Step 3: 实现停止。** start/stop/force-stop Operation 各自幂等；停止接受和最终停止分开。关闭未派发 Task 后扇出 CoreRun cancel，聚合 counts 和 Batch 状态。
- [ ] **Step 4: 验证并提交。**

```bash
uv run --directory apps/backend pytest tests/integration/test_project_run_queries.py tests/integration/test_project_run_stop.py tests/contract/test_project_runs.py -q
git add apps/backend/src/autoflow/application/project_runs apps/backend/src/autoflow/infrastructure/database/project_runs.py apps/backend/src/autoflow/adapters/http/project_runs.py apps/backend/src/autoflow/adapters/http/project_run_schemas.py apps/backend/tests/integration/test_project_run_queries.py apps/backend/tests/integration/test_project_run_stop.py apps/backend/tests/contract/test_project_runs.py
git commit -m "feat(projects): query and stop project runs"
```

### Task 15：先构建运行领域组件

**Files:**

- Create: `apps/desktop/src/renderer/domains/project-runs/events.ts`
- Create: `apps/desktop/src/renderer/domains/project-runs/events.test.ts`
- Create: `apps/desktop/src/renderer/domains/project-runs/components/BatchDirectory.tsx`
- Create: `apps/desktop/src/renderer/domains/project-runs/components/BatchDirectory.test.tsx`
- Create: `apps/desktop/src/renderer/domains/project-runs/components/BatchDetail.tsx`
- Create: `apps/desktop/src/renderer/domains/project-runs/components/TaskDirectory.tsx`
- Create: `apps/desktop/src/renderer/domains/project-runs/components/TaskDetail.tsx`
- Create: `apps/desktop/src/renderer/domains/project-runs/components/TaskLog.tsx`
- Create: `apps/desktop/src/renderer/domains/project-runs/components/TaskEvidence.tsx`
- Create: `apps/desktop/src/renderer/domains/project-runs/components/StopBatchDialog.tsx`
- Create: `apps/desktop/src/renderer/domains/project-runs/components/ForceStopDialog.tsx`
- Create: `apps/desktop/src/renderer/domains/project-runs/components/RunComponents.test.tsx`

- [ ] **Step 1: 写 gallery 行为 RED 测试。** 覆盖运行列表、任务列表、批次详情、日志、输入输出、异常证据、筛选、空/加载/刷新失败、停止与强停确认、运行中日志。
- [ ] **Step 2: 实现事件归并。** 先读取快照再订阅；按 sequence 去重，缺口暂停应用并补读，终态事件不被迟到运行中事件覆盖。卸载和工作区切换关闭订阅。
- [ ] **Step 3: 实现组件。** 使用全局细网格、小圆角和现有反馈组件；日志长文本内部滚动。错误、停止中、结果不明留在页面状态区。
- [ ] **Step 4: 验证并提交。**

```bash
npm --workspace @autoflow/desktop test -- src/renderer/domains/project-runs
npm run typecheck
npm run lint
git add apps/desktop/src/renderer/domains/project-runs
git commit -m "feat(projects): build run history and stop components"
```

### Task 16：组装运行页面和完整项目导航

**Files:**

- Create: `apps/desktop/src/renderer/domains/project-runs/pages/RunDirectoryPage.tsx`
- Create: `apps/desktop/src/renderer/domains/project-runs/pages/RunDirectoryPage.test.tsx`
- Create: `apps/desktop/src/renderer/domains/project-runs/pages/BatchDetailPage.tsx`
- Create: `apps/desktop/src/renderer/domains/project-runs/pages/TaskDetailPage.tsx`
- Create: `apps/desktop/src/renderer/domains/project-runs/pages/RunPages.test.tsx`
- Create: `apps/desktop/src/renderer/domains/project-runs/index.ts`
- Modify: `apps/desktop/src/renderer/domains/projects/pages/ProjectsWorkspace.tsx`
- Modify: `apps/desktop/src/renderer/domains/projects/components/ProjectCapabilityState.tsx`
- Modify: `apps/desktop/src/renderer/app/App.projects.test.tsx`
- Modify: `apps/backend/src/autoflow/application/projects/service.py`

- [ ] **Step 1: 写路由 RED 测试。** 覆盖运行目录、批次、任务、日志 tab、返回目录恢复、非法身份、直接路由、工作区切换和服务重连。
- [ ] **Step 2: 组装真实页面。** 对照 `latest/03-runs/001–017`，只替换全局导航。启动入口放在自动化详情；运行记录页不放假创建按钮。
- [ ] **Step 3: 打开 capability。** 只有后端 core、Automation、Batch/Task 和页面全部装配后，项目 overview 的 `automations/runs` 返回 `available`；其余能力保持原状态。
- [ ] **Step 4: 验证并提交。**

```bash
npm --workspace @autoflow/desktop test -- src/renderer/domains/project-runs src/renderer/domains/project-automations src/renderer/app/App.projects.test.tsx
npm run openapi:check
npm run typecheck
npm run lint
git add apps/desktop/src/renderer/domains/project-runs apps/desktop/src/renderer/domains/projects apps/desktop/src/renderer/app/App.projects.test.tsx apps/backend/src/autoflow/application/projects/service.py
git commit -m "feat(projects): connect automation and run pages"
```

**PM3.3 Exit:** 用户可以从自动化启动并在项目运行页看到真实 Batch/Task/Run；普通停止、强停、日志补读、错误证据、重连和重启均有明确结果。

---

## Milestone PM3.4：端到端、视觉和交付

### Task 17：建立可重复的 PM3 Electron QA 工具

**Files:**

- Create: `scripts/qa-project-management-pm3.mjs`
- Create: `scripts/qa-project-management-pm3.test.mjs`
- Create: `scripts/qa-project-management-pm3-faults.mjs`
- Create: `docs/project-management/implementation/pm3/manual-test.md`

- [ ] **Step 1: 写脚本单元测试。** 验证工作区 marker、端口分配、fixture 地址、故障注入只作用于测试实例、截图命名和清理保护。
- [ ] **Step 2: 实现 `--manual` 和自动模式。** 自动模式完成 UI 主链；手动模式保留应用并输出测试项目、工作区、fixture URL、截图目录和故障命令。
- [ ] **Step 3: 实现隔离故障。** 支持一次性响应丢失、真实竞争更新、worker 中断、sidecar 重启和应用重启。故障脚本不得直接改业务结果，只改变网络/进程时序。
- [ ] **Step 4: 编写逐步手测。** 至少包含：创建自动化、四页签保存、Studio 关联、一次参数运行、多任务串行、双击、响应丢失、修订冲突、停止、强停、服务重启、应用重启、双工作区、归档只读、键盘和 200% 缩放。
- [ ] **Step 5: 验证。**

```bash
node --test scripts/qa-project-management-pm3.test.mjs
```

- [ ] **Step 6: 提交 QA 工具和手测说明。**

```bash
git add scripts/qa-project-management-pm3.mjs scripts/qa-project-management-pm3.test.mjs scripts/qa-project-management-pm3-faults.mjs docs/project-management/implementation/pm3/manual-test.md
git commit -m "test(pm3): add repeatable desktop acceptance tools"
```

### Task 18：运行真实 E2E 与截图对照

**Files:**

- Create at runtime: `docs/project-management/implementation/pm3/runs/run-${runId}/report.json`
- Create at runtime: `docs/project-management/implementation/pm3/runs/run-${runId}/*.png`
- Create: `docs/project-management/implementation/pm3/visual-review.md`

- [ ] **Step 1: 正常链。** UI 创建项目和自动化，在 Studio 保存基础网页链，启动参数批次；核对 fixture 提交计数、参数、结果、Task、Run、日志和 artifact。
- [ ] **Step 2: 状态与恢复链。** 执行双击、响应丢失、自动化 CAS 冲突、普通停止、强停、worker 中断、sidecar 重启、应用重启和双工作区隔离。
- [ ] **Step 3: 截图。** 保存自动化目录、四页签、启动弹窗、运行目录、批次详情、任务日志、异常证据、停止确认、冲突、结果不明，以及适用页面 100%/200% 图。
- [ ] **Step 4: 逐图审查。** 每张实图与对应 gallery/B0 并排记录；逐项检查顶部导航、页面层级、主操作、表格密度、圆角、颜色、状态和滚动。每个适用画面单独达到 85 分且强制结构全部满足。
- [ ] **Step 5: 保存实际结果。** 未运行的 Windows、其他架构和打包项目标记 `notRun`，不能写 passed。

```bash
node scripts/qa-project-management-pm3.mjs
```

- [ ] **Step 6: 提交机器证据。**

```bash
git add docs/project-management/implementation/pm3/runs docs/project-management/implementation/pm3/visual-review.md
git commit -m "test(pm3): record desktop and visual evidence"
```

### Task 19：全量工程验证、文档和最终提交

**Files:**

- Modify: `docs/project-management/implementation/current-baseline.md`
- Modify: `docs/project-management/implementation/coverage.md`
- Modify: `docs/project-management/implementation/coverage.json`
- Modify: `docs/project-management/implementation/execution-ledger.md`
- Create: `docs/project-management/implementation/pm3/verification.json`
- Create: `.ai/decisions/2026-09-14-project-automation-core-boundary.md`
- Modify: `.ai/memory/project-context.md`
- Modify: `.ai/memory/studio-status.md`
- Modify: `docs/PROJECT_STRUCTURE.md`

- [ ] **Step 1: 运行后端全量。**

```bash
uv run --directory apps/backend pytest
uv run --directory apps/backend ruff check .
uv run --directory apps/backend mypy src
```

- [ ] **Step 2: 运行桌面和仓库全量。**

```bash
npm test
npm run openapi:check
npm run typecheck
npm run lint
npm run build
npm run test:scripts
npm run test:structure
npm run smoke:sidecar
npm run smoke:desktop
npm run smoke:studio
git diff --check
```

- [ ] **Step 3: 回归既有模块。** 启动真实应用检查项目 PM1/PM2、浏览器配置、代理、模型、设置和 Studio；细网格、小圆角和下拉宽度不得退化。
- [ ] **Step 4: 更新证据。** 只把实际通过的 PM3 功能和场景写入 coverage；PM4–PM9 保持未实现。记录归档复用文件、改造差异、命令退出码、截图和未执行平台。
- [ ] **Step 5: 规格审查。** 逐条核对 PM3 设计：没有第二执行器、没有 HTTP 自调用、Automation 与 Workflow 修订分离、Task 与 queued CoreRun 原子、业务状态不被 Run 改动、重启不自动重放。
- [ ] **Step 6: 工程审查。** 检查循环依赖、服务/仓储事务所有权、敏感信息、迟到事件、后台任务清理、资源关闭、类型重复和无用抽象。修复后重跑受影响测试和全量门槛。
- [ ] **Step 7: 提交交付资料。**

```bash
git add docs/project-management/implementation .ai/decisions/2026-09-14-project-automation-core-boundary.md .ai/memory/project-context.md .ai/memory/studio-status.md docs/PROJECT_STRUCTURE.md docs/superpowers/plans/2026-09-14-project-management-pm3.md
git commit -m "docs(pm3): record automation and run acceptance"
```

## 最终退出条件

PM3 只有同时满足以下条件才完成：

- 工作流文档和执行核心是真实后端能力，不依赖 Mock 成功事件。
- 自动化目录、四页签、Studio 关联、参数启动、运行记录和停止均连接真实接口。
- Task、参数快照和 queued CoreRun 同一事务提交；响应丢失不会重复创建。
- 停止后没有新的网页动作；服务或应用重启不会自动重跑不明确动作。
- 原型逐页截图审查通过，顶部导航是唯一全局导航，主体结构与原型一致。
- 全量自动检查、本机 Electron E2E 和回归通过；手动测试说明可直接执行。
- Windows、其他架构和打包验收按实际结果记录。
- PM4–PM9 未被假实现，主项目和其他工作区未被本阶段修改。

交付后停在 PM3 验收点，不自动进入 PM4。
