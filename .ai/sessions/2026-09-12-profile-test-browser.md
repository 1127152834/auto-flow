# 浏览器配置卡片、指纹重置与临时测试

- 日期：2026-09-12
- 状态：confirmed（实现、自动化与本机真实验证完成）
- 来源：用户本轮明确要求；当前源码、旧项目配置管理与已安装 CloakBrowser 0.5.9 的本地源码；下列测试。
- 决策：`.ai/decisions/2026-09-12-profile-test-browser.md`。

## 实现边界

配置保存参数与 seed，不代表持久化实例。测试操作以已保存配置快照启动独立临时浏览器；项目环境管理不在本次范围。UI 使用双列 ProfileCard，窄窗口单列；主操作打开测试浏览器，指纹区域显示 seed 与重置按钮，次操作编辑/复制/删除。

重置检查发现既有 `ProfileService.regenerate()` 和仓储已更新并提交 seed；本次没有虚构缺失的后端接口。前端改为直接使用响应更新缓存，后台刷新失败仍保留新 seed，并显示旧值 → 新值及“下次打开测试浏览器时生效”。真实窗口的 seed 传递由新启动适配器负责核验。

HTTP 为 `POST /api/v1/profiles/{profile_id}/test-browser`，成功返回 sessionId、profileId、fingerprintSeed 和可空 warning；DTO 由 OpenAPI 生成。启动时防重复，不自动重试；成功后可以再开全新会话。前端每张卡片独立等待/错误，离线禁用操作，启动请求超时预算为 120 秒。

worker 使用显式已安装可执行文件、独立会话临时目录及 stdin 凭据，避免修改全局环境；正常窗口关闭/服务退出回收。固定代理和代理池使用现有领域能力解析，不静默直连。会话级本地 relay 支持 HTTP/SOCKS5 认证，避免 SDK 将代理密码写进 Chromium 启动参数。可视测试强制 headed，不修改保存的 headless 字段。

## 前端与桌面验证

- profile 定向测试：13 files / 87 tests 通过。
- 全前端：47 files / 281 tests 通过。
- TypeScript 类型检查、ESLint、Electron/Vite 构建通过；API 超时参数追加后 API 定向测试通过。
- OpenAPI 类型已从运行后端生成。
- 隔离 Electron + source sidecar 的真实 CRUD/重置/复制/删除/内核弹窗 smoke 通过。1280/1024 双列、640 单列与无横向溢出有几何断言。
- 实际截图检查了配置双列卡片、seed 前后变化提示，并修正长 Toast 挤压关闭按钮的布局。

## 后端与真实浏览器验证

- 后端全量 pytest：385 passed；生产 src 与本功能测试 Ruff 通过；mypy 119 files 通过。
- OpenAPI 一致性检查、最新前端构建、PyInstaller 后端构建通过；脚本测试 12 passed。
- macOS arm64、公开版 Chromium 145.0.7632.109 实测：同配置可同时保留三个测试窗口；重置前两次启动使用相同 seed，重置后第三次使用已持久化的新 seed。三次初始 Cookie/localStorage 均为空；保存的 headless=true 保持不变，窗口实际可见。
- 同 seed 两次 WebGL 与 Canvas 观测一致；重置后 WebGL renderer 变化，但本次 Canvas hash 没变。因此只确认种子被应用且观察到部分指纹变化，不声称所有指纹特征必然变化。
- 手动关窗仅回收对应会话；退出服务后浏览器/helper 与会话目录全部清理，workspace/profiles 没有生成浏览数据。真实 smoke 先断言会话目录存在，再断言被删除，避免错误路径造成假通过。
- 真实浏览器经过本地 relay → 认证 SOCKS5 测试上游 → fixture.test 成功访问页面，目标 Host/path 与上游凭据均验证；Chromium argv 不含上游地址、用户名、密码。测试使用本地假上游，不创建或修改用户远程代理资源。
- 独立复查验证 POSIX 正常 EOF、异常退出、启动超时下忽略 SIGTERM 的子孙进程回收，以及启动中/已启动会话并行退出。Windows Job Object 的 64 位签名和退出回收配置完成静态审查；没有 Windows 真机或 macOS Intel 实测。
- 冻结侧边服务真实浏览器 smoke 通过：`node scripts/smoke-profile-test-browser.mjs --executable apps/backend/dist/autoflow-backend/autoflow-backend`。独立于 source 再验证真实 Chromium、Playwright 打包资源、认证 SOCKS5 relay、三窗口隔离、指纹参数、单窗关闭及退出后全清理。
- 独立复查最终未发现仍开放的阻塞级或重要正确性问题。详细临时报告：`/tmp/autoflow-profile-test-browser-{backend,review,smoke}.md`；可重复验收入口保存在仓库 scripts，以上结果摘要作为持久记录。

代理池沿用现有选择游标与 resolution 记录；这些是代理选择记账，不是浏览器 Cookie、历史或持久化实例。本次不调整其既有保留策略。扩展与高级参数完成映射测试，未逐一验证第三方扩展的实际运行效果。

## 工作区

保留其他任务的模型与 automation 改动。手动查看当前用户应用时仍处于代理详情，不关闭该窗口或修改其数据；验收使用隔离工作区和本地页面。
