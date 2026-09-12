# AutoFlow 项目目录结构

- 日期：2026-09-12
- 状态：目录骨架与已实现领域的职责索引；空占位目录不代表功能已经实现。
- 依据：用户要求预设目录；`docs/architecture/README.md` 已批准架构与当前运行工程。

## 路径基准

后端继续使用 `apps/backend/src/autoflow`，桌面端继续使用 `apps/desktop/src`。不新增 `apps/sidecar`、根目录 `services` 或根目录 `infrastructure`。

迁移规格 `docs/superpowers/specs/2026-09-11-autoflow-feature-migration-design.md` 第 3 节与此基准存在路径冲突，进入业务实施前须由主任务统一规格；本次没有修改该规格。

正式前端领域使用 `renderer/domains`。`renderer/shared/components/ui` 已是经过交互测试的正式 shadcn/Radix 基础组件层；`renderer/features/profiles` 的旧 mock 草稿由浏览器页面接入任务替换，不再作为功能入口。此前把两者一并标为“未提交草稿”的描述已 superseded。

`packages/ui` 仍只是目录骨架，尚未注册独立 workspace。当前实际使用的 shadcn/Radix 组件位于桌面端 `renderer/shared/components/ui`，Tailwind 令牌位于 `renderer/styles/tokens.css`，`styles/index.css` 导入令牌与 `controls.css`。OpenAPI 类型继续生成到 `renderer/shared/api/generated.ts`，不维护第二套 contracts 包。

## 骨架概览

```text
apps/
├── backend/
│   ├── src/autoflow/
│   │   ├── bootstrap/
│   │   ├── domain/{profiles,proxies,kernels,models,settings}/
│   │   ├── application/{profiles,proxies,kernels,models,settings,dashboard}/
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
    │       ├── domains/{profiles,proxies,kernels,models,settings,dashboard}/
    │       │   └── 每个领域：components/、hooks/、pages/、tests/
    │       ├── shared/{api,components,hooks,lib,ui-lab}/
    │       └── styles/
    └── tests/{e2e,fixtures}/
packages/ui/
├── src/{components,layouts,styles}/
├── tests/
└── examples/
.ai/{memory,knowledge,decisions,plans,sessions}/
docs/{architecture,migration,automation-studio,references,superpowers,design-system}/
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
| `apps/backend/src/autoflow/infrastructure/database/migrations/versions/` | 未来 Alembic 版本脚本；此时仅保留目录，尚未初始化 Alembic。 |
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
| `apps/desktop/src/main/platform/macos/` | 必要的 macOS 桌面适配。 |
| `apps/desktop/src/main/platform/windows/` | 必要的 Windows 桌面适配。 |
| `apps/desktop/src/main/sidecar/` | 本地后端启动、就绪、恢复和退出监管。 |
| `apps/desktop/src/preload/` | 受控桌面能力桥接。 |
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
| `apps/desktop/src/renderer/styles/` | index.css 为入口；tokens.css 定义暖灰/黏土棕令牌，controls.css 为定向控件基础样式与全局 Chromium 滚动条。 |
| `apps/desktop/src/renderer/shared/ui-lab/` | DEV 专用 `#/__ui` 验收页。当前含令牌、RHF、浮层、文字、勾选/单选/开关、选择/搜索、滚动条和数据反馈状态案例；fixture 不进入生产 JS，不访问业务 API。 |
| `apps/desktop/tests/e2e/` | 真实 Electron 与 sidecar 的用户流程。 |
| `apps/desktop/tests/fixtures/` | 桌面端脱敏测试数据。 |
| `docs/architecture/` | 批准的运行边界、依赖方向和基础验证报告。 |
| `docs/automation-studio/` | 未来自动化编排的研究资料；不表示本阶段实现范围。 |
| `docs/migration/` | 能力清单、来源对应、迁移状态和验收证据。 |
| `docs/references/` | 外部资料与来源记录。 |
| `docs/superpowers/plans/` | 正式实施计划。 |
| `docs/superpowers/specs/` | 正式设计规格。 |
| `packages/ui/examples/` | 组件展示与用法示例；页面开发前验证组件状态。 |
| `packages/ui/src/components/` | 计划中的 shadcn/ui 基础控件和跨领域通用组合控件。 |
| `packages/ui/src/layouts/` | 跨领域工作台布局基元；不包含业务导航配置。 |
| `packages/ui/src/styles/` | 计划中的 Tailwind 主题、设计令牌和组件样式。 |
| `packages/ui/tests/` | 组件交互、可访问性和状态测试。 |
| `reference/` | 只读参考材料，不作为运行时依赖。 |
| `scripts/` | 现有构建、类型生成、冒烟和仓库验证脚本。 |

## 依赖与维护规则

### 代理模块实施补充（2026-09-12，confirmed）

代理领域实现已从 `codex/proxy-management@0ad2fd2` 选择性接入浏览器主线。完整接口、验证结果和限制见 [代理模块实施状态](migration/proxy-management-status.md)。

- `application/proxies/facade.py`：事务边界与代理用例入口；HTTP adapter 不直接构造仓储。
- `infrastructure/database/proxy_models.py`：代理扩展 ORM；复用现有 `proxies` / `proxy_pools` 的主键，不改写 `models.py` 中浏览器资源模型。
- `infrastructure/database/proxies.py`：代理 SQLAlchemy 仓储与 Unit of Work。
- `providers/proxy/proxypanel.py`：固定官方地址的只读 HTTP 传输，验证真实列表/分协议端点/到期字段/按需凭据；未知列表包装拒绝更新投影。
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
- 不预设项目管理和工作流执行模块；后续确认范围后再扩展。已有自动化研究文档仍保留。
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

## 控件统一 T0–T2（2026-09-12，confirmed）

- 在 desktop shared 原地补齐，`packages/ui` 仍是骨架，不迁移基础组件路径。
- `shared/components/ui/overlay-host.tsx` 只提供 Dialog 层级和本层弹出内容宿主；Dialog/AlertDialog 复用原 Radix 行为。`ui-lab/LabCombobox.tsx` 是 React Aria 集成验证探针，尚非领域组件的正式 API。
- `scripts/smoke-ui-controls.mjs` 使用独立 Vite 服务与 Electron 临时 userData，保存实际窗口截图与结果；通过 `npm run smoke:ui-controls` 调用，先运行构建。
- 验收与限制见 `docs/design-system/verification/choice-overlay-gate.md`。共享控件替换、领域接入和全系统跨平台回归仍属于 T3–T13。

### 控件统一 T3（2026-09-12，implemented）

`shared/components/ui` 新增 IconButton/SearchInput/PasswordInput/Spinner，并统一现有 Button/Input/Textarea；FormField 新增显式render-prop，FieldGroup使用原生fieldset/legend。`shared/ui-lab/TextControlCases.tsx` 提供状态矩阵，该阶段脚本输出到 `docs/design-system/verification/t3/` 并验证真实配置表单。T3历史报告见 `docs/design-system/verification/text-controls.md`，当前T4结果见下文；领域迁移尚未执行，UI-G0-01须在T5前复核。

### 控件统一 T4（2026-09-12，implemented）

`shared/components/ui` 补齐 Checkbox Indicator、RadioGroup Root/Item/Indicator、Switch Thumb 与原生 Disclosure；状态外观集中在 `styles/controls.css`。`shared/ui-lab/ToggleCases.tsx` 提供状态、组错误、RHF及折叠案例；脚本当前输出到 `docs/design-system/verification/t4/`，验证浏览器配置Switch与设置诊断Checkbox。未替换领域中的原生radio/details。详见 `docs/design-system/verification/toggle-controls.md`；UI-G0-01及UI-T4-01保留为后续门槛。

### 控件统一 T5（2026-09-12，implemented）

`shared/components/ui/choice-types.ts` 定义应用侧选择API；`select-radix.tsx` 是待领域迁移的正式Select入口，旧 `select.tsx` 仍保留。`combobox.tsx` 提供严格选择与自由输入，大目录复用现有RAC Virtualizer；`scroll-area.tsx` 统一双轴轨道与实际viewport的ref/ARIA。`LabCombobox` 现仅为fixture适配器，替代上文T0探针的独立实现。ChoiceCases/ScrollCases/FormFocusCase提供状态与RHF验收，脚本当前输出到 `docs/design-system/verification/t5/`；G0专项脚本 `scripts/verify-choice-overlays.mjs`。详见 `docs/design-system/verification/choice-controls.md`。领域批量迁移、G1与跨平台最终验收未完成。

### 控件统一最终落点（2026-09-12，confirmed）

全部实际页面已接入 desktop shared 控件。Select 只有 `shared/components/ui/select.tsx` 一个入口，FormField 只接受 render-prop；Drawer 复用 Modal；未使用 ResourceState 已删除。模型 TagInput 留在 models 领域。AST 审计位于 `scripts/audit-ui-controls.mjs`，精确例外为 `scripts/ui-controls-allowlist.json`；Playwright/axe 在 `apps/desktop/tests/ui/`，与 Vitest 隔离。`npm run audit:ui` 检查全部 renderer/主入口与生产实验室泄漏，`npm --workspace @autoflow/desktop run test:ui` 验证隔离 Electron 真页面和独立 fixture。历史 T0–T5 未迁移描述已 superseded，最新证据为 `docs/design-system/verification/ui-controls-results.md`。Windows/人工验收仍 pending。
