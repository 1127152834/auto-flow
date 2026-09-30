# Studio 浏览器配置下拉框

- 状态：confirmed（2026-09-24）。来源：用户截图指出顶部配置下拉框外观不一致。
- 修改当前开发应用所在工作区 `pm9-baseline-merge/autoflow`、分支 `codex/automation-studio-entry`，未修改主仓库已有工作。
- `BrowserProfileSelect` 复用 Studio 已有 Radix Select 和 Button：固定合理宽度、菜单对齐、主题选中态、配置图标、独立刷新图标及加载提示。长名称收起时省略、展开时换行；失效配置保留原 ID 并禁止重选。
- 继续使用原 Profile 请求、项目默认值和显式覆盖规则；浏览器、运行和计划任务入口共享组件。未改后端或用户数据。
- 原生 select 测试改为真实菜单交互，原项目默认/覆盖/重连/失效/请求断言保留。相关 3 文件 19 项通过，TypeScript 和专项 ESLint 通过。
- 本地独立 Mock 预览通过真实点击检查展开、选择、Escape 关闭和焦点返回，目视检查样式；不将此记为真实浏览器执行验收，也未打断用户正在操作的主窗口。
- renderer/main/preload 构建通过；无新增依赖，无远端推送。
