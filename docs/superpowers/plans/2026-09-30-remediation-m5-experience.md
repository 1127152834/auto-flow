# M5 体验重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **本计划为任务级。** 5A 在 M1 合并后细化为步骤级；5B 在 M2 的签名 / 台账接口进入 OpenAPI 后细化；5C 在 M4 身份接口可用后细化。每段细化后经用户确认再执行。

**Goal:** 用户按业务语言操作；画布优先；运行过程可见；全应用一套令牌、组件、图标与动效。

**Architecture:** 组件先于页面（`AGENTS.md`）：先迁移令牌与共享控件，再重做 Studio 布局与节点视觉，然后接入签名、台账等新接口重做数据绑定与运行页面。标签输入框与新布局用功能开关逐步切换。

**Tech Stack:** React 19、Tailwind + `styles/tokens.css`、Radix / shadcn（`shared/components/ui`）、lucide、CodeMirror 6（标签输入框）、React Flow、vitest、Playwright（视觉回归）。

**Spec:** [docs/superpowers/specs/2026-09-30-remediation-m5-experience.md](../specs/2026-09-30-remediation-m5-experience.md)

## Global Constraints

- 颜色只来自语义令牌；新增写死调色类或十六进制颜色由 lint 拒绝（守门从"不增加"收紧为"禁止"时机：5A 完成）。
- 图标只用 lucide。
- 动效只用 motion-fast / base / slow / loop 四个令牌；尊重"减少动效"与应用内三档设置。
- 界面文案遵守术语表；错误信息 = 发生了什么 + 怎么办。
- 视觉回归截图作为 CI 产物，不入库。
- 功能开关 `newStudioLayout`、`tagInput` 在黄金场景与视觉回归连续 7 天通过后默认开启。

## Review Focus

1. **1280×800 小窗口**：左右栏折叠后画布仍 ≥ 50%，工具栏不换行（5A Task 4 视觉回归）。
2. **标签输入框中粘贴含引用的文本**：粘贴后仍为标签、内部格式不变（5B Task 3 测试）。
3. **引用的字段被删除或改名**：标签变红、可重选，不静默变成空字符串（5B Task 3 测试）。
4. **批次监控长时间运行**：10,000 行时列表虚拟化、内存稳定、数据延迟 ≤ 2 秒（5B Task 7 测试）。
5. **键盘操作**：命令面板、快速添加面板、抽屉都可全键盘完成并有可见焦点（各任务的可访问性测试）。

---

## 5A 基础（依赖 M1）

### Task 1: 令牌与深色模式
- Files: `apps/desktop/src/renderer/styles/tokens.css`、Tailwind 配置、`shared/components/ui/*` 引用语义类。
- Tests: 令牌完整性测试（每个令牌有浅 / 深值）、组件快照改为语义类断言。

### Task 2: 写死调色类批量替换
- Files: 映射表 `scripts/palette-migration.mjs`（脚本化替换 + 人工校对清单）、`domains/workflows/**`；删除 `webrpa.css`。
- Tests: 守门 `paletteClasses` = 0；视觉回归按页面分批通过。

### Task 3: Studio 控件并入共享库，图标统一
- Files: `workflows/components/controls/*` → `shared/components/ui/*`（补颜色选择器、坐标输入、路径输入）；phosphor → lucide。
- Tests: 控件契约测试迁移；守门 `secondIconLibraryFiles` = 0；移除 phosphor 依赖。

### Task 4: Studio 工具栏与布局
- Files: `Toolbar.tsx`（单行、主次按钮、"更多"菜单、命令面板 Ctrl+K）、`WorkflowEditor.tsx`（可折叠左右栏、底部状态条、小地图默认关闭）。
- Tests: 画布面积测量（1440×900 ≥ 60%）；快捷键与命令面板测试。

### Task 5: 节点视觉与快速添加
- Files: `ModuleNode.tsx`（两行、类别细色条、状态角标、警告角标）、快速添加面板（双击 / `/` / 从连线拖出）。
- Tests: 组件测试、交互测试。

### Task 6: 配置面板分段与就地校验
- Files: `ConfigPanel.tsx`（基本 / 高级、字段下方错误、选择器匹配数常驻）。

### Task 7: 动效令牌与运行态动画
- Files: 动效令牌、`ModuleNode.tsx` 去掉整体闪烁、连线流动、失败定位；设置"完整 / 减少 / 关闭"。
- Tests: 减少动效下无循环动画。

### Task 8: 术语表与文案检查
- Files: `shared/copy/glossary.ts`、`scripts/copy-lint.mjs`（CI）、逐页替换文案。

### Task 9: 全局导航与项目外壳
- Files: `app/ApplicationHeader.tsx` → 左侧窄导航；项目外壳一行头部 + 二级左栏；安卓与实验室移入设置"实验功能"开关。

### Task 10: 模块条视图修正
- Files: `BlockFlowView.tsx`（错误分支显示在来源下方并标注"出错时"）；完全循环图预检报错（后端 `validate_workflow_scope` 同步）。

## 5B 数据与运行（依赖 M2）

### Task 1: 流程"输入与输出"面板（签名编辑、样例值、从数据表导入）
### Task 2: 数据侧栏（输入字段、上游输出、全局变量、凭据）
### Task 3: 标签输入框（CodeMirror 6 原子装饰，替换 `controls/variable-input.tsx`，功能开关 `tagInput`）
### Task 4: 画布数据可见（节点第二行数据标签、读 / 写角标、字段高亮、分支文字）
### Task 5: 写回表单节点（更新当前记录、设置状态、新增记录、查询记录）与 End 勾选
### Task 6: 自动化绑定页（左右映射、实时匹配行数与样例、多表连线图、一键建字段）
### Task 7: 批次实时监控页（分段进度、吞吐、运行中卡片与截图缩略图、失败归组与批量操作）
### Task 8: 运行总览
### Task 9: 数据表页（全宽、虚拟滚动、冻结首列、抽屉详情、台账列）
### Task 10: 任务详情时间线
### Task 11: 试跑（按主显示字段选行、节点旁显示实际值、默认不真实写回）

每个任务：组件测试 + 页面测试 + 与 M2 OpenAPI 类型的契约夹具；涉及 Studio 的任务附视觉回归。

## 5C 身份与衔接（依赖 M4）

### Task 1: 身份列表页（与 M4 Task 9 协作）
### Task 2: Studio 嵌入主窗口工作区，可弹出
### Task 3: 失败归组一键跳到失败节点并用该行试跑
### Task 4: 可用性验收（5 位目标用户，脚本与记录模板见规格 AC5-06；记录放 CI 产物 / 外部存储，仓库只留汇总）

## 里程碑验收
- AC5-01 至 AC5-07 逐条勾选；开关默认开启的条件记录在 `.ai/plans`；独立退出评审。
