# 全局精细网格使用点清单

日期：2026-09-14。状态：confirmed（源码盘点）；运行验收状态由主协调另行记录。

盘点工作区为 `/Users/zhangtiancheng/Documents/projects/autoflow-table-system`，分支 `codex/global-table-system`，基线 `bdca5ee39aa7fef7214551a98b43463bf2aba943`。该基线已包含最新主线 Studio 与同表新增行；主项目目录仅作只读参考。旧 `dcb1831`/`cda081d` 分离方案不代表本清单的实施状态。

视觉依据为[用户选定的精细网格图](../../prototype/table-system-2026-09-14/fine-grid-selected.png)，行为边界见[规格](../../superpowers/specs/2026-09-14-global-table-system.md)。以下共 **14 处真实表面：9 处业务表格、5 处 Studio 表面**。行号是本次源码检查位置，后续修改以组件名和调用关系定位。

## 真实消费者

实现路径以 `apps/desktop/src/renderer/` 为根；同一行中简写的 `pages/`、`components/` 调用位置沿用该实现的 `domains/<领域>/`，`documentation/`、`assistant/` 调用位置沿用 `domains/workflows/components/`。

| 编号 | 表面 | 实现及调用位置 | 复用决策与保留行为 |
|---|---|---|---|
| T01 | 项目数据记录，含行尾草稿 | `domains/project-data/components/DataRecordsTable.tsx:108`；`pages/DataTableDetailPage.tsx:741` 装配，`:748` 传入 `RecordDraftRows` | 原生 `Table` + `TableScroll`；`RecordQueryToolbar` 组合 `TableToolbar`。保留服务端查询、分页、typed 身份、真实复选选择、详情/编辑入口；新增继续在同表草稿行完成，`RecordGridCellEditor` 只收紧样式。`queryLocked`、`createDisabled`、未保存保护及原命令恢复保持。草稿不另计一张表。 |
| T02 | 字段与校验目录 | `domains/project-data/components/SchemaEditor.tsx:71`；`pages/DataTableDetailPage.tsx:799` | 使用共享表格与滚动容器，保留字段抽屉、本地聚合草稿、外层统一保存、只读/冻结状态。 |
| T03 | 字段保存影响摘要 | `domains/project-data/components/SchemaImpactDrawer.tsx:26`；`components/SchemaEditor.tsx:80` | 抽屉内键值表采用 `TableHead scope="row"`；长摘要可换行，保留预检事实、阻塞原因、确认与恢复操作。 |
| T04 | 数据状态及引用计数 | `domains/project-data/components/DataStatusTable.tsx:40`；`pages/DataTableDetailPage.tsx:813` | 共享表格；状态名和实际引用数保持，读取失败不伪装成零引用，删除禁用与解释保持。 |
| T05 | 来源事实 | `domains/project-data/components/DataTableSourcePanel.tsx:32`；`pages/DataTableDetailPage.tsx:819` | `Table data-variant="facts"` + 行标题；键值事实只读，移除交互行悬停暗示，长文件名仍可完整读取。 |
| T06 | Excel 工作表样例 | `domains/project-data/components/ExcelInspectionPanel.tsx:28`；`components/ExcelImportWizard.tsx:56–57` | 共享表格及内部横滚；保持 `sample.slice(0, 10)`、工作表选择、列头/样例 title、空值及检查异常提示，不把预览变成编辑表。 |
| T07 | ProxyPanel 代理列表 | `domains/proxies/components/ProxyFleet.tsx:75`；`pages/ProxyManagementPage.tsx:56` | 共享表格、`TableToolbar`、`TableStatus`；保留输入即查询、筛选重置 offset、服务端数量/分页、凭据缺失/远端缺失/冷却期间检测禁用。 |
| T08 | 本地代理组列表 | `domains/proxies/components/LocalProxyGroups.tsx:40`；`pages/ProxyManagementPage.tsx:65` | 共享表格；保留成员顺序、健康汇总与引用事实、编辑/删除确认。组编辑器的成员查询复用 `TableToolbar`，成员复选列表仍保留列表形态。 |
| T09 | 模型目录 | `domains/models/components/ModelDirectory.tsx:22`；`pages/ModelManagementPage.tsx:46` | 共享表格、`TableToolbar`、`TableStatus`；状态筛选使用已有 Radix `Select`，名称/标识/标签本地过滤以及测试、启停、编辑事件不变。 |
| T10 | Studio 收集数据虚拟表 | `domains/workflows/components/DataTable.tsx:228`；`components/LogPanel.tsx:928` | 保留 div 虚拟表和现有虚拟滚动，使用共享 `af-table-scroll` 视觉外框与 `af-studio-grid-*` 适配；唯一正文滚动区具 `region`、名称及 `tabIndex=0`；`ROW_HEIGHT=32` 同时用于估算及实际行高，表头 32px。保留排序后的原始索引映射、head/tail 预览、编辑及删除定位，不替换成全量 DOM 表格。 |
| T11 | Studio 全局变量表 | `domains/workflows/components/LogPanel.tsx:962`；`components/WorkflowEditor.tsx:1795` | 共享原生表格及 Studio 令牌适配；保留变量名/值/类型、内联编辑、删除与空态。 |
| T12 | Studio 暂停变量表 | `domains/workflows/components/DebugBar.tsx:118`；`components/WorkflowEditor.tsx:1593` | 共享原生表格和具名滚动区；保留真实暂停状态、变量格式化与受限高度，不改变继续/单步/停止命令。 |
| T13 | Studio 文档 Markdown 表格 | `domains/workflows/components/documentation/MarkdownRenderer.tsx:162`；`documentation/DocumentationDialog.tsx:391`，入口 `components/Toolbar.tsx:1691` | 原有 Markdown 渲染输出加共享表格类和具名可聚焦滚动 wrapper；列头保留原生语义，文档内容与其他 Markdown 排版保持。 |
| T14 | Studio AI 助手回复 Markdown 表格 | `domains/workflows/components/assistant/MessageBubble.tsx:260`；`assistant/AIAssistantPanel.tsx:1282` | 先调用 `renderSafeMarkdown` 消毒，再用 DOM 装饰添加表格类、列头 scope 和“助手回复表格”滚动区域；通过 Studio CSS 覆盖旧 `.ai-md` 表格规则。保留消毒边界和原有回复流程。 |

## 共享实现与适配边界

| 源码路径 | 职责 |
|---|---|
| `shared/components/ui/table.tsx` | 原生表格、表头 scope、ref、具名键盘滚动区域；业务选择状态由调用者提供。 |
| `shared/components/ui/table-toolbar.tsx` | 组合独立控件，使用 `role="group"`，不新增查询状态或工具栏方向键协议。 |
| `shared/components/ui/table-status.tsx` | 文字加色点的紧凑状态呈现，主要状态文字 14px。 |
| `shared/components/ui/search-input.tsx`、`pagination.tsx` | 搜索框可选前置图标、紧凑分页；保留原值、回调和服务端页码事实。 |
| `styles/tables.css` | 唯一基础视觉令牌及细网格规则：主要正文 14px、普通单行目标 32px、含按钮行允许 40px、多行增高、工具控件 32px。 |
| `domains/workflows/styles/table-system.css` | 将 Studio 颜色变量映射到共享表格令牌；适配虚拟表和旧 Markdown CSS 优先级，不建立另一套业务组件。 |

记录查询的筛选、排序、显示列继续使用三个互斥草稿；查询弹层单独带表格查询样式类。普通表单、页面导航和确认抽屉的外层操作不因表格密度被全局压缩。次要帮助文字与标签可保持其原有层级；IP、上下文、业务状态等主要值使用 14px。

## 计数与证据口径

- 同表新增行及其单元格编辑器属于 T01；Excel 样例是独立嵌套表 T06。
- T10 是真实虚拟数据表；只搜 `<table>` 会遗漏它。T13、T14 由 Markdown 动态生成，也必须沿渲染器盘点。
- 项目/数据表卡片目录、代理组成员复选列表、Studio 日志流与工作流卡片选择器不属于这 14 张表，保持现有形态。
- `development/table-system/main.tsx` 是开发专用的真实组件合成资料展示入口，不计为第 15 处业务消费者；其中基础场景也不是 `DataRecordsTable` 真实页面。
- 盘点依据：`git status`、`rg` 搜索 `TableScroll`/`Table`/`ROW_HEIGHT`/`renderSafeMarkdown`，逐项读取实现与调用点。源码接入已确认，不等于 14 处均通过真实应用、平台或用户手测。
- 自动报告、截图和最终通过范围由主协调补充；操作步骤见 [manual-test.md](manual-test.md)。
