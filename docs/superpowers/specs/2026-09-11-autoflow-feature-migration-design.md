# AutoFlow 全功能迁移设计规格

> 代理模块说明：本规格第 4.3 节关于通用代理 CRUD、远程代理池和“即将到期”等描述已被 `docs/superpowers/specs/2026-09-12-proxy-management-design.md` supersede。ProxyPanel 专用边界、字段证据等级和实施顺序以后者为准。

## 1. 目标与范围

本阶段在 `/Users/zhangtiancheng/Documents/projects/autoflow` 内，将旧项目 `browser-automation/autoflow-desktop` 中除“项目管理”之外的功能，按新的工程化架构重新实现。旧项目仅作为行为和业务能力参考，不直接复制其目录结构、页面耦合或历史数据模型。

WebRPA 仅作为自动化能力和交互思路的参考来源。本项目不做 WebRPA 集成、不做兼容层、不运行其代码；未来需要的能力以本项目自己的领域模型和接口重新实现。

第一阶段不兼容旧数据。旧数据库、旧配置文件和旧缓存没有迁移价值；新系统使用新的 SQLite schema、迁移版本和数据目录。

不纳入范围：项目管理及其专属页面、项目实体、项目路由、项目 API、项目数据迁移。

纳入范围：总览、浏览器配置、代理管理、代理池、内核管理、模型管理、设置、本地服务健康状态、跨平台数据目录与进程生命周期、错误恢复和桌面端打包运行。

## 2. 设计原则

1. **领域优先**：后端、前端和契约以业务领域组织，页面不是系统边界。
2. **契约先行**：HTTP API 由 FastAPI 生成 OpenAPI；前端类型和请求封装从契约生成或严格对齐，页面不手写未约定的响应结构。
3. **组件先于页面**：先完成设计令牌、通用组件、布局组件和领域组件，再组合页面。
4. **垂直闭环**：每个领域同时完成数据模型、业务服务、API、前端 hooks、组件、页面和测试。
5. **跨平台隔离**：Windows/macOS 差异只能存在于 platform、filesystem、process 等适配层。
6. **本地优先**：桌面应用通过本地 FastAPI sidecar 工作，Electron 负责生命周期、窗口、安全边界和 IPC；业务逻辑不放在 Electron renderer。
7. **删除隐式耦合**：页面不直接访问数据库、文件系统、子进程或 Electron API；领域服务不依赖 React。
8. **先可验证，再并行扩展**：每个波次都有可执行的测试和验收门槛，代理不能提交 mock-only 页面或无法启动的半成品。

## 3. 目标架构

```text
apps/
  desktop/
    electron/              Electron main/preload、sidecar supervisor、窗口与 IPC
    renderer/              React 应用、路由、页面组合和 feature hooks
  sidecar/
    app/                   FastAPI 入口、依赖注入、认证、异常映射

packages/
  contracts/               OpenAPI 生成类型、错误模型、分页和状态模型
  ui/                      shadcn/ui + Tailwind 组件、设计令牌和布局基元
  config/                  运行时配置和环境变量 schema
  testing/                 跨前后端 fixtures、mock server、测试工具

services/
  profiles/                浏览器配置领域
  proxies/                 代理和代理池领域
  kernels/                 浏览器内核与安装生命周期
  models/                  模型供应商、模型目录和连接测试
  settings/                用户设置、本地服务和工作区设置
  dashboard/               总览统计、健康状态和最近活动

infrastructure/
  persistence/             SQLite 连接、迁移、事务、仓储实现
  filesystem/               Windows/macOS 数据目录、文件操作和导出路径
  process/                  跨平台进程启动、停止、状态和超时
  platform/                 OS 差异、路径、权限和系统能力探测
```

后端每个领域保持四层职责：`domain`（实体和值对象）、`application`（用例和事务）、`adapters`（HTTP schema/router）、`infrastructure`（仓储和外部系统实现）。领域之间通过 application service 或明确的只读查询接口协作，不通过内部 ORM 模型互相引用。

前端每个领域保持四层职责：`api`（请求和生成类型）、`hooks`（查询、变更、缓存和错误）、`components`（可复用领域组件）、`pages`（页面布局与组合）。共享 UI 不反向依赖任何领域。

## 4. 功能矩阵

### 4.1 总览

- sidecar 在线/离线/恢复中状态。
- 浏览器配置数量、启用状态、最近修改时间。
- 代理总数、健康/异常数量。
- 内核已安装版本和可用更新。
- 模型供应商状态和最近测试结果。
- 最近活动和错误摘要。

总览只调用聚合查询，不直接读取其他领域的数据库表。统计缺失时显示明确的空状态或不可用状态。

### 4.2 浏览器配置

- 配置列表、搜索、筛选、排序和分页。
- 创建、编辑、复制、删除和批量删除。
- 基本字段：名称、描述、启动地址、语言、时区、地理位置。
- 浏览器行为：无头模式、人工化行为、User-Agent、视口。
- 代理关联：无代理、单代理、代理池和代理引用。
- 内核关联：浏览器内核、版本和可用性状态。
- 高级字段：扩展路径、Chromium 参数、启动策略。
- 表单校验、未保存提示、删除确认和操作反馈。

浏览器配置领域不负责启动浏览器实例；启动能力作为后续自动化执行领域的独立边界预留接口。

### 4.3 代理与代理池

- 代理列表、搜索、筛选、排序、分页。
- 单个代理创建、编辑、删除、批量导入。
- 支持协议、主机、端口、认证信息、标签和备注。
- 代理健康检查、单项测试、批量测试、最近测试时间和失败原因。
- 代理池创建、编辑、删除和成员管理。
- 代理池成员排序、启用/禁用和选择策略。
- 导入错误逐行反馈，不因一条坏数据导致整个导入无反馈失败。

认证信息在 API 响应中默认脱敏；日志不得输出明文密码、Token 或完整代理 URL。

### 4.4 内核管理

- 展示许可/服务状态。
- 展示可用 release、edition、版本、平台和架构。
- 下载、安装、取消、删除和重试。
- 展示下载进度、安装进度、失败原因和磁盘路径。
- 检查本地已安装内核及其健康状态。
- Windows/macOS 使用统一领域状态，路径和进程差异由 infrastructure 处理。

下载和安装是异步任务。API 返回任务标识，前端通过轮询或事件订阅获取状态，不阻塞 HTTP 请求。

### 4.5 模型管理

- 模型供应商列表、创建、编辑、删除和启用/禁用。
- 供应商类型、显示名称、Base URL、认证配置和默认模型。
- 模型目录列表、模型启用/禁用、能力标签和上下文信息。
- 连接测试、状态、延迟、失败原因和最近测试时间。
- 密钥只写不读：编辑时可替换，读取时只返回是否已配置。
- 模型调用接口保留稳定的 provider/model 标识，便于后续自动化编排能力使用。

### 4.6 设置与本地服务

- 主题、语言、启动行为和通知偏好。
- 数据目录、工作区目录和临时目录展示。
- 打开目录、导出诊断信息和清理缓存。
- sidecar 当前状态、端口、版本和重启操作。
- renderer 与 sidecar 断线后提供重连、重启和错误详情。
- 所有路径由后端返回规范化后的显示路径和实际路径标识，renderer 不自行拼接平台路径。

## 5. API 与数据约定

统一响应错误结构：

```json
{
  "error": {
    "code": "PROFILE_NOT_FOUND",
    "message": "Browser profile was not found",
    "details": {},
    "request_id": "..."
  }
}
```

列表接口统一支持 `page`、`page_size`、`search`、`sort` 和领域过滤字段，返回 `items`、`total`、`page`、`page_size`。创建/更新返回完整资源；删除返回 `204` 或明确的操作结果。

资源使用稳定的 UUID/ULID 标识；时间统一使用 UTC ISO 8601；枚举值使用小写机器值，显示名称由前端本地化层提供。所有写操作支持服务端校验，客户端校验只用于改善交互。

数据库按领域表拆分，所有表都有 `id`、`created_at`、`updated_at`，软删除只在需要保留审计或恢复能力的实体上使用，不能默认给所有表增加复杂状态。数据库迁移必须可从空库顺序执行。

## 6. UI 设计和组件层

视觉基准固定为用户选定的第三版：暖象牙背景、暖灰表面、黏土棕主色、鼠尾草绿状态色、顶部导航、左侧资源列表、右侧详情编辑区。组件使用 shadcn/ui 约定和 Tailwind，不直接复制生成页面代码。

### 6.1 共享基础组件

Button、IconButton、Input、Textarea、Select、Combobox、Checkbox、Switch、Radio、Date/Time 输入、Label、Field、Form、Card、Badge、Tabs、Table、Pagination、Dialog、AlertDialog、Drawer、Popover、Tooltip、Toast、Progress、Skeleton、EmptyState、ErrorState、ConfirmAction、CommandMenu。

### 6.2 布局组件

AppShell、TopNavigation、WorkspaceSidebar、ResourceList、DetailPane、PageHeader、Toolbar、FilterBar、SplitPane、SectionCard、FormSection、StatusSummary。

### 6.3 领域组件

ProfileListItem、ProfileEditor、ProfileAdvancedFields、ProxyTable、ProxyImportDialog、ProxyPoolEditor、HealthStatusBadge、KernelReleaseCard、InstallProgress、ProviderCard、ModelCatalog、ConnectionTestResult、ServiceHealthPanel、PathSettingRow、DashboardMetricCard。

共享组件只能处理展示、交互和可配置状态；领域组件可以理解领域字段，但不应直接发起不可测试的裸 fetch。页面只负责布局、路由参数和组合。

## 7. 前后端并行开发方式

### 波次 0：审计和契约冻结

产出：旧项目功能矩阵、排除项目清单、实体关系草图、API 草案、领域依赖图、测试策略和文件冲突矩阵。此波次不实现页面。

### 波次 1：共享基础设施

并行任务：

- 后端：领域目录、SQLite、迁移、错误模型、依赖注入、仓储协议。
- 前端：Tailwind 令牌、shadcn/ui 基础组件、组件测试、Story/展示页或可运行组件画廊。
- 契约：OpenAPI 校验、类型生成、统一请求客户端、测试 fixtures。
- 平台：Electron/sidecar 配置、路径、进程、恢复和诊断接口。

波次 1 完成后才允许页面代理开始依赖这些组件。

### 波次 2：领域垂直切片

按以下顺序推进：浏览器配置 → 代理/代理池 → 内核 → 模型 → 设置/本地服务 → 总览。每个领域任务必须同时提交后端、契约、前端、测试和文档变更；不得只提交静态页面。

### 波次 3：集成与验收

验证真实 sidecar、Electron 开发模式和打包模式；执行 Windows x64、macOS arm64、macOS x64 CI；进行 UI 一致性、键盘操作、错误恢复、数据重启持久化和安全日志审查。

## 8. 代理分工规则

当前并行槽位有限，采用分波次和小任务，不让多个代理同时修改同一个高冲突文件。

- 架构/审计代理：负责功能矩阵、领域边界和 API 契约草案。
- 后端代理：每次只负责一个领域的 schema、application service、router、repository 和测试。
- UI 代理：先负责共享组件和设计令牌，完成后再负责一个领域的组件与页面。
- 平台/测试代理：负责跨平台适配、fixtures、契约校验和集成测试。
- 主代理：负责拆任务、合并顺序、跨领域审查和最终验收。

普通领域实现优先使用 `gpt-5.6-sol`；架构审计、合并审查和跨平台风险由高级代理负责。每个代理必须在自己的任务边界内提交可独立审查的 commit，并报告测试命令和未解决风险。

## 9. 测试与完成定义

后端：领域单元测试、仓储集成测试、API contract test、错误映射测试、迁移从空库执行测试。

前端：共享组件交互测试、领域组件测试、页面路由测试、表单校验、加载/空/错误状态测试、真实 API mock server 测试。

端到端：Electron 启动 sidecar、健康检查、断线恢复、创建/编辑/删除资源、重启持久化、打包后路径解析和进程退出。

每个领域的完成定义：

- 新 schema 和 migration 可从空库执行；
- API schema 与前端生成类型一致；
- 页面只使用真实领域 API，不保留 mock-only 数据；
- 领域组件来自共享 UI 体系；
- 错误、加载、空状态、确认和取消流程完整；
- Windows/macOS 差异位于适配层；
- lint、类型检查、单元测试、构建和相关 E2E 全部通过；
- 不引入项目管理实体或路由；
- 不复制旧项目的无边界组件和历史数据层。

## 10. 迁移策略

旧项目保持只读参考。迁移时先建立行为清单，再以新领域模型实现同等能力。任何旧组件只有在职责清晰、依赖可隔离并符合新 UI 规范时才参考其交互；不直接复制旧页面和状态管理。

由于不迁移旧数据，第一阶段只需要保证新数据从空库创建、编辑、删除和重启持久化正确。未来如确实需要外部导入，另立独立的导入工具和版本化格式，不把导入逻辑混入核心领域服务。

## 11. 风险与控制

- **范围膨胀**：项目管理、自动化编排和 WebRPA 复制能力不进入本阶段；后续另立规格。
- **组件过早抽象**：组件只有在两个以上真实场景出现相同交互时才提升为共享组件。
- **代理互相覆盖**：按目录边界和波次分配，公共文件由主代理合并。
- **前后端漂移**：契约检查作为 CI 必选项，禁止手工复制 API 类型。
- **跨平台差异泄漏**：新增平台分支必须进入 infrastructure，并提供至少一个目标平台测试或明确模拟测试。
- **异步任务失控**：内核下载、健康检查等长任务统一使用可观察任务状态和取消语义。
- **敏感信息泄露**：代理认证和模型密钥默认脱敏，日志和诊断导出经过过滤。
