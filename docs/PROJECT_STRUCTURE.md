# AutoFlow 项目目录结构

- 日期：2026-09-13
- 状态：目录骨架与已实现领域的职责索引；空占位目录不代表功能已经实现。
- 依据：用户要求预设目录；`docs/architecture/README.md` 已批准架构与当前运行工程。

## 路径基准

后端继续使用 `apps/backend/src/autoflow`，桌面端继续使用 `apps/desktop/src`。不新增 `apps/sidecar`、根目录 `services` 或根目录 `infrastructure`。

迁移规格 `docs/superpowers/specs/2026-09-11-autoflow-feature-migration-design.md` 第 3 节与此基准存在路径冲突，进入业务实施前须由主任务统一规格；本次没有修改该规格。

正式前端领域使用 `renderer/domains`。`renderer/shared/components/ui` 已是经过交互测试的正式 shadcn/Radix 基础组件层；`renderer/features/profiles` 的旧 mock 草稿由浏览器页面接入任务替换，不再作为功能入口。此前把两者一并标为“未提交草稿”的描述已 superseded。

`packages/ui` 仍只是目录骨架，尚未注册独立 workspace。当前实际使用的 shadcn/Radix 组件位于桌面端 `renderer/shared/components/ui`，Tailwind 主题位于 `renderer/styles/index.css`。OpenAPI 类型继续生成到 `renderer/shared/api/generated.ts`，不维护第二套 contracts 包。

## 骨架概览

```text
apps/
├── backend/
│   ├── src/autoflow/
│   │   ├── bootstrap/
│   │   ├── domain/{profiles,proxies,kernels,models,settings,workflows,projects}/
│   │   ├── application/{profiles,proxies,kernels,models,settings,dashboard,workflows,projects}/
│   │   ├── adapters/{http,events}/
│   │   ├── infrastructure/{database,filesystem,credentials,process,events}/
│   │   └── providers/{browser,proxy,kernel,model,platform}/
│   └── tests/{unit,integration,contract,fixtures}/
└── desktop/
    ├── src/
    │   ├── main/{sidecar,ipc,platform,settings}/
    │   ├── preload/
    │   ├── shared/                     # main/preload/renderer 的桌面 IPC 契约
    │   └── renderer/
    │       ├── app/
    │       ├── domains/{profiles,proxies,kernels,models,settings,dashboard,workflows,projects}/
    │       │   └── 每个领域：components/、hooks/、pages/、tests/
    │       ├── shared/{api,components,hooks,lib}/
    │       └── styles/
    └── tests/{e2e,fixtures}/
packages/ui/
├── src/{components,layouts,styles}/
├── tests/
└── examples/
.ai/{memory,knowledge,decisions,plans,sessions}/
docs/{architecture,migration,automation-studio,references,superpowers}/
scripts/
reference/
.github/workflows/
```

花括号为并列目录的缩写。下表逐项列出实际路径及职责，包含已存在目录和本次补齐的目录。

## 目录职责清单

| 目录 | 职责 |
| --- | --- |
| `.ai/decisions/` | 架构决策记录；说明背景、取舍和替代关系。 |
| `.ai/knowledge/` | 带来源和验证方式的技术知识、排错经验。 |
| `.ai/memory/` | 稳定事实与用户已确认偏好。 |
| `.ai/plans/` | 计划索引、阶段状态；正式规格与实施计划仍放 docs/superpowers，避免维护两份正文。 |
| `.ai/sessions/` | 阶段交接、验证结果、未决项和下一步。 |
| `.github/workflows/` | 持续集成与各平台构建检查。 |
| `apps/backend/src/autoflow/adapters/events/` | 进度与状态事件的传输序列化。 |
| `apps/backend/src/autoflow/adapters/http/` | FastAPI 路由、请求响应与错误映射；不直接操作数据库。 |
| `apps/backend/src/autoflow/application/` | 业务用例、跨领域协调和事务边界。 |
| `apps/backend/src/autoflow/application/dashboard/` | 总览聚合查询；没有独立 dashboard 实体时不建立领域模型。 |
| `apps/backend/src/autoflow/application/kernels/` | 内核的用例；通过端口使用外部能力。 |
| `apps/backend/src/autoflow/application/models/` | 模型供应商和模型目录的用例；通过端口使用外部能力。 |
| `apps/backend/src/autoflow/application/profiles/` | 浏览器配置的用例；通过端口使用外部能力。 |
| `apps/backend/src/autoflow/application/proxies/` | 代理和代理池的用例；通过端口使用外部能力。 |
| `apps/backend/src/autoflow/application/settings/` | 设置的用例；通过端口使用外部能力。 |
| `apps/backend/src/autoflow/bootstrap/` | 配置、启动、生命周期和依赖装配。 |
| `apps/backend/src/autoflow/domain/` | 纯业务实体、值对象、规则、错误和必要端口。 |
| `apps/backend/src/autoflow/domain/kernels/` | 内核的业务规则和必要端口。 |
| `apps/backend/src/autoflow/domain/models/` | 模型供应商和模型目录的业务规则和必要端口。 |
| `apps/backend/src/autoflow/domain/profiles/` | 浏览器配置的业务规则和必要端口。 |
| `apps/backend/src/autoflow/domain/proxies/` | 代理和代理池的业务规则和必要端口。 |
| `apps/backend/src/autoflow/domain/settings/` | 设置的业务规则和必要端口。 |
| `apps/backend/src/autoflow/infrastructure/credentials/` | 系统凭据存储适配。 |
| `apps/backend/src/autoflow/infrastructure/database/` | 连接、会话、事务和持久化实现。 |
| `apps/backend/src/autoflow/infrastructure/database/migrations/` | Alembic 元数据环境与浏览器资源首个可重复迁移。 |
| `apps/backend/src/autoflow/infrastructure/database/profiles.py` | ProfileSpec 的 SQLAlchemy 映射与仓储实现。 |
| `apps/backend/src/autoflow/infrastructure/database/proxy_options.py` | 代理/代理池本地资源查询适配器。 |
| `apps/backend/src/autoflow/infrastructure/database/migrations/versions/` | 已启用的 Alembic 增量迁移脚本；M1 在 0004 后新增 0005_workflow_documents。 |
| `apps/backend/src/autoflow/infrastructure/database/repositories/` | 按领域命名的仓储实现；ORM 不向领域层泄漏。 |
| `apps/backend/src/autoflow/infrastructure/events/` | 进程内事件分发实现。 |
| `apps/backend/src/autoflow/infrastructure/filesystem/` | 路径、文件和缓存目录操作。 |
| `apps/backend/src/autoflow/infrastructure/process/` | 进程、超时、取消和资源回收。 |
| `apps/backend/src/autoflow/providers/browser/` | 浏览器控制实现。 |
| `apps/backend/src/autoflow/providers/kernel/` | 内核来源、下载和安装实现。 |
| `apps/backend/src/autoflow/providers/model/` | 外部模型供应商连接与能力实现。 |
| `apps/backend/src/autoflow/providers/platform/` | Python 所需的平台能力；凭据和文件操作仍归各自 infrastructure 目录。 |
| `apps/backend/src/autoflow/providers/proxy/` | 代理连接与探测实现。 |
| `apps/backend/tests/contract/` | HTTP schema、错误和 OpenAPI 契约测试。 |
| `apps/backend/tests/fixtures/` | 脱敏样本和测试输入。 |
| `apps/backend/tests/integration/` | 真实临时数据库、迁移和仓储测试。 |
| `apps/backend/tests/unit/` | 纯规则、用例和隔离适配测试。 |
| `apps/desktop/src/main/ipc/` | 有明确输入输出的 IPC handler；禁止任意文件或进程命令。 |
| `apps/desktop/src/main/ipc/automation-studio.ts` | 正式工作流工作台的单窗口生命周期、离开握手和刷新保护；同 renderer 产物的独立 StudioApp 入口。 |
| `apps/desktop/src/main/platform/macos/` | 必要的 macOS 桌面适配。 |
| `apps/desktop/src/main/platform/windows/` | 必要的 Windows 桌面适配。 |
| `apps/desktop/src/main/sidecar/` | 本地后端启动、就绪、恢复和退出监管。 |
| `apps/desktop/src/preload/` | 受控桌面能力桥接。 |
| `apps/desktop/src/shared/automation-studio.ts` | 工作台开窗、离开确认与编辑锁定的固定桌面 IPC 类型契约。 |
| `apps/desktop/src/renderer/app/` | 应用入口、路由、装配、全局错误和服务恢复。 |
| `apps/desktop/src/renderer/domains/` | 正式业务组件和页面；按已批准架构使用 domains。 |
| `apps/desktop/src/renderer/domains/dashboard/` | 总览前端模块；请求封装 api.ts 和必要 model.ts 在实际实现时添加。 |
| `apps/desktop/src/renderer/domains/dashboard/components/` | 总览领域组件；使用共享 UI，不承载跨领域基础设施。 |
| `apps/desktop/src/renderer/domains/dashboard/hooks/` | 总览的查询、变更和交互状态组合。 |
| `apps/desktop/src/renderer/domains/dashboard/pages/` | 总览页面组合；组件完成后再组装页面。 |
| `apps/desktop/src/renderer/domains/dashboard/tests/` | 总览跨组件场景测试；局部单元测试也可与源码相邻。 |
| `apps/desktop/src/renderer/domains/kernels/` | 内核前端模块；请求封装 api.ts 和必要 model.ts 在实际实现时添加。 |
| `apps/desktop/src/renderer/domains/kernels/components/` | 内核领域组件；使用共享 UI，不承载跨领域基础设施。 |
| `apps/desktop/src/renderer/domains/kernels/hooks/` | 内核的查询、变更和交互状态组合。 |
| `apps/desktop/src/renderer/domains/kernels/pages/` | 内核页面组合；组件完成后再组装页面。 |
| `apps/desktop/src/renderer/domains/kernels/tests/` | 内核跨组件场景测试；局部单元测试也可与源码相邻。 |
| `apps/desktop/src/renderer/domains/models/` | 已实现模型供应商和模型目录；api.ts 使用生成 DTO，cache.ts 处理冲突刷新，provider-catalog.ts 固定预设。 |
| `apps/desktop/src/renderer/domains/models/components/` | 模型供应商和模型目录领域组件；使用共享 UI，不承载跨领域基础设施。 |
| `apps/desktop/src/renderer/domains/models/hooks/` | 模型供应商和模型目录的查询、变更和交互状态组合。 |
| `apps/desktop/src/renderer/domains/models/pages/` | 模型供应商和模型目录页面组合；组件完成后再组装页面。 |
| `apps/desktop/src/renderer/domains/models/tests/` | 模型供应商和模型目录跨组件场景测试；局部单元测试也可与源码相邻。 |
| `apps/desktop/src/renderer/domains/profiles/` | 浏览器配置模块；api.ts 封装请求，hooks.ts 组合查询/变更，form-schema.ts 管理表单与生成 DTO 的转换。 |
| `apps/desktop/src/renderer/domains/profiles/components/` | 浏览器配置领域组件；使用共享 UI，不承载跨领域基础设施。 |
| `apps/desktop/src/renderer/domains/profiles/hooks/` | 浏览器配置的查询、变更和交互状态组合。 |
| `apps/desktop/src/renderer/domains/profiles/pages/` | 浏览器配置页面组合；组件完成后再组装页面。 |
| `apps/desktop/src/renderer/domains/profiles/tests/` | 浏览器配置跨组件场景测试；局部单元测试也可与源码相邻。 |
| `apps/desktop/src/renderer/domains/proxies/` | 代理和代理池前端模块；请求封装 api.ts 和必要 model.ts 在实际实现时添加。 |
| `apps/desktop/src/renderer/domains/proxies/components/` | 代理和代理池领域组件；使用共享 UI，不承载跨领域基础设施。 |
| `apps/desktop/src/renderer/domains/proxies/hooks/` | 代理和代理池的查询、变更和交互状态组合。 |
| `apps/desktop/src/renderer/domains/proxies/pages/` | 代理和代理池页面组合；组件完成后再组装页面。 |
| `apps/desktop/src/renderer/domains/proxies/tests/` | 代理和代理池跨组件场景测试；局部单元测试也可与源码相邻。 |
| `apps/desktop/src/renderer/domains/settings/` | 设置前端模块；请求封装 api.ts 和必要 model.ts 在实际实现时添加。 |
| `apps/desktop/src/renderer/domains/settings/components/` | 设置领域组件；使用共享 UI，不承载跨领域基础设施。 |
| `apps/desktop/src/renderer/domains/settings/hooks/` | 设置的查询、变更和交互状态组合。 |
| `apps/desktop/src/renderer/domains/settings/pages/` | 设置页面组合；组件完成后再组装页面。 |
| `apps/desktop/src/renderer/domains/settings/tests/` | 设置跨组件场景测试；局部单元测试也可与源码相邻。 |
| `apps/desktop/src/renderer/shared/api/` | 现有 OpenAPI 类型生成落点、请求客户端和错误归一化。 |
| `apps/desktop/src/renderer/shared/components/` | 应用专用、与领域无关的展示组件。 |
| `apps/desktop/src/renderer/shared/hooks/` | 不含领域查询语义的共享 React hooks。 |
| `apps/desktop/src/renderer/shared/lib/` | 有明确职责的共享函数；不作为杂物目录。 |
| `apps/desktop/src/renderer/styles/` | 现有应用全局样式入口；组件库令牌未来由此引入。 |
| `apps/desktop/tests/e2e/` | 真实 Electron 与 sidecar 的用户流程。 |
| `apps/desktop/tests/fixtures/` | 桌面端脱敏测试数据。 |
| `docs/architecture/` | 批准的运行边界、依赖方向和基础验证报告。 |
| `docs/automation-studio/` | 自动化编排的研究与历史方案；正式 M1 范围和验收以 superpowers 规格与 migration 记录为准。 |
| `docs/migration/` | 能力清单、来源对应、迁移状态和验收证据。 |
| `docs/references/` | 外部资料与来源记录。 |
| `docs/superpowers/plans/` | 正式实施计划。 |
| `docs/superpowers/specs/` | 正式设计规格。 |
| `packages/ui/examples/` | 组件展示与用法示例；页面开发前验证组件状态。 |
| `packages/ui/src/components/` | 计划中的 shadcn/ui 基础控件和跨领域通用组合控件。 |
| `packages/ui/src/layouts/` | 跨领域工作台布局基元；不包含业务导航配置。 |
| `packages/ui/src/styles/` | 计划中的 Tailwind 主题、设计令牌和组件样式。 |
| `packages/ui/tests/` | 组件交互、可访问性和状态测试。 |
| `reference/` | 上游源码保持只读，不作为运行时依赖；`redroid-demo/` 是用户授权的独立 Python + React 管理 Demo，自有源码由主仓库跟踪；Android / Windows / root 实机验收状态见其 `VERIFICATION.md`。 |
| `scripts/` | 现有构建、类型生成、冒烟和仓库验证脚本。 |

## 依赖与维护规则

### 代理模块实施补充（2026-09-12，confirmed）

代理领域实现已从 `codex/proxy-management@0ad2fd2` 选择性接入浏览器主线。完整接口、验证结果和限制见 [代理模块实施状态](migration/proxy-management-status.md)。

- `application/proxies/facade.py`：事务边界与代理用例入口；HTTP adapter 不直接构造仓储。
- `infrastructure/database/proxy_models.py`：代理扩展 ORM；复用现有 `proxies` / `proxy_pools` 的主键，不改写 `models.py` 中浏览器资源模型。
- `infrastructure/database/proxies.py`：代理 SQLAlchemy 仓储与 Unit of Work。
- `providers/proxy/proxypanel.py`：固定官方地址的受控 HTTP 传输，验证真实列表/分协议端点/到期字段/按需凭据；未知列表包装拒绝更新投影。
- `application/proxies/credential_loader.py`：按授权操作读取数据面凭据，检查连接/投影版本与端点一致性，只返回内存值，供探测和 host-only 复制复用。
- `providers/proxy/probe.py`：经过指定代理的固定 HTTPS 健康探针。
- `domain/credentials.py` 与 `infrastructure/credentials/system.py`：原生系统凭据端口和适配器，供内核模块复用。
- `bootstrap/proxies.py`：代理服务、数据库、Provider、凭据与 HTTP 装配。
- `adapters/http/internal_proxy_credentials.py`：仅桌面主进程可以调用的取密通道，不进入 OpenAPI。
- `renderer/domains/proxies/`：生成契约的 API facade、交互 hooks、领域组件与页面组合；基础控件复用 `shared/components/ui`。
- `scripts/preview-proxies.mjs` 与 `renderer/proxy-preview.*`：不改动主应用 App 的独立开发预览，连接独立数据目录的真实本地 sidecar。

- 后端依赖：`adapters → application → domain`；`infrastructure/providers` 实现领域端口，`bootstrap` 装配具体实现。业务规则不依赖 FastAPI、ORM 或平台 SDK。
- 前端顺序：设计令牌 → 基础控件 → 通用布局 → 领域组件 → 页面。`packages/ui` 不依赖业务领域；页面使用领域 hooks，hooks 经共享客户端调用 API。
- `domain/proxies` 同时管理代理与代理池；`domain/models` 同时管理供应商与模型目录，避免为每张表建立独立模块。
- HTTP adapter 先使用按领域命名的文件，只有职责确实需要拆分时再建立子目录；不预生成空 service、repository 或类型文件。
- 项目管理范围已获完整确认；PM0只创建契约和验收资产，业务目录按对应里程碑首次真实交付时建立，禁止整片空骨架。Studio维护唯一文档与执行核心。
- 空目录使用 `.gitkeep` 保留；首次加入真实文件时删除该占位。占位目录不会自动成为可运行 Python 包或 npm workspace。
- Agent 新增、移动、删除目录或改变职责时，须在同一变更更新本文档；新增边界或解决路径冲突时同步记录 `.ai/decisions/`。
- `.ai/plans` 维护索引与状态，正式计划在 `docs/superpowers/plans`，不要复制正文造成漂移。
- `node_modules`、Python 虚拟环境、构建产物、运行时数据库、缓存及用户凭据不属于源码骨架；继续遵循现有忽略规则和平台数据目录。

## 模型管理实现（2026-09-12）

- `domain/models` 定义值对象/实体/端口/URL规则；`application/models/service.py` 协調接入、更新、测试和凭据清理。
- `infrastructure/database/model_providers.py` 实现仓储与原子条件写；迁移 `0002_model_management.py` 增加供应商、模型和cleanup intent三表。
- `providers/model/http.py` 使用httpx实现协议请求；不依赖ORM或GUI。
- `renderer/domains/models/assets/brands/` 保存核验后的供应商品牌原始 SVG/PNG、来源与许可；`provider-icons.ts` 以静态 URL 随应用打包，不再使用旧 Base64 图标或通用占位冒充品牌。components先于pages，hooks管理查询和选择状态。
- 缓存入口已统一为 `renderer/app/ApiProvider.tsx`（此前 `query-provider.tsx` 入口描述 superseded）；握手更新 API 与查询缓存，同一工作区重连不卸载编辑组件，实际切换工作区才重置。共享 Modal/Menu 仍位于 desktop shared，packages/ui 尚非独立 workspace。
- `scripts/electron-cdp.mjs` 是桌面冒烟的调试连接助手；`smoke-model-management.mjs` 用临时目录与本地fixture执行完整UI闭环。
- 实现及平台证据见 [模型管理验收](migration/model-management-verification.md)。

### 模型合并补充（2026-09-12，confirmed）

`0003_merge_proxy_models.py` 汇合代理/模型两条历史迁移，保持唯一head；`test_merged_model_migrations.py` 验证四种数据库起点。HTTP客户端同时支持现有代理与模型错误字段，Electron保留代理复制与内核目录IPC。详见 [baseline合并验收](migration/model-management-baseline-merge.md)。

## 设置与总览实现（2026-09-12，confirmed）

- `main/settings/store.ts`：固定 userData 本机偏好、原子写入/备份、工作区标记与路径校验。
- `main/settings/controller.ts`：服务重启、工作区切换/回退、受控目录打开、白名单诊断预览与保存；平台行为留在 main。
- `main/ipc/settings.ts` 与 `src/shared/settings.ts`：窗口来源校验及跨 main/preload/renderer 的受控类型契约。
- `application/settings/runtime.py`：当前轻量 runtime/总览查询协调与 quiesce 门控；复用同一个只读资源仓储，没有额外 dashboard 实体或重复服务层。
- `infrastructure/database/settings_runtime.py`：真实资源计数、数据库任务及配置占用读取；`adapters/http/settings_dashboard.py` 提供公开查询和 host-only 内部控制。
- `renderer/domains/settings/`：IPC 设置页、卡片、工作区确认与诊断弹窗；`domains/dashboard/`：生成 API 类型的总览查询、资源卡片和工作入口。
- `renderer/app/ApiProvider.tsx`：统一领域 QueryClient，凭据/实例变化替换上下文与缓存；App 按工作区根设置 key，同工作区重连保持组件树，实际切换工作区重置。
- `renderer/public/brand/autoflow-mark.png`：沿用旧项目 renderer/public/brand 的 AutoFlow 品牌资源。
- 详细范围和证据见 [设置与总览实施状态](migration/settings-dashboard-status.md)。

## 浏览器配置与内核实现边界（2026-09-12，confirmed）

- `domain/profiles`、`application/profiles`、`adapters/http/profiles.py` 与数据库仓储分别负责规则、用例、HTTP 契约及持久化；配置目录删除具有占用检查、隔离删除和恢复策略。
- `infrastructure/filesystem/profile_environment.json` 维护浏览器语言/时区目录及 UA 模板，`profile_environment.py` 读取并检查结构；bootstrap 注入 profiles HTTP 查询，前端 `EnvironmentOptionField` 展示全量候选和自定义输入，UA 模板按所选内核主版本展开。维护方式见 `docs/migration/profile-environment-options.md`。
- `providers/kernel` 适配锁定的 CloakBrowser wrapper；`infrastructure/process/kernel_worker.py` 监管隔离 worker、下载取消、原子安装和恢复，`adapters/events/kernels.py` 提供带鉴权的状态快照。
- `renderer/domains/profiles/components` 包含共享字段区块与配置弹窗；`domains/kernels/components` 提供从配置表单进入的内核管理弹窗，无独立内核导航。
- 列表与表单使用生成的 API 类型、TanStack Query、React Hook Form 和 Zod；内核任务缓存同时处理 HTTP/SSE 乱序，页面不直接访问 SQL、凭据或文件系统。
- `scripts/smoke-browser-management.mjs` 验证 source/frozen worker 和真实 HTTP 配置闭环；冻结时区检查显式禁用系统 zoneinfo，以验证随包 tzdata。
- 实施与平台证据以 [浏览器管理验收记录](migration/browser-management-validation.md) 为准；其未运行项目不得视为已验收。

## 配置临时测试浏览器（2026-09-12，confirmed）

- 浏览器配置只保存可复用参数和指纹种子；项目环境中的持久化实例属于后续模块，本功能不创建实例表或保存登录状态。
- `application/profiles/test_browser.py` 协调读取已保存配置、选择已安装内核、解析代理凭据并调用启动端口；HTTP 仍由 `adapters/http/profiles.py` 提供，类型通过 OpenAPI 生成。
- `infrastructure/process/test_browser_worker.py` 管理临时测试工作进程及回收；`bootstrap/test_browser_worker.py` 提供源代码/冻结共用入口；`providers/browser/worker.py` 适配 CloakBrowser 非持久化上下文。平台路径、环境和进程行为不进入 React 或 domain。
- `providers/browser/proxy_relay.py` 为单个测试会话转发 HTTP/SOCKS5 认证代理；浏览器只接收无凭据的本地地址，认证信息留在 worker 内存与上游认证握手中。Windows Job Object 和 POSIX 进程组回收集中在进程适配器。
- `renderer/domains/profiles/components/ProfileCard.tsx` 是配置卡片领域组件，`ProfileList.tsx` 负责双列布局，页面只组合查询和操作。测试启动/关闭按卡片记录等待和错误，运行态通过每秒查询后端同步，包含原生关窗；每份配置仅一个会话，重置结果直接更新 seed 缓存。
- 决策及验证边界见 `.ai/decisions/2026-09-12-profile-test-browser.md` 和对应会话记录。

## 代理位置与轮换实现（2026-09-12，confirmed）

- `domain/proxies/remote.py`：远程状态、目标地点、轮换计划、命令记录及 Provider/仓储端口。
- `providers/proxy/remote_mapping.py`：严格解析详情、公共地点目录与计划，分离运行条件与证据来源；`proxypanel.py` 只调用固定 v1 路径，不重试写入。
- `application/proxies/remote_controls.py`：命令登记、单次发送、限时只读确认、取消和未知结果核实；没有额外调度服务。
- `infrastructure/database/proxy_operations.py`：持久化去重与同代理排他；`0004_proxy_remote_controls.py` 在唯一 0003 head 上增量迁移。
- `adapters/http/proxy_remote.py`：位置与轮换 HTTP 路由和安全操作摘要；旧 placeholders 已移除。
- `renderer/domains/proxies/components/{LocationPicker,RotationScheduleForm,ProxyOperationStatus,ProxyRemoteControls}.tsx`：独立领域组件，由现有详情抽屉组合；`hooks/useProxyRemoteControls.ts` 处理读取、命令状态、限流和恢复。
- 验证证据及尚未执行的实网写入项目见 [远程控制验收](migration/proxy-remote-controls-verification.md)。

## 工作流编排 M1（2026-09-13，confirmed）

- `domain/workflows/{models,catalog,validation}.py`：自有文档、六节点目录、结构与草稿诊断；不依赖 React Flow、HTTP、数据库或浏览器。
- `application/workflows/service.py`：文档用例和仓储端口；`infrastructure/database/workflows.py` 实现 SQLite 幂等创建、revision CAS 和文档/布局原子写入。`0005_workflow_documents.py` 为增量迁移。
- `adapters/http/workflows.py` 与 `workflow_schemas.py`：最小目录/列表/创建/读取/保存 API，复用鉴权、停写和错误包；类型生成到现有 `renderer/shared/api/generated.ts`。
- `renderer/domains/workflows/components/`：动作库、画布、专用属性表单和变量面板；`hooks/useWorkflowEditor.ts` 管理文档历史和保存；`pages/StudioPage.tsx` 组合真实交互；`tests/` 集中组件、状态和页面测试。领域根保留 api/types、文档变换、历史和即时诊断。
- `renderer/app/StudioApp.tsx` 是独立工作台入口，`useDesktopSession.ts` 复用主应用连接与恢复逻辑；同工作区重连保留草稿，实际切换工作区才更换文档上下文。旧 `app-state.ts` 已由该共享 hook 替代。
- `shared/runtime.ts` 只给已登记窗口的主 frame 提供运行上下文；编辑、目录管理和凭据权限仍按各自 IPC 边界校验。
- `scripts/smoke-workflow-studio.mjs` 使用真实 Electron/sidecar 与临时工作区验收；支持构建 HTML、`--dev` 开发 URL、`--executable` 打包入口。
- M1 只提供编排编辑与保存，没有执行器、录制、Debug 或模拟运行。详细证据见 [M1 验收记录](migration/automation-studio-m1-validation.md)。

## 项目管理 PM0（2026-09-13，confirmed 实施范围）

- `docs/project-management/design/`：906deda完整设计与历史验证，保持不变；确认状态由`.ai/decisions/`说明。
- `docs/project-management/implementation/contracts.md`：领域对象、版本、18项执行端口、事务和恢复规范；不是当前Python接口实现。
- `docs/project-management/implementation/api-contracts.md`：HTTP投影、命令查询、核心事件及桌面IPC，真实handler与生成类型按阶段交付。
- `docs/project-management/implementation/fixtures.json`：合成领域样例和描述性工作流，非可执行Studio IR。
- `docs/project-management/implementation/{coverage.json,execution-ledger.md}`：全部功能/规则和30包的责任、依赖、计划测试及实际验收状态。
- `docs/project-management/implementation/verify-pm0.py`：只读文档、引用、编号与样例核验；不导入业务模块、不运行数据库或平台验收。
- 后端目标领域为projects/project_data/project_automations/project_runs/environments；前端目标为projects/project-data/project-automations/project-runs/environments；具体F0–F9与组件文件见[总里程碑文件职责](superpowers/plans/2026-09-13-project-management-milestones.md)。均在首次真实功能包创建，不代表本次存在。
- `apps/desktop/src/renderer/shared/components/ui/`仍是统一控件正式落点；UI独立分支1fb58e1由PM1集成，不新建packages/ui workspace。
- 主目录b2e95b3已提交workflows文档CRUD和Studio窗口，PM0没有复制或修改。核心Run、事件补读、检查点按所需能力门槛接入，不从Profile测试浏览器扩展第二引擎。

[PM0执行卡](superpowers/plans/2026-09-13-project-management-pm0.md)和[实际基线](project-management/implementation/current-baseline.md)是后续开工入口。

## 项目管理 PM1 实施落点（2026-09-13）

本段是 PM0 之后的已实现补充。早期“项目管理只有设计”的现状描述已 superseded；后续数据表、批次、环境和生命周期操作仍未实现。

| 实际路径 | 当前职责 |
|---|---|
| `apps/backend/src/autoflow/domain/projects/` | 项目身份、状态、资源默认值、码点校验和仓储端口。 |
| `apps/backend/src/autoflow/application/projects/service.py` | 项目目录、管理命令、打开和操作查询用例。 |
| `apps/backend/src/autoflow/infrastructure/database/projects.py` | SQLite 短事务、唯一名称、CAS 与幂等结果快照；不建立执行器。 |
| `apps/backend/src/autoflow/infrastructure/database/migrations/versions/pm01_projects.py` | 从 `0005_workflow_documents` 派生，新增 projects/project_operations；不修改历史迁移。 |
| `apps/backend/src/autoflow/adapters/http/projects.py`、`project_schemas.py` | 10 项真实 HTTP 操作与 camelCase DTO；bootstrap/app.py 装配。 |
| `apps/desktop/src/renderer/domains/projects/` | api.ts 命令核验、hooks.ts 查询隔离、form-schema.ts 表单值校验。 |
| `apps/desktop/src/renderer/domains/projects/components/` | ProjectFormDialog、ProjectDirectory、ProjectHeader、ProjectTabs、ProjectCapabilityState。 |
| `apps/desktop/src/renderer/domains/projects/pages/` | Directory/Overview 页面组合与 ProjectsWorkspace 草稿、命令、目录位置协调。 |
| `apps/desktop/src/renderer/app/navigation.ts` | 唯一 hash 导航所有者，协调离开确认及前进/后退真实历史位置。 |
| `apps/desktop/src/renderer/shared/components/ui/` | 选择性接入统一 Select、ScrollArea、Table、Pagination、SearchInput 等当前消费者所需控件。 |
| `apps/desktop/src/renderer/styles/tokens.css`、`controls.css` | 暖灰/黏土棕令牌、控件状态和滚动条；index.css 引入，body 不固定 100% 宽度。 |
| `scripts/smoke-project-management.mjs` | 用隔离临时工作区驱动实际 Electron 和 FastAPI，保留构建产物验收截图与事实。 |
| `docs/migration/project-management-pm1-qa/` | 本机截图、运行记录；不是设计原型或其他平台通过证明。 |

PM1 生成类型仍只有 `renderer/shared/api/generated.ts`，平台桥与工作区会话复用现有实现。`packages/ui` 继续是骨架，不建立第二套 UI 包。详见 [PM1 执行卡](superpowers/plans/2026-09-13-project-management-pm1.md)。

## PM2 持久结构（2026-09-13，实施中）

独立分支 codex/project-management-implementation 从 PM1 ef3178a 继续。
`domain/project_data/identity.py` 与 `rules.py` 负责稳定记录身份和标量/字段规则；
`infrastructure/database/project_data_models.py` 定义表、代次、字段、状态、记录、变更证据和影响确认。
`pm02_project_data.py` 从 pm01_projects 派生；历史迁移不修改。
`infrastructure/filesystem/project_excel.py` 仅为可信基础设施路径的 XLSX 适配器，不能直接暴露 renderer 路径。
表资料目录GET/POST、详情GET/PATCH已交付；字段目录GET/POST、状态目录GET/POST/PATCH通过仓储与真实HTTP验证。`application/project_data/catalog.py`协调目录命令，`infrastructure/database/project_data_catalog.py`保存字段、状态与默认回填原子事实，`project_data_impacts.py`保存字段变更确认并在写事务内复验。`adapters/http/project_data_catalog_schemas.py`声明当前目录DTO，统一Operation查询可恢复字段/状态的原始结果。
`renderer/domains/project-data/components`当前包含已审查的数据表目录与表单组件；正式五页签、记录、文件IPC和实际导入发布仍未完成。迁移/领域/目录接口测试不能据此标记完整PM2验收。

### PM2 记录与字段编辑补充（2026-09-13）

`application/project_data/records.py`与领域records端口负责显式记录命令；`infrastructure/database/project_data_records.py`维护内容/状态/关联分离修订、typed身份和原子操作事实。`adapters/http/project_data_records.py`与record_schemas提供真实四接口，`project_data_impacts.py`与impact_schemas提供字段影响确认，原project_data路由PATCH字段。字段修改由catalog在同一写事务内重新核对影响事实。真实生成类型仍只有shared/api/generated.ts。记录查询、删除、批状态、文件IPC和正式页面继续实施；本次命令核验不代表完整数据管理。

### PM2 查询与状态组件（2026-09-13）

`domain/project_data/query.py`负责严格查询表达式和保真类型比较；`application/project_data/queries.py`校验查询身份/分页，`infrastructure/database/project_data_queries.py`在同一SQLite读快照完成过滤、稳定排序和分页，退出前清理连接临时函数。record HTTP集合GET返回真实DataRecordPage；不改变数据库结构。

`renderer/domains/project-data/catalog-api.ts`负责字段/状态真实命令与原操作恢复，`components/StatusEditorDialog.tsx`及status-form-schema维护状态草稿/校验/差异提交。共享记录投影已纠正缺项与null区别。字段/记录编辑器、五页签与文件IPC尚未装配；最新范围核验见pm2-query-editor-verification.json。

### PM2 数据编辑组件与客户端（2026-09-13）

`renderer/domains/project-data/data-command.ts`是表/目录/记录客户端复用的原身份恢复函数；`records-api.ts`连接真实记录查询与命令，完整typed记录身份、固定请求快照和操作结果校验在领域客户端完成。

`scalar-draft.ts`与`components/ScalarValueEditor.tsx`负责保真值和错误控件定位；`field-form-schema.ts`/FieldEditorDialog维护字段规则和影响确认；`record-draft.ts`/RecordEditorDialog冻结原数据比较基线并仅提交实际修改；DataRecordsTable展示真实记录页、状态与服务端分页回调。正式五页签、筛选组件、删除/批状态和受控文件流程仍待接入。最新范围报告为pm2-editors-verification.json，不替代PM2真实应用验收。

## PM2 目录与详情装配增量（2026-09-13，confirmed）

- `renderer/domains/project-data/pages/DataTableDirectoryPage.tsx`：表目录查询、创建/编辑原命令与草稿保护。
- `renderer/domains/project-data/pages/DataTableDetailPage.tsx`：五页签真实读取、记录详情、筛选草稿及代次保护；写入UI单独继续C2c。
- `renderer/domains/project-data/record-query.ts` 和 `components/RecordFilterEditor.tsx`：后端查询语法的草稿验证和编辑，不替代服务端过滤。
- `application/project_data/deletions.py`、`domain/project_data/deletions.py`、`infrastructure/database/project_data_deletions.py`：删除用例、协议和事务/影响持久实现。HTTP适配位于`adapters/http/project_data_deletions.py`及schemas；不在页面自建引用检查。
- `infrastructure/database/migrations/versions/pm02_status_tombstones.py`：状态历史墓碑与活动名称部分唯一；既有历史迁移保持。
- `scripts/smoke-project-data.mjs`：隔离真实目录/详情验收，证据位于`docs/migration/project-data-directory-qa`；不冒充完整数据编辑或PM2验收。


### PM2 修订实现中的持久文件与批量状态（2026-09-13）

- `domain/project_data/status_batches.py` 与 application/database 同名模块：固定引用、按块事务、可恢复批状态；沿用项目Operation。
- `shared/project-files.ts`、`main/project-files/`、preload固定IPC：窗口与服务实例绑定的文件令牌；渲染层不提交任意路径。
- `application/project_data/excel.py` / `database/project_excel_inspections.py`：检查授权与持久检查事实；SQL仅在仓储。
- `application/project_data/excel_import.py` / `database/project_excel_imports.py`：隐藏代次分段写入和短事务发布，复验影响确认及相关变更。
- `application/project_data/excel_export.py` / `database/project_excel_exports.py`：一致读取快照、导出和原目标核验。
- `filesystem/project_excel.py`：工作簿安全读取、新文件无覆盖发布、发布前摘要回调及只读核验；不会修改来源文件。
- 迁移依次为 `pm02_status_batches` → `pm02_excel_inspections` → `pm02_excel_imports` → `pm02_excel_exports`，均追加在已交付 `pm02_status_tombstones` 后。主线Studio `0006_workflow_runs`分叉仍需后续统一集成。
- 上述文件存在不代表完整PM2已验收；原编辑页面任务仍在进行，真实UI接入和全模块验收单独登记。

### PM2 前端组件与验收资产（2026-09-13）

`domains/project-data`新增excel-api、use-excel-inspection/import/export、status-batch-api、use-record-selection及其测试；components新增ExcelImportWizard/Mapping/InspectionPanel、ExcelExportWorkflow/Dialog、RecordStatusBatchDialog、DataOperationStatus、DataTableSourcePanel。DataRecordsTable提供可选选择工具，DataTableDirectoryPage接通真实新表Excel导入。记录批量选择、批量状态、重新导入、导出和来源事实仍需待原编辑任务提交后装配，不能视为已接入。

`scripts/smoke-pm2-excel.mjs`只操纵隔离工作区并记录native picker注入边界；`scripts/measure-pm2-data.py`执行临时文件/DB测量；`scripts/verify-pm2-delivery.mjs`独立核对阶段覆盖，`--require-complete`要求真实全模块验收，当前应失败。历史PM0/PM1报告保留。

### PM2 最终页面装配（2026-09-13，confirmed）

此前“等待原编辑任务”描述为历史状态，已被本节替代。DataTableDetailPage 现组合五页签与真实记录/字段/状态/表资料编辑、冻结选择批量状态、Excel重新导入/导出、来源事实；use-data-table-editing 负责显式写入、稳定作用域的持久原命令恢复、CAS和草稿保护，不在页面重写事务。表查询/列显示/滚动位置按工作区/项目/表保存。

三个新/扩展 smoke 脚本：smoke-project-data.mjs 覆盖编辑与双工作区/重启恢复；smoke-pm2-detail-flows.mjs 覆盖文件和批状态含10000行；smoke-pm2-native-picker.mjs 需实际原生面板操作，不注入其结果。pm2-verification.json 汇总本机证据及未执行平台。verify-pm2-delivery.mjs --require-complete 在完整交付报告后应通过。主线迁移分叉仍未合并，PM3尚未开始。

### 项目管理原型对齐设计资产（2026-09-13，proposed）

`docs/project-management/design-alignment/`保存全模块逐图事实、自动化四页签旧实现补充、93张审阅/112张来源覆盖、独立审查与仅文档核验脚本；不含新业务原型代码。完整目标规格为`docs/superpowers/specs/2026-09-13-project-management-prototype-alignment-design.md`，现状顶部导航为已确认约束，新增聚合字段合同和参数权威仍待设计确认。

前一轮`docs/project-management/reviews/2026-09-13-prototype-alignment/`的20图审阅及7组应用截图保留历史范围。本轮没有修改页面、数据库或Studio。PM3继续暂停；恢复前需参数身份/覆盖合同裁定及主线能力与迁移分叉核验。

### 原型纠偏实施计划（2026-09-13，planned）

`docs/superpowers/plans/2026-09-13-project-management-alignment-implementation.md`统筹B0图稿与R1–R3独立切片，三个同日前缀r1/r2/r3计划分别定义页面层级、记录路由编辑、字段聚合与数据回归。批准依据在`.ai/decisions/2026-09-13-project-alignment-design-approved.md`；旧“设计待确认”当前描述由此替代，业务代码尚未开始。Popover为计划新增，Drawer已由Modal placement提供；聚合schema/守卫迁移/状态引用为计划目标，不算已存在目录能力。

## 项目管理B0视觉交付（2026-09-13）

`docs/project-management/design-alignment/prototypes/`保存5组imagegen PNG、manifest与提示记录；`prototype-briefs.md`保存原图和旧代码复用映射；`prototype-interactions.md`保存精确交互规则；`implementation-ledger.json`记录B0及未来18任务，业务证据不由静态检查填充。`acceptance/b0/`保存图稿审阅入口、manual-test.md、只读资产验证脚本、核验与审查报告。B0待用户确认，业务源码与原始图库不在该包修改范围。


### R1 对齐实际落点（2026-09-13 confirmed）

以下更新覆盖上文阶段历史中“Popover 尚未存在、纠偏业务代码尚未开始”的旧状态；R2/R3 仍为计划。

- `renderer/shared/components/ui/popover.tsx`：Radix 非模态 Popover，复用 OverlayHost；焦点恢复、视口碰撞及内部滚动。未复制已有 Dialog/Select。
- `domains/projects/components/ProjectCard.tsx` 与 ProjectDirectory：最近卡片/全部条目；ProjectsWorkspace 负责独立真实查询、稳定工作区偏好与请求隔离；ProjectHeader 提供 compact 上下文。
- `domains/project-data/components/RecordQueryToolbar.tsx`：三个互斥查询草稿、指定文本字段搜索；RecordFilterEditor 提供原语法的受控筛选/排序内容。DataTableDetailPage 统一有效查询、分页与导出；DataRecordsTable 的旧工具栏可关闭以消除重复入口。
- `shared/components/Toaster.tsx`：可选 operationId、三条上限及更新计时；调用方仍负责原请求作用域校验。
- `scripts/qa-project-alignment-r1.mjs`：隔离 Electron/CDP 验收与手测辅助；只使用工具创建的工作区，不增加生产调试接口。`docs/project-management/design-alignment/acceptance/r1/` 保存报告、截图、审查、手测和静态覆盖核验。

来源：R1 提交与本机验收；HTTP/IPC/数据库/生成 DTO 未变。记录整页和字段整体草稿尚未实施。

## 项目管理Gallery还原资料（2026-09-13）

`docs/project-management/design-alignment/gallery-baseline/` 保存原始图库路径/hash/尺寸索引、历史验收适用性勘误和本轮文档静态核验。原PNG仍在主项目只读图库，不重新生成副本。当前规格与计划分别为 `docs/superpowers/specs/2026-09-13-project-management-gallery-fidelity.md`、`docs/superpowers/plans/2026-09-13-project-management-gallery-realignment.md`；B0资产仅历史参考。拟新增DataTablePageFrame为展示组合组件，尚未创建，不代表交付。

### Gallery R1验收资产（2026-09-14）

`docs/project-management/design-alignment/acceptance/gallery-r1/`保存逐页原图映射、未修改来源PNG副本、真实Electron截图/运行出处、独立审查、机器结果、逐项用例及用户手册。`scripts/verify-gallery-baseline.mjs`仅核验来源hash/尺寸/证据引用，不代替业务或人工视觉验收。`qa-project-alignment-r1.mjs --manual`只在有专属标记的隔离工作区运行，可注入竞争与响应丢失，不新增生产调试接口。

### Gallery R2 组件责任（2026-09-14，confirmed）

`renderer/domains/project-data/components/RecordEditorForm`维护已有数据草稿/校验与可见错误通知；页面负责路由、外层保存栏和会话隔离。`RecordUnsavedDialog`只呈现真实修改字段和离开选择，`DataDeletionDialog`复用真实删除预检/原操作恢复。`shared/components/ui/calendar-date-input`基于DayPicker与现有Popover提供本地日期选择，保持原文输入和日期时间业务语义，禁止系统默认日期面板。实际文件以apps/desktop/src为前缀。R3字段聚合仍未实施。
