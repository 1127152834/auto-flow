# Node Browser Environments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 打开网页节点决定独立实例的模板、代理、内核，环境页维护实例和新建默认值。
**Architecture:** 复用环境服务、持久身份包、唯一 Runtime 和受控 worker 命令通道。新契约延迟至初始化节点启动，旧 Run 保留冻结语义；先补资源事实再切换界面。
**Tech Stack:** 现有 Python/FastAPI/SQLAlchemy/Alembic 与 React/TypeScript/TanStack Query，不新增依赖。
**Spec:** `docs/superpowers/specs/2026-09-24-node-browser-environments-design.md`

## Global Constraints

- 用户于 2026-09-24 批准书面规格并明确要求“开始实施”，直接在本会话执行，不重复申请同一批准。
- 分支 `codex/node-browser-environments`，起点 `15088ecb`；主目录并行 Studio 工作不修改。
- 每 Task 一个活动实例；不支持隐式替换和多命名浏览器；实例修改不写回模板。
- 原命令恢复、项目归属、占用、授权、执行代次、停止清理和 End 明确保留不削弱。
- 只使用已安装 CloakBrowser；禁止静默替换内核和从当前模板猜旧身份。
- 未满足完整验收前 `releaseAccepted=false`；不合并、发布或触碰用户项目数据。

## Review Focus

1. 修改模板后恢复与维护仍用保存身份，旧缺失身份明确拒绝，任务 1 覆盖。
2. 更新实例与保存旧候选竞争不混合内容和身份，任务 1/2 覆盖。
3. 项目默认值保存响应丢失仍查询原命令且保留模型设置，任务 3 覆盖。
4. 初始化响应丢失、重试和取消竞争不产生两个实例或脱管进程，任务 4 覆盖。
5. 分支/循环/从中间调试不能隐式回退旧顶部选择；旧文档迁移不改写已准备 Run，任务 5 覆盖。

### Task 1: 保存与恢复独立身份

**Files:** `domain/environments/{models,rules,identity}.py`，`infrastructure/database/{environment_models,environments}.py`，新迁移 `0024_environment_identity.py`，`application/environments/{service,retention}.py`，`application/project_runs/resources.py`，`application/workflows/browser_resources.py`，`providers/browser/environment_browser.py`；测试 `tests/unit/test_environment_identity.py`、`test_workflow_browser_resources.py`、`tests/integration/test_environment_persist_restore.py`。以上后端路径均在 `apps/backend/`。

**Interfaces:** 新增纯函数 `identity_from_request(request)`、`request_from_identity(identity)` 与 `profile_from_request(request)`，返回可复制的无凭据身份/资源/现有 Profile。PersistentEnvironment 与 EnvironmentInstance 内部增加可空 identity_package；不把完整身份公开到列表。

- [x] 编写缺失/非法身份、模板后改、字典隔离测试。核心断言：`assert restored['frozenConfiguration']['fingerprintSeed'] == original_seed`；缺失身份应抛 `ENVIRONMENT_IDENTITY_UNVERIFIED`。
- [x] `cd apps/backend && uv run pytest tests/unit/test_environment_identity.py tests/unit/test_workflow_browser_resources.py -q`，观察新增行为先失败。
- [x] 从已有资源冻结中提取共同的严格身份组装；新增可空列（从唯一 0023 head 追加），旧库不伪造值。预约实例持有实际 Run 快照；保存和发布将同一身份包随内容代次保存。重放使用原实例/候选，不能读取当前模板。
- [x] worker 和维护从同一身份恢复 Profile；已有环境解析不应用项目默认代理。验证新建冻结路径仍成立；错误发生在浏览器启动前。
- [x] 运行上述单测及 `tests/integration/test_environment_persist_restore.py`、`tests/contract/test_project_environments.py` 和迁移检查，记录结果并提交。

### Task 2: 编辑实例代理与内核

**Files:** 后端 `domain/environments/identity.py`、`application/environments/service.py`、`infrastructure/database/environments.py`、`adapters/http/project_environment_schemas.py`；前端 `pages/EnvironmentDetailPage.tsx`、`api.ts`、生成 DTO。

**Interfaces:** 现有 EnvironmentPatch 添加可选 `browserConfiguration`（代理策略、KernelRef）及 `expectedContentGeneration`。EnvironmentView 仅公开非秘密摘要/身份可恢复状态。沿用 PATCH、ProjectOperation、修订及占用检查，不新建保存系统。

- [x] 扩展真实 HTTP 测试：关闭实例修改代理后再读相同值；已占用/旧修订拒绝；模板与 Cookie 内容不变。
- [x] `cd apps/backend && uv run pytest tests/contract/test_project_environments.py -q`，新增断言先失败。
- [x] 在同一短写事务核对项目、占用、内容/元数据版本；更新身份配置并推进修订。仅允许可证明兼容的内核，不能自动修改原目录。
- [x] 更新 OpenAPI 和前端摘要/编辑组件；输入缺失、只读、运行中和失效内核有明确反馈，未知保存结果复用原幂等命令。
- [x] 运行契约与详情组件测试、OpenAPI 检查、类型检查并提交。

### Task 3: 项目默认设置与环境布局

**Files:** `apps/desktop/src/renderer/domains/environments/components/ProjectDefaultsPanel.tsx`、`pages/EnvironmentWorkspacePage.tsx` 及对应测试；复用 `domains/projects/api.ts`、项目资源目录和已有选择组件。

**Interfaces:** 默认面板接收 client/项目上下文；用 `createProjectsApi.patch` / `resumePatch` 保存 defaultResources，带 expectedManagementRevision；保留 modelProviderId。

- [x] 新增默认设置组件测试：选择模板/代理、保存再读、失效引用、只读、冲突、响应丢失恢复；修改页面测试为右侧概览不存在。
- [x] `npm test -- src/renderer/domains/environments`，观察新增断言失败。
- [x] 删除 DefaultsCard/aside 与两列样式；默认面板改为真实表单。复用原项目命令恢复，不新建临时保存接口。草稿不被查询刷新覆盖。
- [x] 新建默认值只能作用于新实例；在任务 1 的资源测试补 `assert restored_proxy == saved_proxy`，项目默认不同也不影响已有环境。
- [x] 运行环境组件、项目 API、资源解析测试、类型和 lint 后提交。

### Task 4: 节点契约与受控延迟启动

**Files:** 后端 `domain/workflows/{models,validation,run_validation}.py`、`application/workflows/{browser_resources,dispatcher}.py`、`application/workflows/executors/basic.py`、`providers/browser/{workflow_worker,workflow_session}.py`、现有 worker 命令处理模块、项目 coordinator/scheduler；新增对应节点资源契约与真实 worker 用例。

**Interfaces:** 新版工作流持久化版本标记；open_page.browserEnvironment 来源为 current/newFromProfile/fixedEnvironment/inputEnvironment。初始化参数使用已有引用类型；PreparedContent/Run 存每个初始化节点的无秘密冻结资源。Runtime 的浏览器初始化通过现有命令总线，返回受控启动信息；命令身份含 Run、执行代次和节点执行身份。

- [ ] 测试配置严格校验、无浏览器流程、分支未进入零启动、当前实例缺失、第二初始化拒绝、导航失败后重试只建一次。
- [ ] 运行新增 `tests/unit/test_node_browser_environment.py` 与现有 dispatcher/worker 测试，先确认新增断言失败。
- [ ] 准备阶段冻结模板默认值；执行阶段由宿主预约和授权实例，worker 才启动浏览器。保留现有所有权和停止门禁；旧模式继续原提前启动路径。
- [ ] 初始化成功后 context.browser 指向唯一实例；后续节点 current 直接导航。失败、取消和人工处理沿用原资源生命周期。并行初始化/共享页面未隔离时明确拒绝，不扩大准入。
- [ ] 真实 HTTP/SQLite/worker 验证 Cookie 连续、代理/内核实际启动值、响应丢失、取消与无泄漏，保存日志与结果后提交。

### Task 5: Studio 入口切换、迁移和联合验收

**Files:** `domains/workflows/components/config-panels/BasicModuleConfigs.tsx`、`components/Toolbar.tsx`、`editor-store.ts`、执行请求类型和录制/拾取入口；`domains/project-automations` 资源组件；相关文档、`.ai` 会话与机器证据。

**Interfaces:** OpenPageConfig 维护上述来源和三个属性；Toolbar 新模式只传文档资源，不再 resolve 全局 Profile。旧文档显式迁移写节点且持久化新版标记；已有 PreparedContent 不变。录制/拾取消费所选初始化节点或当前实例。

- [ ] 组件测试先断言节点三个属性往返、来源显隐、顶部选择器消失，以及未配置时运行定位节点；录制/调试不回退旧全局值。
- [ ] 对接真实资源目录与执行契约，再删除顶部选择器；更新自动化配置的来源说明，保留旧文档兼容逻辑。
- [ ] 显式迁移界面先展示将写入的入口，多个入口不猜测；保存/导出不受未迁移影响。记录节点内部 schema 与原文档版本的往返结果。
- [ ] 针对性测试通过后执行 `npm test`、`npm run typecheck`、`npm run lint`、`npm run build`、`npm run openapi:check`；后端完整 pytest、ruff/mypy，保留失败/跳过事实。
- [ ] 隔离 Electron/真实后端/worker 联合验收，再对稳定候选发起一次现有三平台 CI（认证受阻则记录条件，不宣称通过）。检查最新代码、截图和实例持久事实，而非仅测试数量。
- [ ] 完整分支独立审查；修正重要问题并补回归；提交代码、文档与 `.ai`。未满足条件仍保持 releaseAccepted=false，不自动合并。

## 执行记录

详细进度、判断与验证命令写入本计划对应 `.superpowers/sdd/` ledger；完成切片同步持久 `.ai` 会话，避免只存在会话上下文。
