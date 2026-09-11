# ProxyPanel 代理管理实施计划

- 日期：2026-09-12
- 状态：proposed，需规格审查后实施
- 关联规格：`docs/superpowers/specs/2026-09-12-proxy-management-design.md`
- 目标：在 AutoFlow 新架构中交付 ProxyPanel 代理舰队、本地代理组和浏览器配置引用的完整垂直切片

## 阶段 0：契约冻结与验证夹具

### 0.1 建立外部 API fixture

准备脱敏 JSON fixture，覆盖：代理列表、代理详情、实时探测、凭据、地点、轮换计划、IPv4 白名单、用量、余额、401、403、404、409、422、429、5xx 和 schema 缺失。

记录每个字段的证据等级：confirmed-authenticated-doc、confirmed-public、locally-derived 或 unknown。`subscription_expires_at` 默认 nullable，不能用余额或自动续费推导。

### 0.2 冻结 AutoFlow 内部 OpenAPI

先定义连接、投影代理、本地代理组、健康状态、stale projection、ActionResult 和统一错误模型，再生成 renderer 客户端类型。内部契约不得暴露 API key、密码或 ProxyPanel 原始 URL。

### 0.3 完成安全审查

确认固定官方 base URL、CredentialStore 使用方式、URL/日志脱敏、请求并发锁、429 Retry-After 处理和数据面探针目标。

阶段验收：OpenAPI schema 校验通过；fixture 能驱动 adapter contract test；所有敏感字段扫描为空。

## 阶段 1：后端领域与 Provider Adapter

### 1.1 领域和仓储

在 `domain/proxies` 定义 ProxyPanelConnection、ProxyEndpointProjection、LocalProxyGroup、RotationSchedule、HealthSnapshot 和端口协议。

在 `infrastructure/database` 实现 SQLite 表、迁移、投影更新时间、last_error 和引用约束。连接密钥和 endpoint password 只存 CredentialStore secret ref。

### 1.2 ProxyPanel adapter

在 `providers/proxy` 实现新 `/api/v1` Bearer adapter：

- 连接验证和代理同步；
- 代理详情和实时探测；
- 获取/轮换凭据；
- Change IP、改变地点；
- 轮换计划；
- IPv4 白名单；
- 地点、用量和余额读取。

所有 provider 错误先转换为内部错误，不把外部 URL、Token 或原始密码带出。写操作使用本地 request id/并发锁，失败时保留旧投影。

### 1.3 Application services

实现 connection verify/sync、proxy probe、change-ip、relocate、rotation、credentials、allowlist、usage 和 local group CRUD。同步采用显式触发和 TTL stale 标记，不做无界后台轮询。

### 1.4 HTTP adapter

实现内部 API 路由、Pydantic schema、分页/筛选的本地约定、错误映射和 operation 状态。若 ProxyPanel 写操作被识别为异步，统一返回 operation_id。

阶段验收：后端 unit、repository、migration、provider contract、HTTP contract 全部通过；无真实 key 也可用 fixture 启动。

## 阶段 2：共享 UI 组件和数据 hooks

### 2.1 组件先行

在共享 UI 中完成并测试：DataTable、StatusBadge、MetricCard、Drawer、Dialog、Tabs、Select、Combobox、Progress、Toast、EmptyState、ErrorState、Skeleton、ConfirmAction、CopyButton、SensitiveValue。

### 2.2 代理领域组件

在 `renderer/domains/proxies/components` 完成：ProxyPanelConnectionCard、ProxySummary、ProxyFleetTable、ProxyStatusBadge、ProxyDetailDrawer、LocationPicker、RotationScheduleForm、CredentialPanel、IpAllowlistEditor、HealthResult、LocalProxyGroupTable、RiskConfirmationDialog。

组件只接收类型化 props 和显式 action，不直接 fetch 或读取 secret。

### 2.3 hooks 和客户端

实现查询缓存、stale 标记、显式 sync、单行 probe、写操作锁、429 倒计时提示和错误映射。所有类型来自后端 OpenAPI。

阶段验收：共享组件交互/可访问性测试；代理领域组件覆盖加载、错误、空、stale、敏感字段和写入中状态。

## 阶段 3：代理管理垂直页面

### 3.1 主页面

组装单主内容区：连接卡片、可验证摘要、代理舰队表格、筛选和本地代理组。即将到期指标只有契约明确提供截止时间时才渲染。

### 3.2 详情流程

实现 Drawer 的概览、位置与轮换、凭据与白名单、用量四个标签，接入 Change IP、改地点、轮换、健康检查和受控复制。

### 3.3 本地代理组流程

实现组 CRUD、成员排序、Round Robin、异常/未检测成员的二次确认、浏览器配置关联和引用保护。

### 3.4 页面状态

完整实现未连接、同步失败、stale、无代理、探测中、429、认证失败、外部服务不可用和成功 Toast。禁止保留长期静态 mock 数据。

阶段验收：页面交互测试和 API fixture 联调通过；无 API key 时敏感值仍不出现在 DOM、console 或错误文本。

## 阶段 4：浏览器配置集成

更新浏览器配置领域的代理模式：不使用代理、单个 ProxyPanel 代理、本地代理组。表单只选择本地投影 ID，不把 ProxyPanel credential 送到 renderer。

验证：删除/禁用被引用代理时有明确冲突；代理组成员变化不会破坏已保存浏览器配置；代理同步后选择器缓存正确刷新。

## 阶段 5：端到端和跨平台验收

- backend pytest：领域、仓储、迁移、provider fixture、契约和错误；
- desktop Vitest：共享组件、hooks、页面状态和表单；
- Electron E2E：连接 fixture、同步、打开详情、改变地点模拟、健康检查、代理组 Round Robin、浏览器配置引用；
- 安全测试：API key/password/认证 URL 日志扫描、响应脱敏和受控复制；
- macOS arm64/x64、Windows x64 CI：路径、CredentialStore、sidecar 生命周期和打包 smoke；
- 真实 ProxyPanel key 联调单独执行，只允许非破坏性读取、探测和可控测试，不自动换 IP、购买或续费。

## 并行代理分工

当前并行槽位有限，按波次并行：

- 高级架构代理：阶段 0、provider contract、错误/安全审查；
- `gpt-5.6-sol` 后端代理：阶段 1 的领域、迁移、adapter 和 HTTP API；
- `gpt-5.6-sol` UI 代理：阶段 2 的共享组件和代理领域组件；
- 主代理：契约合并、阶段 3 页面装配、阶段 4 集成和阶段 5 最终验收。

禁止多个代理同时编辑 OpenAPI 入口、全局路由、数据库注册和全局样式；公共文件由主代理在每一波末尾合并。

## 提交顺序与停止条件

1. 先提交 fixture、契约和安全规则；
2. 再提交后端领域与 adapter；
3. 再提交共享 UI 和 hooks；
4. 再提交页面垂直切片；
5. 最后提交浏览器配置集成和 E2E。

任一阶段如果发现 ProxyPanel live schema 与 fixture 不一致，停止扩展 UI，先更新 adapter contract、规格中的字段证据等级和测试夹具。未确认 `subscription_expires_at` 前不得实现“即将到期”统计。
