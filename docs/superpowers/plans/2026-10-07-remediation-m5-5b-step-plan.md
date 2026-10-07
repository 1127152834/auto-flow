# M5 5B 数据绑定、试跑与失败处理：步骤级计划

- 日期：2026-10-07；状态：confirmed（决定由实施方按用户授权作出，见 [决定记录](../../../.ai/decisions/2026-10-07-m5-5b-decisions.md)）
- 规格：[M5 规格](../specs/2026-09-30-remediation-m5-experience.md)（R5-12..R5-18、R5-21..R5-25；AC5-03、AC5-05、AC5-08）；任务级计划：[M5 计划](2026-09-30-remediation-m5-experience.md)「5B 数据与运行」Task 1–11
- 依据：2026-10-07 对后端契约、Studio 数据绑定、自动化绑定页、批次监控/总览/时间线、数据表页与试跑五个区域的只读源码调研，以及一次完整性评审（调研未逐条读规格正文，R5 编号与 Task 的对应已由我核对）
- 前置：5A 已完成（[5A 步骤计划](2026-10-06-remediation-m5-5a-step-plan.md)）；M2A/M2B 台账与签名/输出/预览写入后端、M4 身份已交付

## 1. 后端契约就绪度（逐项，来自源码）

| 需要 | 状态 | 证据 / 缺口 |
|---|---|---|
| 流程输入签名读写（字段、类型、必填、敏感） | 就绪 | `domain/workflows/signature.py`；`WorkflowCatalogItem.signature` 只读；写入走整份文档 `content.signature` |
| 签名样例值 | **缺** | `SignatureField` 无 sample（B2） |
| 签名解析失败时的问题暴露 | **缺** | 解析失败返回 `signature=null`，面板会误当"无签名"并覆盖（B3） |
| 签名 outputs | **缺** | 只解析 inputs，`signature_migration.py` 写 `outputs: []`（B12，5B 不做编辑） |
| 节点输出元数据 | 部分 | `domain/workflows/outputs.py` 最小版；无"必有/条件"；只有静态 `schema_export`，无 HTTP（B5） |
| 稳定引用 `{input.组.字段}` / `{node.<id>.<key>}` | 就绪 | `signature.py REFERENCE`、`outputs.py REFERENCE`；旧 `{变量}` 保留到 M6 |
| 写回能力 | 就绪（能力层） | `domain/project_data/capabilities.py`；节点层仍是单一 `project_data` + `ProjectDataConfig.tsx`（JSON textarea 泄漏 fieldId） |
| End（业务结果、保留登录、关联输入） | 就绪 | `domain/workflows/project_end.py`；前端是开关 + 逗号分隔文本框 |
| 输入预览聚合（匹配 N、未处理 M、3 行样例） | **缺** | `InputPreviewResponse` 只有 values/scannedCount/outcome（B4） |
| 台账 state 分段计数、吞吐/ETA、运行中任务摘要、错误码归组、批量重跑/跳过/导出 | **缺** | `processing-units` 仅分页 + state 过滤；`BatchDetail.status_counts` 是任务状态（B7/B8） |
| 周期性截图缩略图 | **缺** | 只有错误/结果截图 artifact（B9，决定降级） |
| 运行总览聚合 | 部分 | `ProjectStatistics`/`ProjectOverview` 有部分；缺并发/上限、今日已处理行、待人工（B10） |
| 数据表台账/身份列 | **缺** | `DataRecordView` 无台账投影（B11） |
| 任务时间线数据 | 部分 | `NodeAttemptView`、`ProjectRunEventView`；"用到的值/产出"的形状与脱敏未核实（B6） |
| 试跑 previewWrites | 部分 | `BatchStartRequest.execution_mode`（`project_run_schemas.py:22`）、冻结入请求（`coordinator.py`）、写后读、claim 跳过预览均已有；**缺 End 启动前预检（B1，现仅运行时 409，网页操作已真实执行）与真实 HTTP+worker+SQLite 端到端验收（B13）** |

## 2. 前端现状要点

- Studio 的 `VariableInput`（563 处使用，原生 input + 下拉）、无 CodeMirror 依赖、无 `tagInput` 开关、无数据侧栏；`ModuleNode` 与 `BlockFlowView` 各有一份 `getSummary`。
- `ProjectInputPanel` 页脚"修改会保存到项目数据"与默认预览矛盾；候选行显示 `recordKey`。
- AC5-03 已知泄漏点：`ProjectDataConfig` 的 fieldId、`ProjectInputPanel` 的 recordKey、`navigation.ts` 与 `DataTableSourcePanel` 的"数据代次"。`copy-lint` 只扫字面量，不扫运行时渲染，需新增运行时渲染扫描测试。
- 自动化绑定页：`InputPlanEditor.tsx` 是 159 行单行 JSX，须先拆分；无自动匹配、无匹配行数。
- 批次/任务页无虚拟化；数据表是服务端页码分页，与行内草稿、批量选择、保存条耦合；任务详情是三标签而非按节点一行。

## 3. 阶段与顺序

**Phase A：数据绑定 + 试跑闭环**（规格要求先做 Task 1/2/3/5/6/11）
**Phase B：失败处理与页面完善**（Task 7/10，再 8/9）

后端缺口里最重的 B7（批次进度聚合，需基准与 loop_lag）与 B4（input-match）作为长线，在 Phase A 期间并行启动。

### Phase A

| 切片 | 内容 | 后端 | 文件所有权（冲突提示） |
|---|---|---|---|
| **A1（第一个切片）Task 11 试跑闭环** | ①后端 B1：`previewWrites` 且工作流 End 配置 `retainEnvironment` 时，启动请求直接 409（沿用 `PREVIEW_CANNOT_SAVE_ENVIRONMENT`，不创建批次/任务），保留 `end.py` 运行时兜底；②前端 `run-project-once` 处理 409：清除 sessionStorage pending，显示原因与建议；③`ProjectInputPanel`：统一为"项目数据仅预览，网页操作仍真实执行"，删页脚矛盾句，候选行用表的主显示字段（`table.identity`）渲染，system 模式回退 recordKey；④B13 真实 HTTP + worker + SQLite 验收：预览前后记录/版本/台账/同步意图/出站/持久环境全不变，再 `realWrites` 对照组发生变化；失败原因进入用户可见日志 | 是 | `ProjectInputPanel.tsx`、`run-project-once.ts`、后端 start 校验与测试（本切片先合入，避免与 A6 冲突） |
| A2 共享引用解析 + AC5-03 骨架 | 前端 `dataReferences`（识别 `input.组.字段`、`node.<id>.<key>`、旧 `PROJECT_INPUTS[...]`、全局变量名四种格式并给出显示别名/类型/来源）；运行时渲染扫描测试骨架（先 skip 已知泄漏，随各页面修复逐个启用） | 否 | 新文件为主 |
| A3 Studio 持有签名 | 前端 Studio 读/写/脏状态 signature；后端 B2 签名样例（敏感字段拒绝）与 B3 签名问题暴露（防覆盖）；OpenAPI 与 `generated.ts` 重新生成 | 是 | `workflows` 域 api/store、`signature.py`、`workflow_catalog.py` |
| A4 后端长线（并行） | B7 批次进度聚合（台账 state 分段计数、吞吐/ETA、运行中任务摘要、稳定 errorCode 枚举）与 B4 `input-match`；附基准与 loop_lag | 是 | 后端为主；Phase B 与 A10 的前置 |
| A5 Task 1 输入与输出面板 | 签名编辑、样例值、从数据表导入；输出区块只读展示 End 业务结果与写回产出（决定 D19） | 否（依赖 A3） | `ProjectInputPanel.tsx` 与 A1 排序 |
| A6 Task 2 数据侧栏 | 输入字段与样例、必有/条件输出（用现有 `nodeOutputs.ts` 生成物，B5 类型暴露后补）、全局变量、凭据 | 否 | Studio 侧栏新组件 |
| A7 Task 5 写回表单 + End 勾选 | 4 个条目作为 `project_data` + operation 的外观层（不新增 moduleType、不改后端执行器）；参数 JSON 折叠到高级；清除 fieldId 泄漏；End 业务结果下拉、"保留当前身份登录状态"开关、"关联到"勾选输入分组名称；文档写明服务批量录入与多账号运营场景（规则 5） | 否 | `ProjectDataConfig.tsx`、`ProjectEndConfig.tsx` |
| A8 Task 4 画布数据可见 | 合并 `ModuleNode`/`BlockFlowView` 的 `getSummary`；节点第二行数据标签、读/写角标、字段高亮、分支连线文字 | 否 | `ModuleNode.tsx`、`BlockFlowView.tsx`、`edges` |
| A9 Task 3 标签输入框 | CodeMirror 6 原子装饰（决定 D15）；`VariableInput` 同名同属性导出，内部按客户端开关 `tagInput` 委托；先默认关，再逐页适配既有测试 | 否 | 最大风险项，不阻塞 A10/A1 |
| A10 Task 6 绑定页 | 先拆 `InputPlanEditor`；自动匹配（名称与类型）、未匹配标红、"当前条件匹配 N 行"+3 行样例（先用 records list 近似；M 与草稿预检待 B4）、多表只读连线图、输出字段一键建列 | 部分（B4） | `project-automations` 域 |
| A11 Task 11 收尾 | 节点旁实际值（B6 先行：核实 `executionContext`/output 事件 payload，缺则补字段与后端脱敏）；AC5-08 完整验收；Phase A 里程碑检查 | 是 | |

### Phase B

| 切片 | 内容 | 后端 |
|---|---|---|
| B1 Task 10 任务详情时间线 | 每节点一行（耗时、用到的值、产出、attempt），失败节点自动展开原因/建议/截图，数据写入与环境保存内嵌 | 否（几乎不依赖后端，可提前） |
| B2 虚拟化基础 | 共享 `virtual-list`（`@tanstack/react-virtual`，决定 D18，写代码前用 Context7 核对 v3 与 React 版本）+ 批次监控数据 hook（可见性感知 ≤2 秒轮询） | 否 |
| B3 Task 7 批次监控 | 分段进度（台账 state）、吞吐/预计剩余、运行中任务卡片（行显示名、身份、当前节点、用时、最近一张已有截图并标明非实时）、全部任务表；失败按 errorCode 归组与批量重跑/跳过/导出（B8，写命令须真实接口验收） | 是（B7、B8、B9） |
| B4 Task 9 数据表页 | 全宽、冻结首列、列宽记忆、行内编辑、右侧抽屉、行操作收进"…"、处理状态左边条；台账/身份列待 B11；虚拟化按基准决定 | 部分（B11） |
| B5 Task 8 运行总览 | 项目内指标行（运行中批次、当前并发/上限、今日已处理行、成功率、待人工数）；跨项目版本归 5D | 是（B10） |

## 4. 验收口径（5B）

- AC5-03：界面可见内部 ID 数为 0，由运行时渲染扫描测试覆盖流程编辑、写回节点、End、绑定页、试跑（A2 起逐个启用）。
- AC5-05：10,000 行批次监控 60fps 滚动、数据延迟 ≤ 2 秒——需要 G2 规模的真实基准与性能脚本，证据放 CI 产物，不入 `docs/`（规则 7）；jsdom 不能证明帧率。
- AC5-08：真实 HTTP + worker + SQLite 的端到端，不能拿 service 层测试代替；界面不宣称网页操作无副作用。
- 每个切片：组件测试 + 契约测试 + 真实入口验证；涉及批量执行的后端改动附 `tests/benchmarks` 前后对比（规则 4）；`ratchets`、`copy-lint`、类型检查、lint 通过；涉及 Studio 的改动做真实窗口实测（见 [Studio 样式陷阱](../../../.ai/knowledge/2026-10-07-m5-5a-studio-css-pitfalls.md)：Studio 只加载 `webrpa.css` 链、`text-sm`=12px、非层级的 `* {border-color}`）。

## 5. 风险

| 风险 | 应对 |
|---|---|
| `VariableInput` 有 563 处使用，替换会碰 ref 语义、label htmlFor、`fireEvent.change` 等既有测试 | 同名同属性导出、内部开关委托；先统计依赖 ref/input 事件的调用点；默认关闭，逐页验证后再开 |
| `ProjectInputPanel.tsx` 被 A1、A5、AC5-03 清理同时触及 | A1 先合入；之后 A5 与清理串行 |
| B7 最重（需基准与 loop_lag） | 在 Phase A 期间并行启动，Phase B 的 B3 才依赖它 |
| 旧引用并存四种格式，后端 REFERENCE 正则对含空格/点的旧变量名无法原子化 | 降级为普通文本；解析器同时显示旧格式别名，避免 AC5-03 泄漏 |
| 周期性截图帧与现有证据模型冲突 | 先降级为最近一张已有截图并标明非实时，Phase B 末尾再评估 |
