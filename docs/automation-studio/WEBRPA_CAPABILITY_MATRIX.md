# WebRPA 能力盘点与 AutoFlow 迁移决策

> 2026-09-13 范围更新：用户要求编排、执行、日志、录制、Debug 等工作台核心完整对齐，排除企业、Windows 控制、发布/版本等管理能力。参见 [核心对齐里程碑](../superpowers/plans/2026-09-13-automation-studio-core-parity-milestones.md)；本文 P0/P1/P2 是早期阶段划分，核心范围内的“暂缓”不能作为最终排除依据。

## 1. 目的与边界

本文以 `reference/WebRPA` 固定快照 `5ccb900e8dcf1530aae66f676d87593c416c7ebb` 为基线，回答三个问题：

1. WebRPA 已经覆盖了哪些能力；
2. AutoFlow Automation Studio 首期需要哪些能力；
3. 每项能力应该移植、重写还是暂缓。

WebRPA 是参考项目和能力来源，不是 AutoFlow 的运行时依赖。AutoFlow 的工作流格式、节点协议、执行引擎、编辑器和 CloakBrowser 适配层必须由 AutoFlow 自己定义。

> **迁移策略修订（2026-09-11）**：目标改为“代码级复刻 + AutoFlow 架构归位”。在已获授权的前提下，优先保留 WebRPA 的模块类型、配置字段、流程语义、事件、日志、调试行为和前端交互契约；不为追求形式上的“原创”而重命名或重写成熟实现。只有以下变化默认允许：放入 AutoFlow 的包和进程边界、替换为 CloakBrowser 运行时、Windows/macOS 适配、移除明确排除的模块，以及有测试或复现证据支持的缺陷修复。

本文第 3、5 节中 `browser.*`、`element.*` 等命名属于早期“原生重建”草案，不再作为代码级复刻阶段的硬性命名要求。复刻阶段优先沿用 WebRPA 的 `moduleType` 和配置契约；待行为对齐且确有架构收益时，再通过显式迁移方案调整命名。

## 2. 快照观察结果

| 观察项 | 结果 | 对 AutoFlow 的结论 |
| --- | --- | --- |
| 前端 | React + TypeScript + Vite + React Flow + Zustand | 可以参考画布、模块面板和调试交互；状态模型重写 |
| 后端 | FastAPI + Pydantic + Playwright + Socket.IO | 可以参考 API 分层和事件流；运行时改为 CloakBrowser 专用适配层 |
| 执行器声明 | 83 个 executor 文件、598 个 `module_type` 声明、556 个唯一类型；存在 42 个重复声明 | 不复制执行器目录；先建立 AutoFlow 节点注册表 |
| 产品文档口径 | README 宣称 571 个模块 | 不能把模块数量当作迁移目标，必须以首期场景和稳定性验收为准 |
| 录制器 | 页面注入脚本，监听 click、dblclick、input、select、check、keypress、drag、scroll、navigate 事件 | 适合提取事件模型和选择器提示字段；录制器需适配 AutoFlow IR |
| 元素拾取 | 页面覆盖层 + 选择器生成 + 相似元素查询 + 命中高亮 | 作为 P1 能力重写，优先保证选择器稳定性和可解释性 |
| 调试 | 日志、暂停、继续、单步、断点、从指定节点开始执行 | 作为 Kernel 和 Studio 的一等能力设计，不照搬 UI 状态 |

主要参考位置：

- `backend/app/models/workflow.py`：工作流、节点、边、变量、执行结果和日志模型；
- `backend/app/executors/base.py`：执行器协议、注册机制、执行上下文、选择器等待和选择器自愈；
- `backend/app/executors/basic.py`：基础浏览器节点；
- `backend/app/executors/advanced_browser.py`：表单、滚动、上传、下载和元素集合操作；
- `backend/app/services/browser_engine.py`：共享浏览器上下文、页面和标签页管理；
- `backend/app/services/recorder.py`：网页事件录制和事件缓冲；
- `backend/app/api/recorder.py`、`backend/app/api/element_picker.py`：录制器和元素拾取 API；
- `frontend/src/types/workflow.ts`：模块类型全集和节点数据结构；
- `frontend/src/components/workflow/WorkflowEditor.tsx`、`ModuleSidebar.tsx`、`ConfigPanel.tsx`、`DebugPanel.tsx`：编辑器交互参考。

## 3. AutoFlow 首期节点范围

### P0：首个可用版本必须具备

这些节点组成最小闭环：打开浏览器、定位元素、执行交互、提取结果、完成控制流。

| AutoFlow 节点 | WebRPA 对应能力 | 首期要求 |
| --- | --- | --- |
| `browser.open` | `open_page` / `use_opened_page` | 在 CloakBrowser 中创建或复用页面并导航；支持等待策略 |
| `browser.close` | `close_page` | 关闭当前页面或结束会话 |
| `browser.reload` | `refresh_page` | 刷新当前页面 |
| `browser.back` | `go_back` | 后退 |
| `browser.forward` | `go_forward` | 前进 |
| `element.click` | `click_element` | 单击、双击、右键；支持点击后跟进新标签页 |
| `element.hover` | `hover_element` | 移动到元素并等待可交互状态 |
| `element.fill` | `input_text` | 填充文本；支持输入前清空；密码字段默认敏感处理 |
| `element.select` | `select_dropdown` | 按 value、label 或 index 选择 |
| `element.check` | `set_checkbox` | 设置复选框或单选框状态 |
| `element.scroll` | `scroll_page` | 页面或元素滚动 |
| `element.upload` | `upload_file` | 选择文件并上传 |
| `element.text` | `get_element_info` | 读取文本、value、href、src 或属性并写入变量 |
| `element.exists` | `element_exists` | 返回元素是否存在 |
| `element.visible` | `element_visible` | 返回元素是否可见 |
| `browser.wait` | `wait` / `wait_element` / `wait_page_load` | 时间、元素状态和页面加载等待 |
| `browser.switch_tab` | `switch_tab` | 按当前页、最后页或索引切换标签页 |
| `browser.switch_frame` | `switch_iframe` / `switch_to_main` | 进入和退出 iframe |
| `browser.dialog` | `handle_dialog` | 接受、取消或输入浏览器对话框 |
| `browser.evaluate` | `inject_javascript` | 在当前页面执行受控 JavaScript |
| `flow.set_variable` | `set_variable` | 设置字符串、数字、布尔、数组和对象变量 |
| `flow.condition` | `condition` | 变量、元素存在、元素可见和文本条件 |
| `flow.loop` | `loop` / `foreach` | 计数循环、条件循环和集合循环 |
| `flow.break` | `break_loop` | 跳出当前循环 |
| `flow.continue` | `continue_loop` | 继续下一次循环 |
| `flow.log` | `print_log` | 输出用户可见日志 |
| `flow.screenshot` | `screenshot` | 保存当前页面截图或作为执行附件 |

P0 的目标是覆盖以下黄金流程：导航、表单填写、登录、列表读取、条件判断、循环处理、截图和失败诊断。

### P1：首个版本稳定后实现

| 能力 | 对应参考 | 实施意见 |
| --- | --- | --- |
| 页面元素拾取 | `element_picker` 服务和页面覆盖脚本 | 重新实现覆盖层，返回 selector、tag、文本、属性、矩形和 hints |
| 网页录制 | `recorder.py` | 先录 click、input、select、check、navigate；拖拽和快捷键随后加入 |
| 选择器候选 | `build_fallback_selectors` | 设计明确的 selector 优先级和自愈日志，禁止静默改写工作流 |
| 子流程 | `subflow` | 等工作流 IR 稳定后加入，避免过早引入跨文件依赖 |
| 数据提取 | `extract_table_data`、多元素读取 | 先输出数组/对象，不引入 Excel 资产系统 |
| 调试 | `/debug/resume`、`/debug/step`、breakpoints | 运行上下文必须支持暂停、单步、节点高亮和从节点运行 |

### P2：暂缓

以下能力在当前范围内不进入 Automation Studio 首期：

- OCR、验证码和图像识别；
- Windows 或 macOS 桌面自动化；
- Android、ADB、手机投屏；
- 媒体、音频、视频和摄像头；
- QQ、微信、飞书等平台专用节点；
- AI 爬虫、AI 元素定位和自愈式流程改写；
- 数据库、Excel、Word、PDF 等办公自动化节点；
- 工作流版本历史、WebDAV、市场、计划任务和企业 RBAC；
- DrissionPage 等第二浏览器运行时。

## 4. 移植、重写和暂缓决策

| 范围 | 决策 | 原因 |
| --- | --- | --- |
| 工作流模型 | 重写 | AutoFlow 需要稳定、可版本化演进但不引入历史版本产品功能的自有 IR |
| 节点注册 | 重写 | WebRPA 存在重复声明；AutoFlow 应由单一注册表生成 schema、UI 元数据和执行器映射 |
| 执行上下文 | 重写并吸收经验 | 保留变量、日志、iframe、标签页和取消控制的概念；去除全局可变状态 |
| 浏览器管理 | 重写 | 必须强绑定 CloakBrowser，不能沿用可切换 msedge/chrome/firefox 的入口 |
| 基础浏览器操作 | 优先代码级移植 | 在授权范围内保留成熟执行逻辑和行为契约，仅将浏览器调用收口到 CloakBrowser 适配层 |
| 选择器格式化与等待 | 选择性移植 | 思路成熟；实现必须适配 AutoFlow 的 Target 和超时策略 |
| 选择器自愈 | 重新设计后实现 | 自愈必须可解释、可观测、可关闭，不能无提示改变用户流程 |
| 录制事件监听 | 选择性移植 | 事件类型和去重策略有参考价值；事件输出改为 AutoFlow 命令和目标模型 |
| 元素拾取覆盖层 | 重写 | 交互要服务于 Studio，返回结构也必须由 AutoFlow 定义 |
| React Flow 画布 | 优先代码级移植 | 保留可用的节点渲染、配置面板和交互行为，再按 AutoFlow 应用边界调整导入和状态依赖 |
| WebRPA 的综合模块 | 暂缓 | 会把 OCR、桌面、媒体、办公和平台集成的依赖带入首期运行时 |

## 5. AutoFlow 目标领域模型

节点不直接暴露 WebRPA 的 `moduleType` 字符串，而使用 AutoFlow 命名空间：

```text
browser.*       浏览器会话和页面生命周期
element.*       元素定位与交互
flow.*          变量、条件、循环和流程控制
data.*          文本、数组、对象和表格数据
debug.*         日志、截图、断点和诊断
```

每个节点需要同时定义：

- `type`：稳定的 AutoFlow 节点类型；
- `input_schema`：用户配置和变量引用规则；
- `output_schema`：节点产生的变量或数据；
- `runtime_requirements`：需要的浏览器能力；
- `error_policy`：失败、重试、跳过和停止策略；
- `ui_metadata`：名称、图标、分组、帮助文本和配置表单；
- `executor`：唯一的后端执行器实现。

这样可以从同一份节点定义生成前端节点面板、属性表单、后端校验和执行器路由，避免 WebRPA 中类型、标签、配置面板和执行器分散维护的问题。

## 6. 评估方案

### 黄金流程

首轮建立 10 个可重复运行的本地测试页面或测试场景：

1. 打开页面并等待 DOM；
2. 点击按钮并验证结果；
3. 填写普通输入框和密码框；
4. 选择下拉项和设置复选框；
5. 等待异步元素出现；
6. 读取文本、属性和列表；
7. 打开新标签页并切换；
8. 进入 iframe 后操作并返回主页面；
9. 条件分支和集合循环；
10. 失败时输出节点、选择器、页面 URL、截图和可行动诊断。

### 每个节点的验收指标

- 首次成功率；
- 重复运行成功率；
- Windows 与 macOS 一致性；
- 元素定位耗时；
- 超时和取消是否生效；
- 错误是否包含节点 ID、目标、页面和建议；
- 是否能在无 WebRPA 目录时独立构建和运行；
- 是否只通过 CloakBrowser 执行浏览器操作。

### 阶段退出条件

只有当 P0 黄金流程全部可运行、可调试、可重复，并且 `reference/WebRPA` 从运行时依赖图中移除后，才进入录制器和高级选择器开发。

## 7. 下一步开发任务

1. 在 `packages/workflow-ir` 定义 Workflow、Node、Edge、Variable、Target、ExecutionEvent；
2. 在 `packages/automation-nodes` 注册 P0 节点及其 schema；
3. 在 `packages/browser-cloak` 完成 CloakBrowser 健康检查和页面会话接口；
4. 在 `packages/workflow-executor` 用一个 JSON 工作流跑通 `open → click → fill → text → condition → loop`；
5. 建立黄金流程测试夹具；
6. 再开始 Studio 画布和元素拾取 UI。

## 8. 代码级复刻实施规则

### 保持不变的契约

- WebRPA 的 `moduleType` 名称和节点配置字段；
- 节点输入、输出、分支 handle 和循环语义；
- 工作流保存结构、执行状态、日志事件和调试操作；
- 录制事件类型、元素提示字段和选择器测试行为；
- 用户已经依赖的编辑器交互和配置默认值。

### 允许改变的内容

- 文件位置、Python/TypeScript 包边界和导入路径；
- Electron 桌面壳、FastAPI sidecar 进程监督和跨平台路径；
- 浏览器启动、会话、页面和标签页实现，使其唯一依赖 CloakBrowser；
- 删除明确不进入产品的 OCR、桌面、媒体、Android 等模块及其重量级依赖；
- 能被测试、复现或静态审查证明的问题修复。

### 每个源文件的迁移记录

代码迁移时建立源文件到目标文件的清单，至少包含：

```text
source_path
source_commit
target_path
action: port | adapt | fix | omit
changed_behavior
verification
```

`fix` 必须记录问题现象、复现方式、修改原因和回归测试；没有证据的“优化”不应混入复刻提交。

### 实施顺序

1. 迁移 WebRPA 的工作流模型、执行器基类、注册机制和基础执行链；
2. 迁移基础 Web 执行器，保持 `moduleType` 和配置契约；
3. 迁移工作流 API、日志/调试事件和前端类型；
4. 迁移 React Flow 编辑器、模块面板和配置面板；
5. 迁移录制器、元素拾取和选择器测试；
6. 将浏览器服务替换为 CloakBrowser 适配层并完成 Windows/macOS 验证；
7. 按排除清单移除不需要的模块和依赖；
8. 通过黄金流程与 WebRPA 快照进行行为对照，最后再做局部重构。

代码级复刻阶段禁止同时改变“模块语义、数据格式和界面行为”。每次提交应尽量只做一类变化，以便定位差异来源。

## M4 实施差异（2026-09-13）

本节按用户明确批准的 M4 规格更新，优先于本文早期“字段必须不变”的迁移建议。仍不承诺 WebRPA 文件/协议兼容或全部核心能力已完成。

| 来源（固定基线 5ccb900e） | AutoFlow 目标 | 动作与已批准差异 | 验证 |
| --- | --- | --- | --- |
| `backend/app/executors/control.py:17` ConditionExecutor | `domain/workflows/control_values.py`、`application/workflows/execution.py` | adapt：保留条件分支能力，改为 all/any 可视化规则和 typed literal/variable；不沿用字符串真假值转换，字段/索引缺失明确失败 | 严格值规则单测、真实页面短路/零匹配/非法定位 |
| `control.py:241` LoopExecutor 与 `control.py:307` ForeachExecutor | `domain/workflows/control.py`、`application/workflows/execution.py` | adapt：统一 loop.mode=count/foreach/while、配对结束节点，不展开列表或绘制回边；1-based只读局部变量、列表快照、每循环和全局调度上限 | 嵌套 break/continue、列表变更不改变遍历、1000轮及上限测试 |
| `control.py:349` BreakLoopExecutor、`:364` ContinueLoopExecutor | 同上 | adapt：仅最近一层循环，不提供普通后继连线；分支可以提前转移，正常路径必须汇合 | 结构编译、真实 worker 与条件内 continue |
| `basic_variable.py:58` IncrementDecrementExecutor | `control_values.py:set_value` | adapt：合入 set_variable 的 assign/add/subtract/append；不把缺失值自动初始化为0，不将字符串隐式转数字 | 严格类型、深复制、真实浏览器累积结果 |
| 原控制节点/编辑交互与 React Flow 画布 | `control-model.ts`、`ControlFields.tsx`、`WorkflowCanvas.tsx` | adapt：以现有 AutoFlow 文档/布局/会话分层实现；配对整块复制/删除，32层结构化控制范围，手动保存 v2 | 编辑测试、正式 Electron 保存重开与执行 |
| 原结果/日志能力 | 原 seq/SSE 加 executionId/loopPath、SQLite 产物索引 | adapt：每次执行和产物独立标识，不用静态节点完成数判断终态，首屏50产物及游标分页 | 历史迁移、55次真实提取与断点续读、重启后读取 |

M4 未移入：range/infinite 等额外循环入口、调度、子流程、错误分支、重试、Debug、录制。未完成项仍由顶部核心对齐目标追踪。[专项验收与证据](../migration/automation-studio-m4-validation.md)。

## M5 实施差异（2026-09-13）

以下差异来自用户明确批准的 M5 计划。固定参考仍为 `5ccb900e8dcf1530aae66f676d87593c416c7ebb`；没有复制旧服务或建立第二套执行器。

| 源码来源 | AutoFlow 目标 | 动作与批准的差异 | 验证 |
| --- | --- | --- | --- |
| `backend/app/services/workflow_executor.py:329` configure_debug、`:336` debug_resume、`:348` set_breakpoints | `application/workflows/debug.py` 与现有 execution.py | adapt：保留节点前暂停、断点和单步；明确控制节点一次调度、独立 executionId/轮次；暂停不计入网页节点预算 | 双层循环逐条单步、循环重复命中、12秒真实暂停、纯变量暂停停止 |
| `backend/app/api/workflows.py:388` 启动选项与 `:921` 后续调试接口 | 原 runs API 与 debug/commands | adapt：从文档级即时控制改为运行快照资源上的稳定 commandId、pauseId、controlRevision；状态由 worker 确认并持久化，同标识异内容409 | 重复单步/迟到暂停拒绝、命令仓储恢复、HTTP契约 |
| `workflows.py:656` start_node_id | `domain/workflows/debug.py` | adapt：只允许顶层直接起跑；真实嵌套路径使用运行至此，缺少输入显式补充，不制造分支和局部变量 | 跳过无效上游配置、手动导航后真实执行、嵌套目标未达与非法起点 |
| `frontend/src/components/workflow/DebugPanel.tsx`、工作流编辑工具栏 | AutoFlow DebugStart/DebugPanel/RunLogs | adapt：使用正式组件、草稿隔离；可见临时浏览器，失败保留现场直到结束；没有“单节点日志占位”入口 | 正式开发/构建/打包入口，真实变量修改与页面结果、失败后清理 |
| 原日志与变量诊断能力 | 原 SQLite seq/SSE + purpose诊断索引、文件引用、原生流式导出 | adapt：调试专属检查点及增量追加，普通运行不增加追踪成本；结果与诊断分别计数和导出；全库筛选 | 1000轮、大于64KiB变量、分页、ZIP/JSONL/诊断JSON、重启读取 |

不宣称旧协议或文件格式兼容。旧 M4 段落里的 Debug“未完成”是当时状态，已由本节与 [M5专项验收](../migration/automation-studio-m5-validation.md)替代。子流程、错误处理/自动重试、录制、双视图、分组注释及其余网页动作仍未交付。
