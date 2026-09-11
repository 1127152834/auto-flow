# AutoFlow 项目目录结构

- 日期：2026-09-12
- 状态：本次已创建的目录骨架；目录存在不代表功能已经实现。
- 依据：用户要求预设目录；`docs/architecture/README.md` 已批准架构与当前运行工程。

## 路径基准

后端继续使用 `apps/backend/src/autoflow`，桌面端继续使用 `apps/desktop/src`。不新增 `apps/sidecar`、根目录 `services` 或根目录 `infrastructure`。

迁移规格 `docs/superpowers/specs/2026-09-11-autoflow-feature-migration-design.md` 第 3 节与此基准存在路径冲突，进入业务实施前须由主任务统一规格；本次没有修改该规格。

正式前端领域使用 `renderer/domains`。现有 `renderer/features/profiles` 和 `shared/components/ui` 是此前未提交草稿，本次原样保留，后续迁移时归入领域目录或组件库。不要继续发展两套正式结构。

`packages/ui` 此时只是目录骨架，尚未注册 workspace、安装 shadcn/ui 或变更 import。OpenAPI 类型继续生成到现有 `renderer/shared/api`；本阶段不额外创建重复的 contracts 包。

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
    │   ├── main/{sidecar,ipc,platform}/
    │   ├── preload/
    │   └── renderer/
    │       ├── app/
    │       ├── domains/{profiles,proxies,kernels,models,settings,dashboard}/
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
| `apps/desktop/src/renderer/domains/models/` | 模型供应商和模型目录前端模块；请求封装 api.ts 和必要 model.ts 在实际实现时添加。 |
| `apps/desktop/src/renderer/domains/models/components/` | 模型供应商和模型目录领域组件；使用共享 UI，不承载跨领域基础设施。 |
| `apps/desktop/src/renderer/domains/models/hooks/` | 模型供应商和模型目录的查询、变更和交互状态组合。 |
| `apps/desktop/src/renderer/domains/models/pages/` | 模型供应商和模型目录页面组合；组件完成后再组装页面。 |
| `apps/desktop/src/renderer/domains/models/tests/` | 模型供应商和模型目录跨组件场景测试；局部单元测试也可与源码相邻。 |
| `apps/desktop/src/renderer/domains/profiles/` | 浏览器配置前端模块；请求封装 api.ts 和必要 model.ts 在实际实现时添加。 |
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
- `providers/proxy/proxypanel.py`：固定官方地址的只读 HTTP 传输；真实返回字段未核验时拒绝创建投影。
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
