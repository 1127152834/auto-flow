# Studio 后端 WebRPA 迁入实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将冻结 WebRPA 3.2.0 中当前批准的 227 个节点及其共享业务能力迁入 AutoFlow 正式 sidecar，使已验收的 Studio 前端无需补业务分支即可完成真实保存、执行、Debug、拾取、录制、日志、结果和宿主生命周期闭环。

**Architecture:** 保留 WebRPA 的执行器注册、图解析、变量、控制流和节点业务语义，把全局浏览器、文件、数据库、秘密、模型与外部服务访问替换为 AutoFlow domain port。HTTP/SSE 只适配已冻结的前端合同；应用层协调工作区资源、稳定命令标识和清理；每次运行使用一个受管 worker，CloakBrowser Profile 只从主应用读取。

**Tech Stack:** Python 3.11、FastAPI、Pydantic、SQLAlchemy、Alembic、SQLite、CloakBrowser 0.5.9、pytest、Ruff、mypy；Studio 小助手使用经 B5 兼容验证后锁定版本的 LangGraph；Electron、React、TypeScript、Vitest、现有 Electron CDP smoke 与 CUA 正式 UI 验收；JSON/JSONL、SSE、工作区文件产物。

**Spec:** [Studio 后端 WebRPA 迁入设计规格](../specs/2026-09-15-studio-backend-webrpa-migration-design.md)

## 全局约束

- 权威节点范围是 [scope-database-dp-cloakbrowser.md](../../migration/studio-frontend-completion/scope-database-dp-cloakbrowser.md) 与 [capabilities.json](../../migration/studio-frontend-completion/capabilities.json) 中的 227 项。数据库 48 项、DP 9 项及此前排除能力不得恢复。
- 冻结源码固定为 `reference/WebRPA` 提交 `5ccb900e8dcf1530aae66f676d87593c416c7ebb`、产品版本 3.2.0。生产包不得读取该目录；它只用于迁入、差分测试和来源追踪。
- `LICENSE.WebRPA` 保存与冻结上游相同的许可文本。项目负责人已确认在本项目范围内获准使用并迁入源码；不把该确认写成具体商业授权或公开发布授权。每个迁入文件仍记录来源、上游许可证和修改内容。
- 中文单语言。Studio 只消费主应用 CloakBrowser Profile，不迁入 WebRPA 浏览器配置 UI、内核管理或第二套凭据。
- 前端验收、Mock 协议验收和真实后端验收分开记账。Mock 不能核销真实执行、真实采集或真实秘密存储用例。
- Studio 小助手必须由 LangGraph 实际处理多轮模型/工具/权限/取消/恢复；普通工作流执行器不得改为 LangGraph，也不得保留一条绕过图的完整助手循环。
- 不改写历史迁移，不在测试中打开用户数据库。所有迁移与浏览器测试使用程序创建的临时工作区或用户数据库只读副本。
- 不执行 `git reset`、`git clean`、全量回滚或无关格式化；每个提交只包含本任务功能边界内的文件。
- 每个节点必须核销 `BE.<type>.source-parity`、`BE.<type>.contract`、`BE.<type>.real-execution`。共享算法集中测试，但节点注册、字段映射和独有分支逐项验证。
- 所有命令、运行、拾取、录制和 Debug 控制使用客户端稳定 ID；相同 ID 与相同请求幂等，相同 ID 与不同请求返回 409。
- 清理完成前不报告终态、不释放 Profile/内核/工作区占用。SSE 断线不等于运行失败，sidecar 崩溃不重放网页动作。
- 先写失败用例，再迁入最小源码，再运行受影响检查；功能块关闭或共享基础设施变化时才扩大回归。

### 2026-09-15 执行策略调整

经项目负责人批准，本计划改为“原版模块批量迁入 + 按实际依赖并行推进 + 集中真实验收”。B0–B9 的验收要求与最终完成标准不变；里程碑编号表示能力归属，不再表示所有工作只能严格串行。

- 以冻结 WebRPA 的源码文件或紧密依赖模块族为迁入单位，一次迁入其中全部批准节点；不为每个节点重新设计实现。
- 依赖已经稳定的任务可以提前实施和做专项验证。依赖未稳定的任务只能做源码差分、纯逻辑迁入或明确的接口准备，不能提前核销集成验收。
- 调度器、共享协议、数据库迁移、执行器注册汇总和生命周期由唯一集成负责人修改；并行任务只修改文件边界清晰的模块并提出接口需求。
- B1 正式五节点主链的已有证据直接核销；正常关窗保护、停止、异常和离开矩阵仍须分别验收，不能由 `BrowserWindow.destroy()` 后重开替代。
- 局部修改只运行受影响测试。模块族关闭、共享边界变化和最终交付时扩大回归；不重复运行没有新风险的完整构建或全量测试。
- 首个效率检查点以 4 小时为预算：先确定依赖和模块族，再批量迁入及差分验证，最后测试、修复和记录证据。该预算既不是阶段完成承诺，也不是停止指令。

---

## B0：迁移历史兼容与事实源护栏

**用户结果：** 暂无新页面能力；后续后端可在临时工作区、当前数据库和包含 `0010_android_fleet` 的正式数据副本上安全启动，不丢现有工作流、项目数据或 Android 表。

**前置依赖：** 无。B0 是所有生产持久化工作的硬前置。

**估计：** 开发 1–2 工程日；验证 1–2 工程日；外部等待未知，只在取得脱敏的用户数据库副本或由用户在本机执行只读复制后发生。置信度中。

### Task B0.1：冻结源和 227 节点映射防漂移

**Files:**
- Create: `apps/backend/tests/migration/test_studio_backend_source_mapping.py`
- Modify: `docs/migration/studio-frontend-completion/capabilities.json`
- Modify: `docs/migration/studio-frontend-completion/backend-support-mapping.json`
- Evidence: `docs/migration/studio-backend-migration/evidence/b0/source-mapping.json`

- [x] 写测试读取 `capabilities.json`，断言恰有 227 个唯一类型，每项都有冻结文件、符号、行号、注册方式、共享能力引用和三条唯一验收 ID。
- [x] 解析冻结 `_SUBMODULES`、`@register_executor` 与手动 `registry.register`，先确认测试能在缺失或漂移时失败。
- [x] 固定预期为 226 个装饰器注册和 `subflow` 手动注册；排除类型若混入立即失败。
- [x] 运行 `cd apps/backend && uv run pytest tests/migration/test_studio_backend_source_mapping.py -q`。
- [x] 保存命令、退出码、冻结 commit、类型差异和映射摘要到证据 JSON。
- [x] 提交边界：只提交映射护栏、台账修正与 B0 证据。

### Task B0.2：恢复缺失的历史 revision 并合并 Alembic heads

**Files:**
- Create verbatim from commit `f573a44`: `apps/backend/src/autoflow/infrastructure/database/migrations/versions/0007_android_devices.py`
- Create verbatim from commit `f573a44`: `apps/backend/src/autoflow/infrastructure/database/migrations/versions/0008_merge_android_m4.py`
- Create verbatim from commit `f573a44`: `apps/backend/src/autoflow/infrastructure/database/migrations/versions/0009_merge_android_m5.py`
- Create verbatim from commit `f573a44`: `apps/backend/src/autoflow/infrastructure/database/migrations/versions/0010_android_fleet.py`
- Create: `apps/backend/src/autoflow/infrastructure/database/migrations/versions/0011_merge_android_project_data.py`
- Create: `apps/backend/tests/integration/test_studio_migration_compatibility.py`
- Create: `apps/backend/tests/integration/test_migration_heads.py`
- Evidence: `docs/migration/studio-backend-migration/evidence/b0/migration-graph.json`

- [x] 先写迁移图测试，要求 `0011_merge_android_project_data` 的 `down_revision == ("0010_android_fleet", "0009_merge_project_data")` 且 Alembic 只有一个 head。
- [x] 从 `f573a44` 逐字恢复四个历史文件，校验文件哈希；不得恢复 Android 路由、服务、ORM 或 UI。
- [x] 增加空操作 merge revision；`upgrade` 和 `downgrade` 都不修改业务表。
- [x] 构造空库、`0005`–`0008` 工作流库、当前 `0009_merge_project_data` 库和 `0010_android_fleet` 库，分别升级到唯一 head。
- [x] 在事务中注入失败，验证未 stamp、无半迁移；重复启动验证幂等。
- [x] 运行 `cd apps/backend && uv run pytest tests/integration/test_studio_migration_compatibility.py tests/integration/test_migration_heads.py -q`。
- [x] 运行 `cd apps/backend && uv run alembic -c src/autoflow/infrastructure/database/alembic.ini heads`，输出必须只有 `0011_merge_android_project_data`。
- [x] 提交边界：只提交迁移文件、迁移测试与证据。

### Task B0.3：只读数据库副本兼容验证

**Files:**
- Create: `apps/backend/scripts/inspect_database_compatibility.py`
- Create: `apps/backend/tests/integration/test_database_compatibility_inspector.py`
- Evidence: `docs/migration/studio-backend-migration/evidence/b0/database-copy-report.json`

- [x] 实现只接收显式源路径和独立目标路径的检查脚本；源文件以只读 URI 打开，只输出 revision、表/列/索引/外键、行数和非秘密数据哈希。
- [x] 用临时 fixture 证明源文件 mtime、大小与哈希在检查前后不变；源目标相同、目标已存在或源非 SQLite 时拒绝。
- [x] 在副本上执行升级并比较业务表行数与哈希；不得执行 downgrade、stamp、drop。
- [x] 没有正式副本时将 `BE-B0-004/005` 保持“外部等待”，不能以临时 fixture 标通过。
- [x] 运行 Ruff、mypy 和上述测试；证据中记录原库未被写入的校验值。

### Task B0.4：记录源码使用确认并固定迁入记录格式

**Files:**
- Verify unchanged: `LICENSE.WebRPA`
- Create: `docs/migration/studio-backend-migration/source-provenance.json`
- Create: `.ai/decisions/2026-09-15-studio-webrpa-backend-source-authorization.md`

- [x] 校验 `LICENSE.WebRPA` 与冻结 `reference/WebRPA/LICENSE` SHA-256 相同，并记录上游 commit、原路径与产品版本。
- [x] 记录项目负责人确认“已经获得在本项目范围内使用并迁入 WebRPA 源码的授权”；不得推断或写成具体商业授权、公开发布授权或其它未确认权利。
- [x] 定义每个直接迁入文件的来源 commit、源路径、目标路径、修改摘要、保留/删除依赖和许可路径字段；`capabilities.json` 的 227 项引用该来源记录。
- [x] 授权确认记录与来源台账通过结构检查后，源码使用门槛关闭，B1.2 可以按计划迁入。

**B0 退出门槛：** `BE-B0-001` 至 `BE-B0-008` 中除明确依赖正式副本的项外均通过；Alembic 只有一个 head；正式副本项若未取得必须作为 B1 使用临时工作区的显式限制。源码使用确认已记录，不再阻塞 B1.2；任何正式用户数据接入仍被阻止。

---

## B1：五节点真实纵向闭环

**用户结果：** 用户能在正式 Studio 新建并保存 `打开网页 → 输入文本 → 点击元素 → 提取数据 → 网页截图`，关闭重开后选择主应用 Profile，在独立 CloakBrowser 中真实执行，查看持久化日志、提取结果和 PNG，并停止清理。

**前置依赖：** B0 临时数据库路径通过；WebRPA 本项目范围内源码使用确认与来源记录已完成；主应用 Profile、已安装 CloakBrowser 内核与有效 License 可用；本地受控网页 fixture 可启动。

**估计：** 开发 12–20 工程日；验证 6–10 工程日；外部等待 0–3 工程日用于 CloakBrowser 平台/License 环境。置信度低，因为尚无当前架构下真实执行器迁入速率样本。

### Task B1.1：工作流领域模型、保存规则和仓储

**Frozen sources:**
- `reference/WebRPA/backend/app/models/workflow.py`
- `reference/WebRPA/backend/app/models/custom_module.py`
- `reference/WebRPA/backend/app/api/workflows.py`

**Files:**
- Delete: `apps/backend/src/autoflow/domain/workflows/.gitkeep`
- Delete: `apps/backend/src/autoflow/application/workflows/.gitkeep`
- Create: `apps/backend/src/autoflow/domain/workflows/__init__.py`
- Create: `apps/backend/src/autoflow/application/workflows/__init__.py`
- Create: `apps/backend/src/autoflow/domain/workflows/document.py`
- Create: `apps/backend/src/autoflow/domain/workflows/errors.py`
- Create: `apps/backend/src/autoflow/domain/workflows/ports.py`
- Create: `apps/backend/src/autoflow/application/workflows/documents.py`
- Create: `apps/backend/src/autoflow/infrastructure/database/workflow_models.py`
- Create: `apps/backend/src/autoflow/infrastructure/database/workflows.py`
- Create: `apps/backend/tests/unit/workflows/test_documents.py`
- Create: `apps/backend/tests/integration/test_workflow_repository.py`

- [x] 用前端真实 fixture 写保存往返、未知字段保留、`selected/dragging` 不持久化、稳定 ID、revision 冲突、保存失败回滚和保存中继续编辑的失败测试。
- [x] 定义 `WorkflowDocumentRepository`，接口至少包含 `list_summaries(workspace_id, cursor, limit)`、`get(workspace_id, workflow_id)`、`create(snapshot, client_request_id)`、`update(snapshot, expected_revision, client_request_id)`、`delete(expected_revision)`。
- [x] 服务生成 revision、时间和内容摘要；文档与布局在同一事务写入。
- [x] 使用现有 `0005_workflow_documents` 表意；若字段不足，只在 B0 唯一 head 后新增一条增量迁移，不改 `0005`。
- [x] 运行 unit/repository 测试，并以 SQLite 故障注入验证原子性。

### Task B1.2：迁入执行器注册、图解析和变量内核

**Frozen sources:**
- `reference/WebRPA/backend/app/executors/__init__.py`
- `reference/WebRPA/backend/app/services/workflow_parser.py`
- `reference/WebRPA/backend/app/services/workflow_executor.py`
- `reference/WebRPA/backend/app/services/variable_manager.py`
- `reference/WebRPA/backend/app/executors/base.py`
- `reference/WebRPA/backend/app/executors/type_utils.py`

**Files:**
- Create: `apps/backend/src/autoflow/application/workflows/executors/__init__.py`
- Create: `apps/backend/src/autoflow/domain/workflows/graph.py`
- Create: `apps/backend/src/autoflow/domain/workflows/variables.py`
- Create: `apps/backend/src/autoflow/domain/workflows/execution.py`
- Create: `apps/backend/src/autoflow/application/workflows/executors/base.py`
- Create: `apps/backend/src/autoflow/application/workflows/executors/registry.py`
- Create: `apps/backend/src/autoflow/application/workflows/runtime.py`
- Create: `apps/backend/tests/differential/workflows/test_graph_parser_parity.py`
- Create: `apps/backend/tests/differential/workflows/test_variable_parity.py`
- Create: `apps/backend/tests/unit/workflows/test_executor_registry.py`

- [x] 参数化移植冻结的 parser、variable、safe expression 与 registry 用例，先让它们对空目标实现失败。
- [x] 保留注册覆盖次序、起点、分支和原变量替换行为；删除 FastAPI、SQLAlchemy、全局 browser engine 依赖。
- [x] 定义 `ExecutionContext`，仅暴露浏览器、产物、凭据、模型、外部集成、事件、取消与时钟端口。
- [x] 未知/排除/尚未迁入节点在预检返回 `UNSUPPORTED_NODE_TYPE`，包含 `nodeId` 和 `path`，不执行任何节点。
- [x] 运行冻结差分用例与 registry 测试；证据记录源输入、源输出、目标输出和允许的 AutoFlow 适配差异。

### Task B1.3：CloakBrowser 会话端口和受管 worker

**Frozen sources:**
- `reference/WebRPA/backend/app/services/browser_engine.py`
- `reference/WebRPA/backend/app/services/browser_manager.py`
- `reference/WebRPA/backend/app/services/browser_process.py`

**Reusable AutoFlow sources:**
- `apps/backend/src/autoflow/application/profiles/test_browser.py`
- `apps/backend/src/autoflow/providers/browser/worker.py`
- `apps/backend/src/autoflow/infrastructure/process/browser_processes.py`
- `apps/backend/src/autoflow/infrastructure/filesystem/profile_data.py`

**Files:**
- Create: `apps/backend/src/autoflow/domain/workflows/browser.py`
- Create: `apps/backend/src/autoflow/providers/browser/workflow_session.py`
- Create: `apps/backend/src/autoflow/infrastructure/process/workflow_worker.py`
- Create: `apps/backend/src/autoflow/bootstrap/workflow_worker.py`
- Create: `apps/backend/tests/unit/workflows/test_browser_session_contract.py`
- Create: `apps/backend/tests/integration/test_workflow_worker_protocol.py`
- Create: `apps/backend/tests/integration/test_workflow_resource_ownership.py`

- [x] 定义页面/context/locator/下载/截图的窄端口，页面身份和当前页规则以冻结 WebRPA 为基准。
- [x] worker 启动消息只接收运行快照、Profile 冻结参数和秘密引用；License/代理密码不得回传事件或日志。
- [x] 复用 `FilesystemProfileUsageGuard` 与进程出生/组清理；新增工作区活跃运行和内核目标占用协调。
- [x] 验证启动中取消、命令管道断开、浏览器被杀、worker 被杀和超时强杀；清理完成前保持占用。
- [x] 运行协议与资源测试，使用真实短生命周期子进程，不用内存状态冒充清理。

### Task B1.4：迁入首批五个网页执行器

**Source mapping:** `capabilities.json` 中 B1 的 `open_page`、`click_element`、`input_text`、`get_element_info`、`screenshot` 条目。

**Files:**
- Create or modify only files named by each entry's `backendMigration.target.executor`
- Create: `apps/backend/tests/differential/workflows/test_b1_executor_parity.py`
- Create: `apps/backend/tests/integration/test_b1_cloakbrowser_flow.py`
- Fixture: `apps/backend/tests/fixtures/workflow-page.html`
- Fixture: `apps/backend/tests/fixtures/workflow-frame.html`

- [x] 对每节点建立字段映射表，覆盖默认值、变量、CSS/XPath、超时、空值、首个匹配和错误。
- [x] 先逐项运行 `BE.<type>.source-parity`；只有 WebRPA IO 调用替换为 `ExecutionContext` port，业务分支保持源码行为。
- [x] 在本地受控页面核对导航 URL、输入值、点击计数、提取字节和 PNG 解码/尺寸。
- [x] 对导航、输入和截图分别测试取消；确认后续节点没有副作用。
- [x] 把五节点三类证据写入各自 `backendMigration.acceptanceCases[].evidencePath`；源码差分、HTTP 合同和真实 provider 分别引用证据，正式 Electron 项保持待验收，不提前标记 B2 节点完成。

### Task B1.5：运行、事件、日志和产物持久化

**Frozen sources:**
- `reference/WebRPA/backend/app/services/workflow_runner.py`
- `reference/WebRPA/backend/app/services/workflow_log_manager.py`
- `reference/WebRPA/backend/app/services/workflow_timeout.py`

**Files:**
- Create: `apps/backend/src/autoflow/domain/workflows/runs.py`
- Create: `apps/backend/src/autoflow/application/workflows/runs.py`
- Create: `apps/backend/src/autoflow/application/workflows/events.py`
- Create: `apps/backend/src/autoflow/infrastructure/database/workflow_runs.py`
- Create: `apps/backend/src/autoflow/infrastructure/filesystem/workflow_artifacts.py`
- Create: `apps/backend/src/autoflow/infrastructure/events/workflows.py`
- Create: `apps/backend/tests/integration/test_workflow_run_repository.py`
- Create: `apps/backend/tests/integration/test_workflow_events.py`
- Create: `apps/backend/tests/integration/test_workflow_artifacts.py`

- [x] 先写 runId 同请求幂等、不同请求冲突、事件事务顺序、SSE 补读、大值引用和文件落盘失败测试。
- [x] 定义运行状态，使 accepted 到清理完成一直占用资源；终态不能由完成节点数量推断。
- [x] `workflow_run_events` 每个 run 严格递增；节点成功状态和事件同事务提交，提交后再广播。
- [x] 产物先写临时文件、fsync/原子替换，再登记归属、相对路径、大小、哈希、MIME 和 purpose；下载只接受 artifact ID。
- [x] 启动恢复把遗留活跃运行标为 interrupted，不重启 worker，不重放动作。

### Task B1.6：真实 HTTP/SSE 合同与装配

**Files:**
- Create: `apps/backend/src/autoflow/adapters/http/workflows.py`
- Create: `apps/backend/src/autoflow/adapters/http/workflow_runs.py`
- Create: `apps/backend/src/autoflow/adapters/events/workflows.py`
- Create: `apps/backend/src/autoflow/bootstrap/workflows.py`
- Modify: `apps/backend/src/autoflow/bootstrap/app.py`
- Modify: `apps/backend/src/autoflow/bootstrap/http_routes.py`
- Modify: `apps/backend/src/autoflow/adapters/http/errors.py`
- Modify: `apps/backend/src/autoflow/adapters/http/workflow_studio_schemas.py` only when the frozen frontend contract requires a missing runtime schema
- Create: `apps/backend/tests/contract/test_workflows_api.py`
- Create: `apps/backend/tests/contract/test_workflow_runs_api.py`
- Create: `apps/backend/tests/contract/test_workflow_events_api.py`

- [x] 按前端 `api.ts` 和 `contract-matrix.md` 注册静态路由，确保 `/workflows/data-latest/*`、`/workflow-runs/*` 等不会被动态 `{id}` 路由吞掉。
- [x] 复用本机 token、工作区实例/连接代次、统一错误包和 `QuiesceGate`。
- [x] 运行相同 runId 的响应丢失、停止竞争、SSE 断流补读、分页边界和停写阻断测试；正式 sidecar 断流与宿主竞争仍由 B1.7 做 Electron 实测。
- [x] 运行 `cd apps/backend && uv run pytest tests/contract/test_studio_*.py tests/contract/test_workflows_api.py tests/contract/test_workflow_runs_api.py tests/contract/test_workflow_events_api.py -q`，结果为 388 passed。
- [x] 运行 OpenAPI 生成与一致性检查；生成类型变化均来自运行草稿快照、结果分页与产物读取合同，并通过 TypeScript 检查。

### Task B1.7：正式 Electron 真实 UI 验收

**Files:**
- Create: `scripts/smoke-studio-backend-b1.mjs`
- Reuse: `scripts/electron-cdp.mjs`
- Create: `apps/desktop/tests/fixtures/studio-backend-b1-workflow.json`
- Evidence: `docs/migration/studio-backend-migration/evidence/b1/`

- [ ] 通过真实主窗口打开 Studio，点击新建、拖入五节点、填写、连线、保存、关闭、重开并核对恢复；不得直接修改 Store。
- [ ] 通过 UI 选择主应用 Profile 并运行；核对页面真实状态、日志、提取内容与 PNG。
- [ ] 运行中修改草稿，证明运行快照隔离；停止并确认 browser/worker PID 和锁均释放。
- [ ] 覆盖保存冲突、HTTP 首次响应丢失、SSE 断线、新建/打开/关闭/退出/换区的保存、放弃、取消顺序。
- [ ] CDP smoke 只允许查找/操作可访问 UI 和派发真实输入事件，不得调用 Store、页面私有函数或直接构造服务完成状态；关键链路另用 CUA 实点复核并保存截图/AX/网络/进程证据。
- [ ] 在开发入口、冻结 sidecar 和 Electron 目录包各运行一次；包内扫描不得引用 `reference/WebRPA`、Mock server 或 Vite URL。
- [ ] 关闭 `BE-B1-001` 至 `BE-B1-012`，为五节点写入真实证据；B1 未关闭时，B2 中依赖已稳定、文件边界独立的模块族可以提前迁入和专项验证，但不得绕过其共享定位、会话、生命周期及正式 UI 门槛。

**B1 退出门槛：** 正式 Electron 五节点闭环及失败、停止、重连、幂等、清理通过；五节点 15 条逐项用例有真实路径；pytest、Ruff、mypy、OpenAPI、TypeScript、ESLint、renderer/main/preload 构建和目录包 smoke 通过。

---

## B2：其余网页节点、统一定位与拾取

**用户结果：** 35 个网页节点全部真实执行；用户可打开专用浏览器、选择页面、拾取/测试元素并应用到节点，保存后在独立运行浏览器命中同一目标。

**前置依赖：** B1 的 CloakBrowser worker、执行上下文与资源所有权边界稳定；涉及正常离开、共享定位或会话互斥的集成验收仍依赖 B1/B2 对应生命周期门槛。跨 origin、iframe、Shadow DOM、下载、弹窗和网络监听 fixture 可用。

**源码与目标：** 以 `capabilities.json` 中 B2 的 30 项为逐节点文件清单；共享来源为 WebRPA `browser_engine.py`、`element_picker/` 及浏览器相关执行器，目标集中在 `application/workflows/executors/`、`providers/browser/`、`application/workflows/inspection.py`、`adapters/http/workflow_inspection.py`。

**接口与数据：** 实现前端现有 `/api/browser/*`、`/api/element-picker/*` 请求和对应命令状态；会话持久化资源所有权、页面身份与已确认请求，悬停高亮等瞬态只留 worker 内存。定位结果保存回工作流文档，浏览器 Cookie/登录态不进入数据库。

**估计：** 开发 15–25 工程日；验证 10–15 工程日；外部等待 0–5 工程日用于 CloakBrowser 平台差异。置信度低。

- [ ] Task B2.1：把 locator、frame/page identity、导航、弹窗、下载、网络监听抽成已有 Browser port 的有限能力；不建通用 RPC。
- [ ] Task B2.2：按 30 项映射逐个迁入执行器，每项先差分字段与独有分支，再做真实页面证据。
- [ ] Task B2.3：实现 inspection session 仓储、受管 worker 命令、页面列表、拾取、测试、相似元素、取消和幂等查询，接上现有 `/element-picker/*` 与 `/browser/*` 合同。
- [ ] Task B2.4：真实验证 CSS、XPath、零/一/多匹配、同域/跨域嵌套 iframe、开放 Shadow DOM、页面关闭/导航失效和高亮清理。
- [ ] Task B2.5：验证运行、Debug、拾取、录制的原子互斥，以及清理失败时资源不提前释放。
- [ ] Task B2.6：通过正式 UI 完成拾取→测试→应用→保存→独立运行；关闭 B2 的 90 条逐节点用例和 `BE-B2-001` 至 `008`。

**B2 退出门槛：** 35 个网页节点真实行为通过；拾取结果可以由独立运行重放；页面/字段迟到结果不会覆盖新状态；大值、下载、截图与网络产物按引用完整读取。B3 的源码差分与纯控制算法可以并行准备；依赖网页副作用的集成验收须等待共享定位与会话所有权稳定。

---

## B3：控制流、变量、子流程与自定义模块

**用户结果：** 用户能保存并运行条件、循环、并行、错误边、变量、子流程和自定义模块组成的复杂流程，重复节点的日志与结果能对应具体执行轮次。

**前置依赖：** B1 调度/事件稳定，B2 页面动作可作为分支副作用核验。

**源码与目标：** `capabilities.json` 中 B3 的 21 项；WebRPA `workflow_parser.py`、`workflow_executor.py`、`variable_manager.py`、`subflow.py`、控制执行器；目标为 `domain/workflows/graph.py`、`variables.py`、`application/workflows/runtime.py`、`executors/control*.py`、`application/workflows/modules.py`、`infrastructure/database/workflow_modules.py`。

**接口与数据：** 扩展工作流保存/运行预检合同并实现 `/api/custom-modules*`；模块正文、revision 和依赖图持久化，运行记录保存解析后的不可变模块快照和 executionId 上下文。

**估计：** 开发 12–20 工程日；验证 8–12 工程日；外部等待无。置信度中低。

- [x] Task B3.1：将冻结 parser/variable/subflow 测试参数化为源/目标差分，覆盖几何分组、无入口回退、错误边、循环和并行偏序。
- [x] Task B3.2：迁入 21 节点及注册，保留 `${name}`、`{name}`、递归值、scope stack、break/continue、stop 与等待语义。
  - 2026-09-16 检查点：21/21 节点已生产注册；控制/变量/视觉、`input_prompt`、`run_workflow_file` 与 `subflow` 的源码差分及真实 worker/HTTP 合同已通过。节点迁入完成；不计入227节点但属必要配套的自定义模块仓储/运行时和正式Electron集中验收仍未完成。
- [x] Task B3.3：实现自定义模块 CRUD、revision、依赖图、循环引用检测和运行时冻结解析；工作流保存只存引用，运行快照存解析内容与摘要。
  - 2026-09-16 检查点：八个前端入口已接入真实 SQLite 仓储；稳定请求 ID、revision、名称冲突、依赖缺失/循环、工作流引用删除保护、运行快照摘要、嵌套隔离执行、声明输出回传、浏览器需求传播及 16 层允许/17 层拒绝均通过专项、真实 HTTP 与 worker 验证。正式 Electron 组合仍归 B3.6 集中验收。
- [ ] Task B3.4：每次调度生成 executionId 和循环/子流程上下文；同一 nodeId 多轮不得覆盖事件或产物。
- [ ] Task B3.5：测试并行取消、1,000 轮纯变量停止、空/非法控制流、缺变量和嵌套 32 层；失败位置必须指向 nodeId/path。
- [ ] Task B3.6：正式 UI 编排包含真假分支、循环、并行和子流程的流程，保存重开并真实执行；关闭 B3 的 63 条节点用例与 `BE-B3-001` 至 `008`。

**B3 退出门槛：** 图和变量差分无未解释差异；并行没有为测试被串行化；模块运行快照不受运行中编辑影响；停止可中断纯算法循环和网页动作。

---

## B4：纯数据与表格执行器

**用户结果：** 用户能在不启动浏览器的流程中处理字符串、正则、JSON、列表、字典、数学、统计、表格和 CSV，也能把这些节点与网页结果组合运行。

**前置依赖：** 对应模块族使用的变量读取、写入和错误封装接口稳定。字符串、列表、字典、数学等不依赖复杂控制流的源码族可以提前迁入并做差分验证；工作流集成、取消和错误策略验收仍等待 B3 相关边界稳定。

**源码与目标：** `capabilities.json` 中 B4 的 88 项；WebRPA `string*.py`、`list*.py`、`dict*.py`、`math*.py`、`statistics.py`、`table*.py`、`type_utils.py`、`safe_expr.py`、`json_safe.py`；目标为对应 `application/workflows/executors/` 模块，文件边界保持原版族群。

**接口与数据：** 不新增节点专属 HTTP 体系；继续通过工作流运行、事件、结果和产物接口。表格/CSV 文件只通过登记后的 artifact/file port 读写，运行变量保留原值类型。

**估计：** 开发 10–18 工程日；验证 8–15 工程日；外部等待无。置信度中。

- [ ] Task B4.1：参数化原版纯函数测试，覆盖中文、空值、NaN/Infinity、编码、越界、正则和集合顺序。
- [ ] Task B4.2：按原模块族迁入 88 节点；标准库可直接使用，不增加新的数据处理框架。
- [ ] Task B4.3：文件读写通过 Artifact/File port，验证路径归属、CSV 编码、哈希、原子落盘和磁盘失败。
- [ ] Task B4.4：加入可取消检查点，验证 CPU 密集和大序列化取消后无半份产物。
- [ ] Task B4.5：逐项核销 264 条节点用例和 `BE-B4-001` 至 `005`，再运行 B1–B3 回归。

**B4 退出门槛：** 88 节点注册、合同、真实执行全部有证据；源/目标值差异为零或已记录的 AutoFlow IO 适配；性能/取消测试有界。

---

## B5：AI 节点、模型、MCP 与 LangGraph 小助手

**用户结果：** 22 个 AI/视觉节点使用主应用模型与 MCP 配置执行；Studio 小助手通过 LangGraph 完成多轮模型调用、画布工具、权限批准/拒绝、取消与恢复。流式结果、错误和大产物可诊断，秘密不会进入运行记录或图检查点。

**前置依赖：** B1 事件/产物，B2 浏览器，主应用 ModelService 可按稳定 model ID 读取。

**源码与目标：** `capabilities.json` 中 B5 的 22 项；WebRPA `ai*.py`、Firecrawl、OCR/验证码/人脸执行器、`ai_assistant_service.py` 及模型/MCP 服务；目标为 `domain/workflows/model.py`、`providers/model/` 适配、`application/workflows/executors/ai*.py`、`application/workflows/mcp.py`、`application/workflows/assistant.py`、`providers/assistant/__init__.py`、`providers/assistant/langgraph.py`、`infrastructure/database/workflow_assistant_checkpoints.py`、`adapters/http/workflow_ai.py` 和 `adapters/http/workflow_mcp.py`。

**接口与数据：** 复用主应用模型查询，落实现有小助手与 MCP 请求/编号事件；新增的 LangGraph thread/checkpoint 只存工作区隔离的安全状态和工具命令引用，大模型输出及大文件走结果/产物索引。

**估计：** 开发 12–20 工程日；验证 8–15 工程日；外部等待未知，取决于供应商凭据、额度、模型可用性和 MCP server。置信度低。

- [ ] Task B5.1：定义 Model/MCP 窄端口，复用主应用 model ID 和系统秘密存储；不迁入第二套 provider 配置。
- [ ] Task B5.2：建立 `tests/compatibility/test_langgraph_runtime.py`，验证候选 LangGraph 版本在 Python 3.11 下的图中断、检查点恢复、取消、无默认外部遥测和 PyInstaller 收集；通过后才修改 `apps/backend/pyproject.toml` 与锁文件。
- [ ] Task B5.3：实现小助手图：上下文→模型→结构化工具校验→权限中断→工具结果→后续模型；`assistantSessionId` 映射受工作区隔离的 thread/checkpoint，恢复查询原 commandId，不重放副作用。
- [ ] Task B5.4：把模型文本、工具请求、权限状态、结果、错误和结束投影到现有 SSE/查询合同；服务端重复检查 227 范围、工具开关、参数和批准修订。
- [ ] Task B5.5：用本地可控 HTTP/MCP fixture 迁入 22 节点，验证请求形状、流式分块、取消、超时、限流和错误映射。
- [ ] Task B5.6：实现现有 MCP 保存、测试、重载和调用合同，写操作带 revision/commandId，MCP 工具不能绕过小助手权限。
- [ ] Task B5.7：大图像/视频/文本经 artifact 引用传输；日志、SSE、诊断、LangGraph 检查点和导出扫描不得出现 API key、代理密码或 License。
- [ ] Task B5.8：正式 UI 验证小助手多轮添加/修改节点、批准/拒绝/取消、断线重连及历史；排除节点请求必须拒绝，页面确认前不得宣称草稿已修改。
- [ ] Task B5.9：核销本地合同和真实供应商证据；没有凭据的供应商保持“外部等待”，不能用 fixture 核销 real-execution。

**B5 退出门槛：** 66 条节点用例和 `BE-B5-001` 至 `005` 有证据；小助手确实通过 LangGraph 完成多轮工具与权限闭环，重启/重连不重复副作用，正式包可加载图和检查点；真实供应商未测项明确列出并阻止对应节点最终完成，不阻止其它已独立验收节点进入 B6。

---

## B6：触发器、计划任务、外部集成与平台能力

**用户结果：** 用户能配置并真实运行当前保留的 API、邮件、通知、SSH、分享、触发器、计划任务、脚本、语音和平台节点；不可用平台得到明确能力错误。

**前置依赖：** B1 运行幂等/生命周期，B3 图与变量，B5 凭据/模型边界。

**源码与目标：** `capabilities.json` 中 B6 的 61 项；WebRPA trigger/scheduler/notify/ssh/share/script/system executors；目标按映射进入 `application/workflows/executors/`、`providers/integrations/`、`application/workflows/triggers.py`、`infrastructure/database/workflow_triggers.py`、`adapters/http/workflow_triggers.py`。

**接口与数据：** 实现现有 `/api/scheduled-tasks*`、运行期 `/api/events/*` 查询/回传及保留的配置服务；触发器、计划、在途请求与外部资源所有权持久化，秘密仅保存引用。

**估计：** 开发 18–30 工程日；验证 12–22 工程日；外部等待未知，涉及邮件/通知/SSH 凭据和 macOS Intel/Windows/打印环境。置信度低。

- [ ] Task B6.1：建立本地 HTTP、SMTP、SSH、webhook、文件监视和通知 fixture；可观测请求次数、字节、时区和关闭状态。
- [ ] Task B6.2：按依赖族迁入 61 节点；网络统一使用 timeout/取消/代理/脱敏端口，平台命令使用能力探测。
- [ ] Task B6.3：实现触发器与计划任务持久化、去重、停写和重启语义；历史事件不得在重启后重放。
- [ ] Task B6.4：实现输入、JS/Python、语音和路径等双向请求的 claim/result/cancel/query 幂等，停止回收所有在途请求。
- [ ] Task B6.5：验证分享/屏幕服务端口冲突、停止和进程退出；监听 socket 关闭后才报告成功。
- [ ] Task B6.6：平台节点在隔离适配器和对应实机分别记账；无真实设备的平台保持未验收，不能假成功。
- [ ] Task B6.7：核销 183 条节点用例和 `BE-B6-001` 至 `008`，再做全运行生命周期回归。

**B6 退出门槛：** 所有可用依赖族在本地受控服务与正式 UI 通过；真实外部或平台等待逐节点登记；无残留监听端口、子进程、任务或秘密泄漏。

---

## B7：真实网页录制、审查与生成

**用户结果：** 用户能在专用可见 CloakBrowser 中录制真实操作，暂停/恢复/停止，审查、编辑、变量化并整批加入画布；保存重开后在独立浏览器重放。

**前置依赖：** B2 会话/定位，B3 文档/变量，B1 事件/资源互斥。

**源码与目标：** WebRPA `recorder.py`、录制注入和确认逻辑；目标为 `domain/workflows/recording.py`、`application/workflows/recordings.py`、`providers/browser/recording.py`、`infrastructure/process/recording_worker.py`、`infrastructure/database/workflow_recordings.py`、`adapters/http/workflow_recordings.py`。

**接口与数据：** 实现现有 `/api/recorder/start|stop|events|status` 与 `/api/recorder/reviews/{documentId}`；确认步骤和审查 revision 持久化，页面对象、Cookie、登录态和注入句柄不持久化。

**估计：** 开发 12–22 工程日；验证 10–18 工程日；外部等待 0–5 工程日用于不同 CloakBrowser/输入法环境。置信度低。

- [ ] Task B7.1：先用真实浏览器验证当前/未来文档注入、中文输入法、跨域 iframe、刷新/导航尾部确认和页面关闭，记录冻结行为。
- [ ] Task B7.2：实现会话、稳定命令、确认序号、步骤分页、暂停/恢复/停止、重连和崩溃恢复；已确认步骤持久化，手动动作不重放。
- [ ] Task B7.3：实现审查 revision、步骤编辑、导航歧义、密码待补、变量化、定位测试和生成预览；迟到响应绑定会话/页面/修订。
- [ ] Task B7.4：整批加入画布为一次可撤销操作；生成不自动保存工作流。
- [ ] Task B7.5：验证单值 1 MiB、单录制 10,000 步/64 MiB、磁盘失败和清理重试；达限明确暂停，不截断后继续。
- [ ] Task B7.6：正式 UI 完成录制→审查→生成→保存重开→关闭原浏览器→独立运行，关闭 `BE-B7-001` 至 `007`。

**B7 退出门槛：** 独立运行副作用与录制一致；异常尾部如实标记；关闭清理后才释放互斥资源；不保存 Cookie、登录态或会话页面 ID。

---

## B8：Debug、诊断、日志结果与恢复

**用户结果：** 用户能在复杂流程中断点暂停、单步、继续、查看/修改运行变量、从指定位置调试、保留失败现场，并搜索、分页、补读和导出历史诊断。

**前置依赖：** B3 多次调度上下文，B1 worker 命令通道，B7/B2 页面会话能力。

**源码与目标：** 冻结执行事件、监控与原调试行为；目标为 `domain/workflows/debug.py`、`application/workflows/debug.py`、`infrastructure/database/workflow_debug.py`、`infrastructure/filesystem/workflow_diagnostics.py`、`adapters/http/workflow_debug.py`，并扩展已有 worker 的单一命令读取方。

**接口与数据：** 实现现有 `/api/workflows/{id}/debug/*`、`/api/workflow-runs/{runId}/logs|results|variable-tracking*` 和编号事件；命令、检查点、变量差量和大值引用分别持久化，筛选游标与实时事件游标不混用。

**估计：** 开发 12–20 工程日；验证 10–16 工程日；外部等待无。置信度中低。

- [ ] Task B8.1：实现 pausing/paused/failed_paused 状态、pauseId/controlRevision/commandId、节点前边界暂停和可中断心跳。
- [ ] Task B8.2：实现断点、继续、一次调度单步、顶层直接起跑和嵌套运行至此；未选分支不伪造命中。
- [ ] Task B8.3：实现变量检查点、差量变化、大值诊断文件和暂停时原子修改；循环局部变量只读。
- [ ] Task B8.4：失败暂停保留浏览器；结束调试清理后仍记 failed，普通暂停停止记 cancelled。
- [ ] Task B8.5：实现日志全文搜索、级别/节点/executionId 筛选、游标分页、SSE 补读和固定截止序号导出。
- [ ] Task B8.6：验证 1,000 轮、10,000 日志、64 KiB 以上变量、响应丢失、迟到命令、停止竞争、sidecar 崩溃与重连。
- [ ] Task B8.7：正式 UI 完成复杂调试闭环并重开历史，关闭 `BE-B8-001` 至 `007`。

**B8 退出门槛：** 单步一次只调度一次；人工变量修改影响真实网页结果且有诊断记录；失败现场按规则保留/清理；分页和导出内容、数量、哈希一致。

---

## B9：227 节点总验收、正式包和后端交接

**用户结果：** 正式 AutoFlow 包中的 Studio 在当前范围内不再依赖 Mock 或冻结源码，前端入口与真实后端业务链路完整，升级、退出和异常恢复有证据。

**前置依赖：** B1–B8 的功能块关闭；正式数据库副本、目标平台和外部凭据按对应节点验收要求可用。

**估计：** 开发修复 5–15 工程日；验证 12–25 工程日；外部等待未知，取决于 macOS Intel、Windows、打印/系统能力和第三方凭据。置信度低。

- [ ] Task B9.1：执行映射检查，227 项、681 条逐节点用例无遗漏；共享用例引用不重复计为节点真实证据。
- [ ] Task B9.2：运行完整后端 `cd apps/backend && uv run pytest -q`、`uv run ruff check src tests`、`uv run mypy src`。
- [ ] Task B9.3：运行前端合同回归、`npm test`、`npm run typecheck`、`npm run lint`、`npm run openapi:check` 和 `npm run build`。
- [ ] Task B9.4：冻结 PyInstaller sidecar，运行启动/迁移/执行/停止 smoke；扫描包内 import、路径和字符串，确认不读取 `reference/WebRPA`、Mock 或开发端口。
- [ ] Task B9.5：正式 Electron 通过真实点击、输入、快捷键和原生对话框运行保存、执行、Debug、拾取、录制、日志导出与离开矩阵。
- [ ] Task B9.6：在正式数据库只读副本完成升级演练并比较数据哈希；实际用户数据库升级是独立发布操作，本计划不自动执行。
- [ ] Task B9.7：macOS arm64、macOS Intel、Windows 分平台登记；未取得机器或依赖时保持未验收，不用平台分支模拟替代。
- [ ] Task B9.8：更新 `capabilities.json`、`backend-support-mapping.json`、`studio-backend-migration-validation.md` 与 `backend-handoff.md`，列出真实后端通过、外部等待和明确排除。

**B9 完成门槛：** 227 个节点的 source-parity、contract、real-execution 均有可复查证据；共享矩阵全部通过；无遗留进程、锁、监听端口或伪造终态；正式包不依赖 Mock/冻结源码；未测平台或外部依赖不得被标为完成。

---

## 各里程碑强制异常与恢复矩阵

下表是每个里程碑的最低场景，不替代 [后端验收矩阵](../../migration/studio-backend-migration-validation.md) 中的详细用例。

| 里程碑 | 正常链路 | 失败 | 取消/停止 | 重连/重启 | 幂等 | 清理 |
|---|---|---|---|---|---|---|
| B0 | 四类数据库起点升级到唯一 head | 注入迁移失败、未知 revision、只读源 | 迁移前取消不写目标 | 重启后重复 migrate | 重复 upgrade 不变 | 临时副本和失败目标可删除，原库哈希不变 |
| B1 | 五节点保存、重开、运行、日志/产物 | 保存冲突、节点失败、磁盘/License/Profile 错误 | 导航/输入/截图中停止 | SSE 补读；遗留 run 标 interrupted | runId/保存 request ID | browser、worker、Profile/内核/工作区锁 |
| B2 | 30 节点与拾取闭环 | 非法选择器、页/框架失效、下载/网络失败 | 拾取、等待、下载中取消 | 会话状态查询恢复；崩溃不恢复页面 | sessionId/requestId | 注入监听、高亮、页面、浏览器和资源锁 |
| B3 | 条件/循环/并行/子流程/模块 | 交叉图、缺变量、循环依赖、模块缺失 | 算法循环和并行分支停止 | 运行事件补读；崩溃不重跑分支 | runId、模块 revision 写 | 子任务、局部 scope、运行资源和临时快照 |
| B4 | 88 数据节点及文件往返 | 类型、编码、越界、磁盘错误 | CPU/序列化检查点取消 | 重连读取已提交结果 | 节点不因查询重跑；导出 request ID | 临时文件、半成品和大值引用 |
| B5 | AI 节点、MCP、LangGraph 多轮工具 | 模型不支持、限流、工具/MCP 错误 | 模型流、图和工具取消 | checkpoint 恢复并查询原工具 | assistant/tool commandId | 模型流、MCP 会话、检查点锁和临时产物 |
| B6 | 触发、计划和外部集成 | 网络、凭据、平台不可用、端口冲突 | 在途请求、脚本、分享停止 | 服务重启不重放历史触发 | trigger event ID、commandId | SSH/SMTP/socket/子进程/临时文件 |
| B7 | 录制、审查、生成、独立重放 | 导航尾部、磁盘、容量、页面崩溃 | 暂停/恢复/停止/关闭 | 按确认序号补读，手动动作不重放 | sessionId/commandId/review revision | 注入器、浏览器、步骤缓冲和资源锁 |
| B8 | 断点、单步、变量修改、诊断导出 | failed_paused、过期命令、大值缺失 | 当前动作或暂停等待中停止 | pause/command 查询与事件补读 | commandId/pauseId/controlRevision | 失败现场结束、浏览器、诊断临时文件和锁 |
| B9 | 正式包全链和数据副本演练 | 包依赖、平台、升级、合同漂移 | 退出/换区全矩阵 | 正式 sidecar 崩溃与重启 | 全服务稳定 ID 回归 | PID、端口、锁、临时目录与敏感导出扫描 |

---

## 第一阶段可直接执行的任务清单

按以下顺序执行，常规步骤不等待产品确认：

1. B0.1 建立映射防漂移测试和证据输出。
2. B0.2 从 `f573a44` 原样恢复四个 revision，新增 `0011_merge_android_project_data`，用临时库验证唯一 head。
3. B0.3 完成只读副本检查工具；没有用户副本时只登记外部等待，不阻塞临时工作区的 B1。
4. B1.1 完成文档领域、仓储与真实保存 API 所需用例。
5. B1.2 迁入执行器注册、图解析和变量内核；冻结差分通过后才写网页执行器。
6. B1.3 打通 Profile 冻结、CloakBrowser 会话和受管 worker，先完成启动/停止/异常清理。
7. B1.4 逐个迁入五节点并用受控页面核验真实副作用。
8. B1.5–B1.6 接入运行持久化、日志/产物、HTTP/SSE 和 OpenAPI。
9. B1.7 通过正式 Electron 核心链路后关闭 B1，再启动 B2。

第一阶段不包含：其余 222 个节点、录制、Debug、外部供应商实测、正式用户数据库实际升级。它们不能被 B1 的五节点结果提前核销。

## 产品决策与阻塞项

需要用户决定的真实产品冲突：**无**。项目负责人已确认本项目范围内的 WebRPA 源码使用和迁入授权；不把该确认解释成具体商业授权或公开发布授权。来源、上游许可证和修改记录继续作为每个迁入提交的门槛。

当前阻塞只影响相应验收，不影响准备文档：

- 正式用户数据库副本尚未用于 B0 只读升级演练；因此正式数据接入保持阻塞，临时工作区开发不受影响。
- CloakBrowser 在当前平台的 License、已安装内核及跨平台机器可用性需在 B1/B2/B9 开始时探测。
- 第三方 AI、MCP、通知、邮件、SSH、打印和系统能力的真实凭据/设备可用性未知；本地受控服务只能验收合同，不能核销真实外部执行。

发现新的合同冲突时，必须提交冻结源码路径/行号、前端字段、无法兼容的具体行为、影响节点和最小修正建议；在此之前不得自行改变原版语义或删减前端功能。
