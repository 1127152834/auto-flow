# Studio Trace 设计

2026-09-24，状态 proposed。用户要求 CloakBrowser 诊断节点、底部 Trace 面板与小助手证据诊断。

新增规格：docs/superpowers/specs/2026-09-24-studio-cloakbrowser-trace-design.md。
核对本机 CloakBrowser0.5.9、Playwright tracing、已有浏览器会话/日志/产物/LangGraph入口，并查官方资料。没有声称能够记录每条JS执行；全程采集/诊断三节点/分层证据和采集缺口见规格。Product Design提供三张视觉候选，未写生产代码，未运行浏览器采集或模型验收，未修改用户数据库/配置及原有工作树修改。

## 2026-09-25：图1选择与原型

状态：confirmed（视觉选择与原型交付），生产 Trace 未实施。用户选第1张时间线设计。独立原型位于 `/Users/zhangtiancheng/.codex/visualizations/2026/09/11/01a09074-84c2-76b0-b9c8-5f9a6fe693e5/studio-trace`，预览5197。浏览器交互与视觉证据见该目录 design-qa.md；build与单项数据规则测试通过。没有干扰运行中的主应用，没有改业务源码/数据库。后续应按正式规格接真实采集和证据工具，不把演示当真实 Trace。
