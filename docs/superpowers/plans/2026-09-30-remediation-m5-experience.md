# M5 体验重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **本计划为任务级。** 5A 在 M1 合并后细化为步骤级；5B在M2A台账与M2B签名/输出/预览接口进入OpenAPI后细化；5C身份随M4；5D为视觉完善，不阻塞5B。每段细化审查后继续执行。

**Goal:** 用户按业务语言操作；画布优先；运行过程可见；全应用一套令牌、组件、图标与动效。

**Architecture:** 组件先于页面（`AGENTS.md`）：先完成当前切片需要的令牌/基础控件与布局，再接签名/台账/输出/预览的真实接口；全量视觉迁移在5D逐页推进，不挡业务闭环。标签输入框与新布局用功能开关逐步切换。

**Tech Stack:** React 19、Tailwind + `styles/tokens.css`、Radix / shadcn（`shared/components/ui`）、lucide、CodeMirror 6（标签输入框）、React Flow、vitest、Playwright（视觉回归）。

**Spec:** [docs/superpowers/specs/2026-09-30-remediation-m5-experience.md](../specs/2026-09-30-remediation-m5-experience.md)

## Global Constraints

- 颜色只来自语义令牌；新增写死调色类或十六进制颜色由 lint 拒绝（守门从"不增加"收紧为"禁止"时机：5D 完成）。
- 图标只用 lucide。
- 动效只用 motion-fast / base / slow / loop 四个令牌；尊重"减少动效"与应用内三档设置。
- 界面文案遵守术语表；错误信息 = 发生了什么 + 怎么办。
- 视觉回归截图作为 CI 产物，不入库。
- 功能开关 `newStudioLayout`、`tagInput` 在连续7天正确性/视觉回归、全部消费者迁移、后端预览及回退验证通过后才默认开启。

## Review Focus

1. **1280×800 小窗口**：左右栏折叠后画布仍 ≥ 50%，工具栏不换行（5A Task 4 视觉回归）。
2. **标签输入框中粘贴含引用的文本**：粘贴后仍为标签、内部格式不变（5B Task 3 测试）。
3. **引用的字段被删除或改名**：标签变红、可重选，不静默变成空字符串（5B Task 3 测试）。
4. **批次监控长时间运行**：10,000 行时列表虚拟化、内存稳定、数据延迟 ≤ 2 秒（5B Task 7 测试）。
5. **键盘操作**：命令面板、快速添加面板、抽屉都可全键盘完成并有可见焦点（各任务的可访问性测试）。

---

## 5A 必要基础（依赖 M1）

### Task 1: 当前切片所需的语义令牌
- Files: `apps/desktop/src/renderer/styles/tokens.css`、Tailwind 配置、`shared/components/ui/*` 引用语义类。
- Tests: 所触及控件语义令牌/状态对比度和键盘可达；完整深色值矩阵移至5D。

### Task 2: 当前切片调色类替换（全量在5D）
- Files: 映射表 `scripts/palette-migration.mjs`（脚本化替换 + 人工校对清单）、本切片触及的workflows组件；webrpa.css仅在全部消费者迁移后删除（5D）。
- Tests: 守门不新增，当前页面视觉回归；全量归零由5D验收。

### Task 3: 通用控件复用与领域控件保留
- Files: 按消费者逐个复用shared/components/ui中的button/select/dialog等；颜色/坐标/路径输入仅确有跨领域复用才进入shared；variable-input等流程语义留workflows。新增图标用lucide，全量phosphor替换在5D。
- Tests: 原控件契约/焦点/键盘行为保持，共享层不import workflows；5B标签组件替换前保留旧引用组件，不能提前删目录。

### Task 4: Studio 工具栏与布局
- Files: `Toolbar.tsx`（单行、主次按钮、"更多"菜单、命令面板 Ctrl+K）、`WorkflowEditor.tsx`（可折叠左右栏、底部状态条、小地图默认关闭）。
- Tests: 画布面积测量（1440×900 ≥ 60%）；快捷键与命令面板测试。

### Task 5: 节点视觉与快速添加
- Files: `ModuleNode.tsx`（两行、类别细色条、状态角标、警告角标）、快速添加面板（双击 / `/` / 从连线拖出）。
- Tests: 组件测试、交互测试。

### Task 6: 配置面板分段与就地校验
- Files: `ConfigPanel.tsx`（基本 / 高级、字段下方错误、选择器匹配数常驻）。

### Task 7: 必要运行反馈（完整动效移5D）
- Files: 动效令牌、`ModuleNode.tsx` 去掉整体闪烁、连线流动、失败定位；设置"完整 / 减少 / 关闭"。
- Tests: 减少动效下无循环动画。

### Task 8: 术语表与文案检查
- Files: `shared/copy/glossary.ts`、`scripts/copy-lint.mjs`（CI）、逐页替换文案。

### Task 9: 当前项目外壳减负（全局导航移5D）
- Files: 项目头压缩、当前页面减少重复层级；全局左导航切换与实验入口迁移在5D完成，不作为数据绑定接入前置。

### Task 10: 模块条视图修正
- Files: `BlockFlowView.tsx`（错误分支显示在来源下方并标注"出错时"）；完全循环图预检报错（后端 `validate_workflow_scope` 同步）。

## 5B 数据与运行（依赖 M2A/B，优先于全量视觉改造）

### Task 1: 流程"输入与输出"面板（签名编辑、样例值、从数据表导入）
### Task 2: 数据侧栏（输入字段、M2B声明的必有/条件输出、全局变量、凭据）
### Task 3: 标签输入框（CodeMirror 6 原子装饰，替换 `controls/variable-input.tsx`，功能开关 `tagInput`）
### Task 4: 画布数据可见（节点第二行数据标签、读 / 写角标、字段高亮、分支文字）
### Task 5: 写回表单节点（更新当前记录、设置状态、新增记录、查询记录）与 End 勾选
### Task 6: 自动化绑定页（左右映射、实时匹配行数与样例、多表连线图、一键建字段）
### Task 7: 批次实时监控页（分段进度、吞吐、运行中卡片与截图缩略图、失败归组与批量操作）
### Task 8: 运行总览
### Task 9: 数据表页（全宽、虚拟滚动、冻结首列、抽屉详情、台账列）
### Task 10: 任务详情时间线
### Task 11: 试跑（后端previewWrites、主显示字段选行、节点实际值）

- 接口前置：M2B Task9，生成类型中的executionMode冻结入请求，原请求恢复不变模式；不能只增加前端开关。
- 测试：真实HTTP/worker/SQLite下预览写后读、记录/版本/台账/同步意图/环境不变，显式realWrites才写入；End保存预检拒绝，临时引用不可真实写回。文案明确网页操作仍真实执行。

每个任务：组件/页面测试及生成OpenAPI类型；开发契约夹具不能替代真实API/worker验收，涉及Studio附视觉回归；先完成Task1/2/3/5/6/11的数据绑定试跑闭环，再完成Task7/10失败处理及Task8/9页面完善。

## 5C 身份与衔接（依赖 M4）

### Task 1: 身份列表页（与 M4 Task 9 协作）
### Task 2: Studio 嵌入主窗口工作区，可弹出
### Task 3: 失败归组一键跳到失败节点并用该行试跑
### Task 4: 可用性验收（5 位目标用户，脚本与记录模板见规格 AC5-06；记录放 CI 产物 / 外部存储，仓库只留汇总）

## 5D 视觉完善（不阻塞5B）

### Task 1: 全量语义颜色与深色值
- 按页面迁移，paletteClasses=0；每个令牌浅/深值齐全，webrpa.css全部消费者迁完才删除。
### Task 2: 图标与通用控件收尾
- secondIconLibraryFiles=0后删除phosphor；旧controls目录无消费者且标签开关迁移/回退验证后移除，不把流程语义搬入shared。
### Task 3: 完整动效与全局导航
- 120/180/280ms和1.2s令牌、减少/关闭设置；全局左导航与项目外壳分批迁移、状态/草稿保持，分别做视觉和键盘回归。

## 里程碑验收
- AC5-01 至 AC5-09 逐条勾选；开关默认开启的条件记录在 `.ai/plans`；独立退出评审。
