# User Agent 预设

- 日期：2026-09-12
- 状态：confirmed
- 来源：用户要求优化 User Agent 并提供预设；Chromium UA Reduction 官方说明及当前代码/测试。
- `profile_environment.json` 增加 `user_agent_templates`，通过既有鉴权接口导出 `userAgentTemplates`。三个模板对应 Windows 10/11 64 位、macOS、Linux 桌面；平台字符串按 Chromium 统一格式维护。
- 前端只按所选内核主版本替换 `{major}`，不保存平台 UA 模板；无有效版本或无服务端目录时不生成预设。
- 使用既有 `EnvironmentOptionField` 提供完整下拉框、自定义和跟随浏览器（保存为 null），展示实际 UA 字符串。切换内核更新候选，保留已填写值，出现 Chrome 主版本差异时提示重新选择。
- 验证：17 个后端 profile 契约测试、84 个前端 profiles 测试、lint/typecheck/Ruff/mypy、OpenAPI 一致性和前后端构建通过；macOS arm64 冻结后端真实 HTTP 冒烟确认 UA 模板已随包提供。未进行本轮桌面 GUI 目视验收或 Windows 构建。
- 维护规则与官方来源：`docs/migration/profile-environment-options.md`。此项只改配置功能，不增加自动化执行后端。
