# 下拉展开时页面宽度跳动

日期：2026-09-12；状态：confirmed（本机 Electron 自动回归）。

范围：`autoflow-ui-controls-plan` / `codex/ui-controls-plan`。使用 Superpowers systematic-debugging、test-driven-development、verification-before-completion。未修改主目录、业务接口、后端或数据；保护基线的 225 个文件 SHA256 全部一致。

## 复现与原因

用户预览为本 worktree 的已构建 Electron 应用。1440px 窗口中打开浏览器配置列表的代理模式下拉框，主内容宽度由 1428px 变成 1440px，筛选框 x 坐标由 1171px 变成 1183px，筛选框自身宽度保持 208px。

`apps/desktop/src/renderer/styles/index.css` 将 body 设置为 `width:100%`。Radix 的滚动锁隐藏滚动条时，使用 body 右外边距补偿滚动条占位，但显式百分比宽度阻止 body 随外边距收缩，造成页面扩大。临时设置 `body { width:auto }` 后现场测量恢复稳定，随后移除临时样式。

修复：只保留 html、#root 的 100% 宽度，让 body 使用默认自动宽度；保留滚动锁、滚动条和既有浮层行为。

## 验证

- 新增 `apps/desktop/tests/ui/controls.layout.spec.ts`。修复前真实 Electron 回归失败：主内容宽度变化 12px，超过 0.5px 容差；修复后通过。
- 100%、125%、200% 缩放：断言存在实际滚动条，反复展开/关闭列表 Select，测量主内容、搜索输入框、筛选框的宽度及位置；继续覆盖表单 Modal 和浏览器语言可搜索组合框、Escape 关闭与焦点恢复。
- `npm --workspace @autoflow/desktop run test:ui`：6/6 通过，包含真实导航页面、嵌套弹窗、axe、代理与模型 fixture，以及既有窗口/缩放矩阵。
- `npm run typecheck`、`npm run lint`、`npm run build`、`git diff --check`：通过。构建仍有依赖 zod 的注释位置警告，无构建错误。
- 已刷新用户现有隔离预览；构建产物实测 Select 展开前后主内容均为 1428px，筛选框 x 均为 1171px。语言组合框展开前后均为 343px，表单均为 928px。

Windows、读屏、实体输入法及系统滚动条设置切换未执行；原平台验收矩阵和 UI-T4-01 状态不变。本记录补充本次修复证据，不覆盖此前阶段的历史报告。
