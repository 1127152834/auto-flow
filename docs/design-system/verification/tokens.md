# T1 令牌与浏览器样式

- 日期：2026-09-12；状态：confirmed（代码及自动检查），视觉见后续G0。
- 先新增ui-tokens测试，观察10项因缺token失败；实现后10/10通过。
- 颜色/字体/密度/层级/焦点/阴影/动效集中到tokens.css；index保留data-motion规则。controls.css统一Chromium滚动条，输入外观规则使用data-af-control定向启用，避免提前替换领域表单。
- typecheck与build通过；原有Zod PURE注释警告仍在。没有更改业务接口/后端/领域数据逻辑。
- 32/40密度与token颜色将在T2正式展示页验证；不以色值测试声称跨平台外观通过。

T2 续验：Electron 色板实际暴露 Tailwind 裁掉未静态引用变量，改为 `@theme static`；新增运行时色板检查，先复现 success 缺失再通过。输入 :read-only 限于 enabled 的 input/textarea，避免误作用于按钮及覆盖 disabled 背景。32/40 密度往返与只读/禁用背景区分均加入 G0。完整范围见 [G0 报告](choice-overlay-gate.md)。
