# 设置页能力基线

- 日期：2026-09-12
- 范围：设置页高保真原型的事实与提案边界
- 视觉约束：沿用暖灰画布、黏土棕强调色、shadcn/ui 与 Tailwind CSS；页面保留“常规 / 工作区 / 关于”三个页签，不增加页内侧栏。
- 验证方式：只读核对旧项目 `browser-automation/autoflow-desktop` 与本仓库源码；未读取数据库、凭据或用户 Workspace 配置，未执行重启、切换或退出。

## 已确认事实（confirmed）

### 旧版设置页

旧版页面有“常规 / Workspace / 关于”三个页签。常规页展示本地服务、本地存储与重启服务入口；Workspace 页展示当前路径、数据库、浏览器配置、内核和日志位置，并提供打开目录、切换 Workspace、切回上一个 Workspace；关于页展示版本与运行组件，并提供退出入口。页面用同一个操作状态禁止切换、切回和重启并发执行，操作成功后重置 API 地址并刷新页面，失败则保留在页面内显示错误。

来源：

- 旧项目 `src/renderer/pages/SettingsPage.tsx:22-26,60-128,130-156,158-370`
- 旧项目 `src/renderer/features/workspace/workspace-api.ts:4-7`

旧页面每 10 秒读取一次 Workspace 状态，并只以 `kernelBusy` 判断能否切换。主进程在打开目录选择器前检查一次，在切换协调器内再次检查；sidecar 未就绪、状态接口失败或内核任务进行中都会拒绝切换。

来源：

- 旧项目 `src/renderer/pages/SettingsPage.tsx:60-64,253-261`
- 旧项目 `src/main/index.ts:72-89,198-215`
- 旧项目 `src/main/sidecar-lifecycle-coordinator.ts:57-69`

Workspace 目标必须存在、是目录并带有 `.autoflow-rebuild-workspace` 标记。用户新选的空目录可以创建该标记；非空且无标记的目录会被拒绝，旧 V1 数据不会被打开。选择器取消时不切换。

来源：

- 旧项目 `src/main/workspace-settings.ts:113-129`
- 旧项目 `src/main/index.ts:198-209`

切换、重启与退出相关 sidecar 操作由协调器串行执行。Workspace 切换先停止旧服务，再启动新服务，只有新服务成功启动后才保存当前路径和上一个路径；新服务启动失败时尝试停止新服务并恢复旧服务，回滚也失败时返回聚合错误。快速连续选择会合并到最后一个目标。

来源：

- 旧项目 `src/main/sidecar-lifecycle-coordinator.ts:17-97`

旧版桌面设置使用临时文件、`fsync` 和重命名落盘，并维护 `.bak`。主设置损坏时尝试备份；恢复前复制原文件作为证据。主文件和备份都不可用时，启动流程要求用户重新选择 Workspace 或退出。

来源：

- 旧项目 `src/main/workspace-settings.ts:53-110`
- 旧项目 `src/main/index.ts:91-133`

旧版没有为正常的切换、重启和退出增加二次确认。恢复故障时才出现“重新选择 Workspace / 退出应用”确认框。旧版 `openPath` 将 renderer 提供的路径直接交给 `shell.openPath`，这一宽口 IPC 不应原样迁移。

来源：

- 旧项目 `src/main/index.ts:91-107,184-216`

旧页面的“运行正常”、版本 `0.2.0`、Python 版本和部分技术栈信息是静态文案，不能作为新原型中的实时能力依据。

来源：旧项目 `src/renderer/pages/SettingsPage.tsx:174-212,319-353`

### 新仓库已有能力

新桌面主进程已经提供 sidecar 状态读取和重启 IPC，preload 暴露了对应受控方法。状态包含 `starting`、`stopped`、`failed` 和 `ready`；重启实现为先停止再启动。当前重启入口没有业务任务占用预检或失败后恢复旧进程的事务协调器。

来源：

- `apps/desktop/src/main/index.ts:32-45`
- `apps/desktop/src/preload/index.ts:7-12`
- `apps/desktop/src/main/sidecar/supervisor.ts:7-25,145-180`

主进程当前把 `app.getPath('userData')` 固定传给 sidecar。平台路径能力只返回 `userData` 和其下的 `logs`；后端再从固定数据根推导数据库、日志、Workspace、缓存、临时目录、Profiles 和 Kernels。当前没有 Workspace 选择、切回、持久化、标记校验、迁移或恢复 IPC；前后端 settings 领域也仍是空目录骨架。

来源：

- `apps/desktop/src/main/index.ts:32-45`
- `apps/desktop/src/main/platform/paths.ts:4-12`
- `apps/backend/src/autoflow/infrastructure/filesystem/paths.py:5-30`
- `apps/desktop/src/renderer/domains/settings/.gitkeep`
- `apps/backend/src/autoflow/application/settings/.gitkeep`
- `apps/backend/src/autoflow/domain/settings/.gitkeep`

新前端已经通过 `prefers-reduced-motion` 跟随操作系统减少动画，但没有用户可选的三态偏好及其持久化。源码中没有页面缩放设置。后端已有一个针对已知密钥和常见凭据语法的文本脱敏函数，但没有诊断信息白名单、诊断包生成、预览、保存或完整脱敏验证流程。

来源：

- `apps/desktop/src/renderer/styles/index.css:22-35`
- `apps/backend/src/autoflow/infrastructure/credentials/redaction.py:1-20`

新桌面的窗口关闭语义有平台差异：macOS 最后一个窗口关闭后保留应用进程，可通过 activate 重新建窗；Windows 最后一个窗口关闭后退出。真正退出时会先停止 sidecar。因此 About 页必须按当前平台显示实际语义，不能照搬旧版统一的“关闭窗口即退出应用”。

来源：`apps/desktop/src/main/index.ts:47-58`

## 原型提案（proposed，尚未实现）

### 工作区能力迁移

保留旧版“当前工作区 / 切换 / 切回上一个 / 恢复与回滚提示”的产品能力，但只迁移行为，不兼容或读取旧版数据。切换只改变后续使用的数据根，不复制、移动或合并目录内容。

实现前需要新增：桌面设置持久化与备份、受控目录选择 IPC、新格式 Workspace 标记与校验、切换协调器、启动恢复协议、后端 Workspace 状态契约，以及切换成功后客户端重新连接流程。打开目录应使用只允许已知应用路径的 IPC，不接受 renderer 传入任意路径。

原型中，任务占用时必须禁止“重启服务”和“切换工作区”，并说明失败时会尝试恢复原服务与原工作区。旧版预检只覆盖 `kernelBusy`；新实现必须把预检扩展到当前及后续所有会持有进程、文件、浏览器会话或写事务的执行器。在统一执行器状态与占用契约完成前，此处只能标为设计目标，不能称为已实现。

### 三项新增设置

1. **界面缩放**：提供 `90% / 100% / 110% / 125%`。当前无缩放 API 接线和偏好持久化，需要新增单一缩放应用点、启动恢复及越界保护。
2. **减少动效**：提供“跟随系统 / 减少动效 / 完整动效”。“跟随系统”已有 CSS 基础；另两态及三态持久化尚需开发。用户强制选择应通过根节点状态统一控制动画组件。
3. **导出诊断包**：默认只选择白名单基础信息和错误码，日志默认不选；生成前向用户展示将包含的项目，确认预览后仅保存到用户选择的本地路径。现有文本脱敏函数只能作为基础，白名单收集、日志二次脱敏、归档、预览、保存 IPC 和脱敏测试均需开发验证。原型不得宣称诊断包已经安全脱敏。

## 首版明确不加入

- 日志保留策略：当前只有日志目录，没有统一落盘、轮转和清理能力。
- 主题与语言：当前没有相应产品契约和持久化能力。
- 开机启动：需要独立的平台适配、状态检测和失败反馈。
- 自动更新：当前没有更新服务、签名与发布通道基础设施。
- 清空数据库或一键重置：具有破坏性，且缺少任务占用、备份、恢复和引用保护协议。
- 任意 sidecar 端口编辑：当前端口、实例令牌和 host token 由主进程管理，开放编辑会破坏现有安全与生命周期边界。

## 原型与旧版的关键差异

| 项目 | 旧版 | 新原型要求 |
| --- | --- | --- |
| 信息架构 | 常规 / Workspace / 关于 | 常规 / 工作区 / 关于；不增加侧栏 |
| 服务状态 | 页面静态显示“运行正常” | 显示真实 `starting / ready / failed / stopped` 状态 |
| 任务预检 | 只检查内核任务 | 覆盖所有当前执行器；未完成前标 proposed |
| 重启失败 | 显示错误 | 展示恢复原服务的结果；协调器尚需实现 |
| Workspace 切换 | 旧格式 marker 与旧数据路径 | 使用新格式能力；不兼容旧数据、不搬迁目录 |
| 打开目录 | 存在接受任意路径的 IPC | 只允许应用已知路径的受控 IPC |
| 关闭窗口 | 统一文案为关闭即退出 | About 按 macOS / Windows 显示真实平台行为 |
| 可访问性 | 跟随系统减少动效 | 增加三态选择，其中仅跟随系统已有基础 |
| 诊断 | 无诊断包流程 | 白名单、默认不含日志、预览后本地保存；需开发验证 |
