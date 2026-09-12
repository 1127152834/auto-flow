# 浏览器语言、时区目录

- 日期：2026-09-12
- 状态：confirmed
- 来源：用户要求后端 JSON 维护、当前代码及前后端测试；详见 `docs/migration/profile-environment-options.md`。
- 既有输入框使用原生 datalist，候选会按当前值过滤，产生“只有一个选项”的体验。已替换为完整 select 和显式自定义输入，保持旧值和已有校验。
- 目录唯一来源是后端 `infrastructure/filesystem/profile_environment.json`，通过鉴权的 `/api/v1/profiles/environment-options` 提供；禁止恢复前端写死的语言/时区兜底目录。
- JSON 每次请求读取，PyInstaller spec 包含该文件；macOS arm64 冻结后端 HTTP 冒烟已验证目录可读。此改动不实现自动化执行后端。
- 验证：15 个后端 profile 契约测试、83 个前端 profiles 测试，lint、类型、前端/后端构建和 OpenAPI 检查通过。桌面 GUI 手工验收未完成，不把组件测试等同于桌面目视验证；Windows 未验证。
