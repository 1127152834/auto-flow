# 数据记录行尾连续录入规格

日期：2026-09-14。状态：**proposed，待详细方案确认；用户已选择第一种视觉方向。**

本说明是侧对话的独立设计产物，不代表主线程已暂停、合并或完成任何实现。只读检查的实施工作区 HEAD 为 `3bf74dddea65c43723bde1918f758229ea80926e`；相关页面存在主线程未提交修改，实施时必须重新核对并协调文件所有权。

## 1. 目标与变更范围

新增记录直接在现有数据表末尾完成：点击“新增行” → 在单元格输入或粘贴 → 校验 → “保存 N 行” → 留在记录列表。

视觉以[用户选中的第一种原型](../../project-management/design-alignment/record-grid-entry-2026-09-14/selected-prototype.png)为准。保留顶部导航、项目页头、两组页签、现有表格和暖灰/黏土棕令牌。仅在表格内增加草稿行、尾部新增入口及底部保存条。不得另开新增表单页、弹窗、抽屉，也不把所有已保存记录改成可直接编辑的电子表格。

原型中的具体记录、计数、时间是演示数据。实现时已保存数量和草稿数量分开，例如“4 条记录”与“未保存 · 新增 2 行”，不能把草稿算进服务端总数。系统身份的草稿编号显示“保存后生成”；不得在客户端预分配业务编号。

本方案仅替代旧原型中“新增记录表单”的入口和操作方式。已有记录详情、编辑、删除、业务状态、查询、Excel 文件导入/导出、批量状态规则继续沿用。工作流、同步、整表编辑、公式计算、合并单元格、格式刷、拖拽填充不在范围内。

## 2. 实际代码依据与复用决定

以下路径相对实施工作区。结论来自文件读取，不是运行验收。

| 现有文件 | 已有事实 | 本次决定 |
|---|---|---|
| `apps/desktop/src/renderer/domains/project-data/components/DataRecordsTable.tsx` | 真实记录展示、选择及打开/编辑/删除回调 | 同一表体追加草稿行，保留已保存行行为 |
| `apps/desktop/src/renderer/domains/project-data/components/RecordQueryToolbar.tsx` | 创建及查询工具入口 | 创建改为追加并聚焦草稿行 |
| `apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.tsx` | 创建路由、列表、编辑协调及文件流程装配 | 接入独立草稿协调 Hook，不在大页面内堆积单元格逻辑 |
| `apps/desktop/src/renderer/domains/project-data/record-draft.ts`、`scalar-draft.ts` | 类型、缺失/null/空文本、日期精度、数字、只读字段处理 | 复用并小范围抽出逐单元格校验，支持同时定位多个错误 |
| `apps/desktop/src/renderer/domains/project-data/components/ScalarValueEditor.tsx` | 已有标量控件和类型交互 | 复用其基础控件和转换规则，不把整个纵向表单塞进格子 |
| `apps/desktop/src/renderer/domains/project-data/records-api.ts`、`data-command.ts` | 单条创建、Operation 查询及未知结果处理 | 增加批量命令，复用原查询体系和 lookupOnly |
| `apps/desktop/src/renderer/domains/project-data/use-data-table-editing.ts` | 草稿作用域、旧单条创建恢复 | 保留旧 pending 操作；新网格使用独立版本化存储键 |
| `apps/backend/src/autoflow/adapters/http/project_data_records.py`、`project_data_record_schemas.py` | 单条 POST、读取、修改、状态操作 | 新增有界批量创建，不删除单条接口 |
| `apps/backend/src/autoflow/application/project_data/records.py` | 单条命令规范化、类型校验和操作身份 | 增加批量输入规范化 |
| `apps/backend/src/autoflow/infrastructure/database/project_data_records.py` | 单条创建在自身短事务中提交记录、操作和变更证据 | 新增单事务多行写入，禁止循环调用会自行提交的 create |
| `apps/backend/src/autoflow/infrastructure/database/project_data_models.py` | 变更证据具有 `(operation_id, sequence)` 唯一约束 | 批量证据按行分配不同 sequence；现有单条 helper 固定为 1，不能直接循环复用 |

## 3. 行与单元格模型

### GE-01 草稿身份及范围

草稿组绑定 `workspaceId + projectId + tableId + datasetGeneration`，并记住开始编辑时的 `tableRevision`。每行使用客户端 UUID `clientRowId`，只用于定位草稿和响应映射，不充当持久记录键。单元格按 `fieldId` 保存原始输入和 `ScalarDraft`。

服务实例仅用于请求隔离，不进入草稿身份；同工作区重连保留草稿。另一工作区、表或代次不能复用这批输入。真实切换工作区仍经过已有切换保护。

### GE-02 空行与值语义

- 表格末尾常驻一条未参与保存的新增占位入口；点击后创建空白草稿行。
- 全部可写单元格均为 `missing` 的行不进入保存请求。空白占位行不触发必填错误。
- 显式 `null`、空字符串 `""`、数字 `0`、布尔 `false` 都是有意义的输入，不能当空行丢弃。
- 单元格辅助菜单提供“留空（未填写）”“设为空值”，文本字段另有“设为空文本”。占位视觉与真实空字符串使用说明或标记区分。
- 一旦一行存在有意义输入，该行参加整行必填校验；必填字段缺失、null、空文本按现有规则拒绝。
- 系统身份由提交事务生成；业务字段身份必须输入合法值并通过表内唯一性校验。带类型键继续区分文本 `"001"`、文本 `"1"`、整数 `1`。
- 新行业务状态为 null、环境关联为空、三类记录修订初值沿用现有创建行为；不按自动化含义预设状态。

### GE-03 布局与查询关系

草稿行追加在当前页已保存记录之后，并使用浅暖色底、细分隔线和当前单元格强调边框。不能把草稿塞进服务端排序结果，不能把草稿纳入导出、批量状态和已保存记录选择。

开始录入时临时显示创建所需的必填可写列及业务身份列；只是本次编辑可见列集合，不改用户保存的列偏好。系统/计算/只读列不可填写。字段顺序沿用表结构和已应用可见列，不按字段名猜测映射。

存在非空草稿或未决提交时，筛选、快捷搜索、排序、分页、选列、重新导入暂时禁用并显示“请先保存或放弃新增”；防止输入位置或数据代次悄悄变化。可复制已有内容，已有编辑/删除入口采用离开保护。空白且全 missing 的草稿可直接丢弃，不制造无意义确认。

保存完成后保留原查询、排序和页码，刷新真实结果。新记录若不在当前筛选/分页中，显示“已新增 N 条记录，部分记录不在当前列表中”，不宣称保存失败、不强制清空筛选或打开详情。

### GE-04 输入、键盘与焦点

| 操作 | 行为 |
|---|---|
| 点击“新增行”或尾部入口 | 追加一行并聚焦首个可写单元格；滚动限于表格容器 |
| 单击格子 / 双击或 F2 | 前者选中，后者进入格内编辑；直接键入字符也进入编辑 |
| Tab / Shift+Tab | 提交当前本地输入并横向移动，跳过只读格；末格继续到下一草稿行 |
| Enter | 编辑模式完成当前输入并向下移动；末行按需创建下一空白行 |
| Shift+Enter | 文本编辑模式插入换行；浏览模式不触发保存 |
| Escape | 编辑模式撤回当前格本次未确认输入并退出编辑；不清空整批草稿 |
| Delete/Backspace（格子选择态） | 将选中的草稿格设为 missing；绝不删除已保存记录 |
| Ctrl/Cmd+Z（格子选择态） | 撤销本次草稿动作，最多保留 50 个动作；输入框编辑态使用原生文本撤销 |
| Ctrl/Cmd+Enter | 等同点击“保存 N 行”，经过同一完整校验 |

输入法 `isComposing` 和组合输入期间的 Enter/Tab 不触发移动、增行或保存。长文本在格内截断，激活后可用轻量单元格编辑浮层；日期/枚举等复用自有视觉控件和成熟可访问行为，不调用系统默认日期面板替代设计。

网格使用行列语义、一个 roving tab stop；编辑器有“第 N 行 · 字段名”可访问名称。错误使用 `aria-invalid`、`aria-describedby`，首个错误格在保存失败时滚入视野并获得焦点。底部保存条不能遮住最后一行，横向滚动限于表格。

### GE-05 Excel 多行粘贴

在格子选择态处理 `paste` 事件的 `text/plain`；不新增系统剪贴板读取权限或文件 IPC。文本编辑态的粘贴保持文本输入语义。页面给出“选中单元格可粘贴多行；双击可编辑长文本”的提示。

解析制表符、CRLF/LF、引号内制表符/换行和双引号转义。从当前可写格向右、向下按列位置映射；只覆盖草稿，不能落入已保存记录。粘贴范围超过剩余可写列、命中只读列或超过限额时整次粘贴拒绝，现有输入不变；不截断和静默跳列。

未加引号的空 token 为 missing；被引号包裹的空 token 在文本列为显式空字符串，在其他列报类型错误。只去掉换行产生的最后一个空解析行，不删除中间行、前导空格或文本前导零。空 token 覆盖原草稿值时明确成为 missing，可撤销。

布尔值只接受 `true/false`（不区分大小写），其他文本保留原文并报错；数字、日期精度、时区按现有 scalar 规则解析。`=SUM(...)` 等在文本字段保持文本，不能执行公式。单元格类型错误保留原始输入并标红，整次粘贴作为一次撤销动作。

初期建议上限：每次保存 100 行，规范请求 UTF-8 不超过 1 MiB；原始粘贴文本不超过 1 MiB。超限原输入不变，提示使用现有 Excel 文件导入。这些是本方案新增限制，不能写成当前系统已具备的能力。

## 4. 一次保存的真实语义

### GE-06 推荐新增原子批量创建

“保存 N 行”对应一个操作：全部写入或全部不写。一个错误不能造成部分新增；不通过 N 次单条 POST 拼成假批量。

拟新增：`POST /api/v1/projects/{projectId}/tables/{tableId}/records/batch`。

```ts
type DataRecordBatchCreate = {
  datasetGeneration: string;
  expectedTableRevision: number;
  rows: { clientRowId: string; values: DataCellWrite[] }[];
};
type DataRecordBatchResult = {
  records: { clientRowId: string; record: DataRecordView }[];
};
type DataRecordBatchResponse = DataRecordBatchResult & {
  operation: ProjectOperationView;
};
```

引用的 `DataCellWrite`、`DataRecordView`、`ProjectOperationView` 复用现有 DTO。新 Operation kind 为 `createRecords`，resource 为表，result 保存上述 `DataRecordBatchResult` 的不可变提交快照。每行证据 resource 指向其真实 RecordRef，sequence 为请求行序号加一。

请求带 `Idempotency-Key`。规范请求摘要包含项目、表、代次、结构修订、行顺序、clientRowId 和按 fieldId 规范化的单元格值；JSON 对象键序变化不构成不同请求，行顺序/值变化构成不同请求。禁止重复 clientRowId、重复 fieldId、空 rows，禁止客户端写入状态/关联/修订。

事务内先找原操作并比较摘要，再检查项目可写、表归属、代次与结构、字段类型与约束、批内及已有记录身份冲突。收集行错误后整批拒绝。通过后在同一短事务提交全部记录、逐行变更证据和操作快照。响应首发 201，重放 200。不新增后台队列、Operation 表或数据库迁移；若实施时发现新增持久约束确需迁移，先单独评估，不偷偷改变此设计。

后台表结构变更必须被 `expectedTableRevision` 检测；与本批无关的现有记录内容更新不应误报记录内容 CAS 冲突。身份唯一约束仍由数据库兜底。已导入异常单元格不参与本次新行校验，也不能阻止新增正常行。

### GE-07 错误协议

沿用 `{error:{code,message,details,requestId}}`。新增批量行错误以 `details.rowErrors` 表达，元素为 `{clientRowId, fieldId: string|null, code, message}`；无特定字段的错误 fieldId 为 null。全局错误保留现有错误码，不假设每个错误都有行号。

| 情形 | 结果 |
|---|---|
| 空请求、行数或字段校验失败 | 422；整批不写；可定位错误保留草稿 |
| 超过 1 MiB 限额 | 413；整批不写；明确减少行数或走 Excel 导入 |
| 记录键重复 | 409 RECORD_ALREADY_EXISTS；指出冲突行/身份字段；整批不写 |
| 相同键不同规范请求 | 409 OPERATION_PAYLOAD_MISMATCH；禁止改用新键自动重试 |
| 结构版本冲突 | 409 REVISION_CONFLICT；保留输入，读取新结构后明确确认再编辑 |
| 旧数据代次/归属失效 | 沿用现有领域错误；冻结旧草稿，不自动绑定新代次 |
| 项目归档/切换中/服务拒绝写 | 沿用现有准入错误；保留输入并说明原因 |
| 网络中断、响应丢失、不可判定 5xx | 进入待核验；不能把请求失败等同于未写入 |

前端校验用于即时定位；服务端是最终权威。Python 正则不编译成 JavaScript 冒充一致校验。动态类型错误保留原文，不把非法数字变成 0、非法日期变成另一时区值。

### GE-08 草稿、提交与恢复状态

| 状态 | 可做事项 | 禁止事项/后续 |
|---|---|---|
| draft / invalid | 输入、粘贴、撤销、移除草稿行；保存时定位错误 | 未通过校验不能发 POST |
| submitting | 展示“正在保存 N 行…” | 冻结输入与重复提交；取消网络请求不等于撤销写入 |
| uncertain / recovering | 以原 key 查询 Operation，可离开视图并保留恢复证据 | 不改 payload、不换键、不显示“未保存成功所以可重试” |
| confirmedNotAccepted | 明确原操作不存在后允许原 key、原 payload 重发，或放弃 | 不把一次查询网络失败当不存在 |
| rejected | 展示确定校验/冲突事实；用户修改后生成新命令身份 | 不自动修改业务值重试 |
| schemaStale / generationStale | 保留只读草稿，可复制内容、放弃；同代次按 fieldId 对照新结构确认 | 不按名称猜字段，不把旧代次草稿直接发给新数据 |
| succeeded | 持久化结果收据，清理该批已确认行，恢复查询操作并刷新 | 不因旧响应清空后来的草稿、不重复 Toast |

保存前先持久化不可变 pending（工作区、表、代次、key、payload、行映射）；存储失败时阻止 POST，明确提示。普通草稿存储失败保留内存并提示“尚未保存草稿”，不能虚称已自动保存。

复用项目 Operation 的 by-idempotency-key 查询；恢复使用 `lookupOnly`。只有可信的 OPERATION_NOT_FOUND 才解锁原请求重发。Abort、超时或新的服务实例到来都不能证明命令未提交。

成功后先记已完成收据，再删除草稿；重启遇到收据或 pending 都先查询/恢复，不再创建第二批。作用域检查覆盖缓存、弹窗、Toast 和本地草稿清理。操作去重键包含工作区和原操作身份。

新网格草稿使用独立版本键，不覆写旧编辑 Hook 的存储。旧 `createRecord` 结果不明时先由旧恢复逻辑查清；旧新增 URL 在恢复后 replace 到表列表并只初始化一次草稿入口。不能删除旧 pending 信息来实现路由跳转。

### GE-09 离开与放弃

“放弃新增”只清理尚未提交的草稿；存在有意义输入时需确认。取消确认后 URL、焦点和输入不变。保护覆盖全局导航、页签、记录详情、浏览器前进/后退和真实工作区切换。窗口关闭使用已有退出保护及持久草稿，不拦截系统强杀；下次启动恢复。

已接受或结果不明的操作显示“离开视图”，不能显示“取消保存”。离开后仍保留其查询恢复入口。已有文件/编辑任务忙碌时不能启动第二个冲突写入流程。

## 5. 验收定义

- UI：新增入口不跳转、不弹表单；草稿嵌入原表体；尾部加行和底部统一保存清楚可见。
- 数据：单行与多行都走同一批量命令；原子、幂等、状态 null、类型身份及历史输入语义不变。
- 交互：键盘、中文输入、多行粘贴、单元格错误、丢失响应恢复和离开保护通过真实应用测试。
- 视觉：以选中图对齐正常编辑状态；错误/保存中/未知结果等新增状态按照同一布局补截图，不声称用户已确认这些新状态。
- 兼容：既有单条 API、旧 pending 恢复、已保存记录详情和编辑、查询与文件流程回归。
- 本文仅给出规格；当前业务测试、真实 Electron、Windows 和打包验收均未执行。

实施步骤和逐条测试用例见[实施计划](../plans/2026-09-14-record-grid-entry.md)。


## 实施补记（2026-09-14）

状态：用户已授权实施，独立分支 `codex/record-grid-entry`。本规格只替代新增记录交互，父任务其他原型不因此改变。

新增已使用同表草稿行；保存条在视口底部固定，内容预留空间，防止放大后找不到保存入口。默认保留现有表格的记录身份、业务状态、最近修改与操作列，没有伪造图中业务字段。旧代次 pending 允许仅查询历史结果，核验成功后不向新代次再发创建请求；非 pending 旧草稿可明确放弃后开始新代次录入。
