# Studio 网页输入原文保护

2026-09-14，confirmed。14 文本/截图范围测试复现多行输入丢换行，启用现有 VariableInput.multiline；相关44、类型/lint/构建通过。真实浏览器编辑→保存→刷新→打开保留两行及模板文本。见 docs/migration/studio-frontend-completion/web-text-validation.md。尚未覆盖真实执行与正式 Electron；F0–F6 继续推进。
