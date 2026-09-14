# 行尾连续新增记录 Implementation Plan

> **For agentic workers:** 使用 Superpowers `executing-plans` 逐项执行、`verification-before-completion` 核验。本文由 `writing-plans` 编写。本侧对话不派发智能体、不执行主线程任务；正式实施须先确认本规格并取得相关文件独占修改时段。

**Goal:** 用同一表格内的草稿行和一次原子保存替代新增记录表单，交付键盘连续录入、多行粘贴、单元格校验及断线恢复。

**Architecture:** React 项目数据领域新增小型草稿状态机和单元格组件，复用 ScalarDraft、现有表体和 Operation 查询；FastAPI 新增有界批量创建，在一次 SQLite 短事务中提交记录、变更证据和操作结果。已有单条创建、记录编辑及文件能力保持兼容。

**Tech Stack:** 现有 React / TypeScript / TanStack Query / shadcn-Radix / Tailwind / Electron / FastAPI / SQLAlchemy / SQLite / Vitest / pytest。计划不引入完整电子表格引擎或新的后台执行器。

---

## 0. 依据、状态和文件所有权

日期：2026-09-14。状态：**用户已授权实施；独立分支实现中，G4 验收逐项登记。**

- [业务与交互规格 GE-01–09](../specs/2026-09-14-record-grid-entry.md)。其中原子批量保存、限额和键盘细则为本次推荐方案，不伪称已单独获得确认。
- [选中原型](../../project-management/design-alignment/record-grid-entry-2026-09-14/selected-prototype.png)，真实尺寸 1487×1058，[来源及 SHA-256](../../project-management/design-alignment/record-grid-entry-2026-09-14/prototype.json)。
- 只读核对工作区：`/Users/zhangtiancheng/Documents/projects/autoflow-project-management-implementation`，HEAD `3bf74dddea65c43723bde1918f758229ea80926e`。
- `DataRecordsTable.tsx`、`RecordQueryToolbar.tsx`、`DataTableDetailPage.tsx` 及对应测试等存在其他任务未提交改动。此次只新增本计划、配套规格和选中图资产；不合并、不重置、不代提交任何主线程文件。
- 主目录 `/Users/zhangtiancheng/Documents/projects/autoflow` 和旧项目只读。执行者在当前页面所有者提交并交接后，重新核对 HEAD 和差异；从已交接提交创建独立实施 worktree。不能把主线程未提交目录覆盖进新分支。
- 旧记录新增页规划仅在本范围被替代。不能借此更改项目导航、目录、其他数据页，或继续执行父线程的 R1/R2/R3。

### 交付阶段

| 阶段 | 交付 | 门槛 |
|---|---|---|
| G1 合同与保存 | 真实有界原子批量接口和幂等查询 | 行错误不写半批、重复请求不重复新增；旧接口回归 |
| G2 表格录入组件 | 草稿模型、键盘、粘贴、格内校验、底部保存条 | 组件行为通过，视觉保持原表格，尚不宣称真实页面交付 |
| G3 页面与恢复 | 真实页面接入、原请求核验、草稿与工作区保护 | UI→后端完整闭环，旧单条 pending 不丢失 |
| G4 E2E 与截图 | 本机端到端、逐状态截图、手测方案、报告 | 正常和故障链通过后才可交付 |

每个任务按：失败行为测试 → 运行确认失败原因 → 最小实现 → 定向复验 → 规格审查 → 工程审查 → 修复复核 → 明确文件提交。测试失败必须由缺失目标行为引起，不能以导入拼写错误当作行为反例。以下保留原任务清单，实际执行与证据以文末实施记录为准；未验证细项不批量勾选。

## 1. 文件责任图

路径均相对独立实施工作区；标为“新增”的文件当前不存在，是实施目标。

| 路径 | 操作及责任 |
|---|---|
| `apps/backend/src/autoflow/adapters/http/project_data_record_schemas.py` | 修改：请求/响应及行错误 DTO |
| `apps/backend/src/autoflow/adapters/http/project_data_records.py` | 修改：batch handler；静态 batch 路由放在动态记录路径之前 |
| `apps/backend/src/autoflow/application/project_data/records.py` | 修改：规范化 create_many 命令 |
| `apps/backend/src/autoflow/domain/project_data/records.py` | 修改：repository Protocol 的 create_many |
| `apps/backend/src/autoflow/infrastructure/database/project_data_records.py` | 修改：单事务创建多行及逐行证据；不让共享 helper 自行提交 |
| `apps/backend/src/autoflow/adapters/http/project_schemas.py`、`projects.py` | 修改：Operation kind/查询序列化接纳 createRecords |
| `apps/desktop/src/renderer/shared/api/generated.ts` | 唯一生成类型，真实 handler 完成后由集成者生成 |
| `apps/desktop/src/renderer/domains/project-data/record-grid-draft.ts` | 新增：草稿、有效行、选择、撤销、字段错误的纯状态逻辑 |
| `apps/desktop/src/renderer/domains/project-data/record-grid-clipboard.ts` | 新增：TSV 解析和有界矩形粘贴，独立于 React |
| `apps/desktop/src/renderer/domains/project-data/record-draft.ts` | 小范围修改：共享单格校验和错误收集；旧 recordValues 语义不变 |
| `apps/desktop/src/renderer/domains/project-data/components/RecordGridCellEditor.tsx` | 新增：格内输入及特定类型轻量浮层 |
| `apps/desktop/src/renderer/domains/project-data/components/RecordDraftRows.tsx` | 新增：同一表体内草稿行、尾行入口及行删除 |
| `apps/desktop/src/renderer/domains/project-data/components/RecordDraftSaveBar.tsx` | 新增：计数、保存/放弃、保存中/核验中反馈 |
| `apps/desktop/src/renderer/domains/project-data/record-grid-storage.ts` | 新增：版本化持久信封校验、pending/收据、容量错误 |
| `apps/desktop/src/renderer/domains/project-data/use-record-grid-entry.ts` | 新增：单一草稿会话、保存与恢复协调 |
| `apps/desktop/src/renderer/domains/project-data/records-api.ts`、`data-command.ts` | 扩展批量 API 和必要类型投影；复用 lookupOnly，不改变其他命令默认行为 |
| `apps/desktop/src/renderer/domains/project-data/components/DataRecordsTable.tsx`、`RecordQueryToolbar.tsx` | 修改：表体组合、创建入口；待原所有者交接 |
| `apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.tsx`、`record-route.ts` | 修改：真实页面和旧 create URL 一次性转换；待交接 |
| `apps/desktop/src/renderer/domains/project-data/use-data-table-editing.ts` | 仅在旧 pending 恢复接入所需位置修改；不删除旧恢复实现 |
| `scripts/qa-record-grid-entry.mjs` | 新增：隔离 Electron 端到端与手测工具 |
| `docs/project-management/design-alignment/acceptance/record-grid-entry/` | 新增：manual-test.md、用例结果、截图和报告 |

前端所有新增纯逻辑和组件使用同目录同名 `.test.ts` / `.test.tsx`。后端新增测试见各任务。预计不改迁移、数据库模型、业务状态、通用 UI 令牌和主进程文件 IPC。发现需要扩展这些边界时说明原因并修订计划后处理，不能悄悄改动。

## 2. 任务 1：基线交接与冻结契约（准备）

**Files:** 本计划、配套规格；确认后才同步 `docs/project-management/implementation/api-contracts.md`、相关阶段交付记录。

- [ ] 记录实施 worktree 的 HEAD、分支、未提交文件、主目录 HEAD，确认计划所列三个正在修改的页面已由原所有者交接；保留其完整功能。
- [ ] 重读 AGENTS、`.ai/README.md`、`.ai/memory/project-context.md`、gallery-only-navigation-change ADR 和结构文档；只更新本范围结论。
- [ ] 对照实际代码确认 `_table` 的写准入、代次错误、结构版本字段以及现有单条校验。记录哪些错误可明确证明未提交，哪些必须查询。
- [ ] 将 GE-06/07 精确加入公共接口文档：DTO、100 行/1 MiB 上限、原子性、createRecords、行定位、查询恢复、201/200；保留原单条 API。
- [ ] 检查状态和来源页面不在变更清单，确认 UI 修改只替代新增入口。同步父阶段记录时明确“新增表单由本计划取代”，不改其他原型。
- [ ] 审查合同和文件边界后提交文档；建议提交主题 `docs: define inline record creation contract`。

**退出：** 没有文件所有权重叠、第二套创建规则或把图示数字当业务事实的描述。

## 3. 任务 2：原子批量仓储与应用服务（G1）

**Files:** 上表 domain/application/database records；新增 `apps/backend/tests/integration/test_project_data_record_batches.py`。

- [ ] 增加反例 `test_invalid_second_row_leaves_no_records_or_operation`：第一行合法、第二行必填缺失，断言记录、操作和变更证据均无新增。
- [ ] 增加 `test_batch_replay_keeps_original_rows_and_snapshot`：两行同 key 重放仍只有两条，后续编辑首行后重放返回初次快照。
- [ ] 增加 `test_duplicate_identity_in_batch_and_database_is_atomic`：批内重复、与已有记录冲突、并发同身份分别验证全批拒绝及 typed key 语义。
- [ ] 运行 `uv run --directory apps/backend pytest tests/integration/test_project_data_record_batches.py -q`，保存明确失败点。
- [ ] 实现 `create_many`：规范每格输入、复用字段校验；在 `BEGIN IMMEDIATE` 后先查幂等，再查项目/表/代次/结构，再验证所有行；收集 rowErrors，不调用单条 commit 方法。
- [ ] 通过后统一写入：每条初值沿用单条创建、操作 resource 为表、result 是 clientRowId→RecordView 映射、每条证据 resource 为对应记录且 sequence 唯一。事务提交前任何异常整批回滚。
- [ ] 增加故障测试：第二条记录插入后抛错、证据写入后抛错、提交前异常都无部分结果；提交后响应层异常不撤销已提交事实。
- [ ] 增加边界：0/1/100/101 行、恰好/超过字节上限、重复 clientRowId、重复 fieldId、missing/null/空文本/false/0、非法日期、结构冲突、旧代次、项目不可写。
- [ ] 运行新增测试及 `tests/integration/test_project_data_records.py`、`test_project_data_catalog.py`；对照 GE-06–08 审规格，再查事务/证据/错误映射质量，修复后提交 `feat: create record drafts atomically`。

## 4. 任务 3：HTTP、Operation 和客户端契约（G1）

**Files:** HTTP schema/router、project operation schema/序列化、`records-api.ts`、生成类型；新增 `apps/backend/tests/contract/test_project_data_record_batches.py`，修改 `records-api.test.ts`。

- [ ] 写契约失败测试：batch 201、重放 200、非法请求 422、身份冲突 409、超限 413、归属/准入拒绝；错误有稳定 clientRowId，不泄漏跨项目记录。
- [ ] 写 Operation 查询测试：原 key 能找回包含完整映射的成功结果；不同项目不能查询；同 key 改行顺序/输入返回 mismatch；JSON 对象键序变化不误冲突。
- [ ] 定向运行新增 contract 测试，记录失败；随后实现 handler 和 kind 支持。沿用认证、QuiesceGate、现有服务装配，不在单服务内调用 HTTP 组事务。
- [ ] 运行 `npm run openapi:generate`，仅提交真实新增类型。实现 `recordsApi.createBatch` 的结果投影：检查项目、表、代次、kind、行映射恰好完整且无重复。
- [ ] 测试未知结果以原键 lookupOnly 查询；404 OPERATION_NOT_FOUND 才得出未接受；查询失败不 POST；服务返回缺行/错代次映射不能清理草稿。
- [ ] 运行 contract 测试、records-api 定向 Vitest、`npm run openapi:check`、`npm run typecheck`。规格审查关注“接受≠成功”，工程审查关注路由、类型和旧调用兼容，修复后提交 `feat: expose recoverable batch record creation`。

**G1 退出：** 新后端真实可测，旧单条接口不退化；不以 HTTP 成功冒充新 UI 已完成。

## 5. 任务 4：草稿、校验和粘贴纯逻辑（G2）

**Files:** 新增 record-grid-draft / record-grid-clipboard 及同名测试；小范围修改 record-draft 及测试；复用 scalar-draft。

- [ ] 写失败测试：全 missing 行不提交；显式 null、空文本、false、0 会参加校验；system ID 未预生成；clientRowId 在增删/撤销中稳定且不等于记录身份。
- [ ] 测试两个字段同时错误时返回两个 `{clientRowId,fieldId}`；隐藏必填列可被定位；只读/计算字段不允许粘贴；旧编辑未修改异常值逻辑继续通过。
- [ ] 运行定向测试，再实现纯 reducer 和派生有效行/错误集合；只抽出已有校验的共用部分，不建立另一个业务校验系统。
- [ ] 写 TSV 测试样例：`001\t温室\r\n002\t阳台`、引号内 tab/newline、`""` 与未加引号空 token、双引号转义、尾换行、空中间行、中文、表情、以 `=` 开始文本；注意测试输入使用真实制表/换行字符。
- [ ] 测试粘贴越列、超行、超字节时整个动作不应用；类型错误保留原输入；一次粘贴一次撤销；文本列 001 不变，数字列不悄悄转成 1。
- [ ] 实现 TSV parser 和矩形应用；不解析 HTML，不计算公式，不新增 Clipboard 权限；每次动作最多检查有界 100 行。
- [ ] 用下列定向命令及 scalar/record-draft 原测试复验，审查后提交 `feat: model spreadsheet-style record drafts`。

```bash
npm test -- src/renderer/domains/project-data/record-grid-draft.test.ts src/renderer/domains/project-data/record-grid-clipboard.test.ts src/renderer/domains/project-data/record-draft.test.ts src/renderer/domains/project-data/scalar-draft.test.ts
```

## 6. 任务 5：先完成格内组件，再展示正常/异常状态（G2）

**Files:** RecordGridCellEditor、RecordDraftRows、RecordDraftSaveBar 及同名测试；DataRecordsTable 组合接口与测试（交接后修改）。

- [ ] 写失败组件测试：新增在同一表体；不出现 Dialog；系统编号占位；已保存行不可通过格子 Delete 删除；保存数量排除空占位行。
- [ ] 写键盘反例：Tab/ShiftTab、Enter 末行增行、Escape 仅撤当前格、F2、中文 IME Enter 不增行、不提交；用真实 focus 断言而不是只检查回调次数。
- [ ] 实现格内输入、错误描述、roving focus、只读单元格、临时显露必填列及新增尾行。基础控件复用现有 Input/Select/Popover/Checkbox 等，不构建另一个 UI 库。
- [ ] 实现 sticky 保存条，预留底部空间；显示草稿数量、保存中、待核验和明确失败。多行文本轻量浮层不变为整行表单。
- [ ] 测试禁用/只读、首错误聚焦、内部滚动、日期浮层 Escape 分层、丢弃取消后焦点回原格；输入控件和通知具备可访问名称。
- [ ] 用选中图建立组件候选截图：普通草稿、选中格、错误格、长文本、保存中；只作为开发辅助，正式验收必须走真实页面。
- [ ] 运行这三个组件和 DataRecordsTable 的定向 Vitest、typecheck/lint。先审结构是否仍是原表格，再审可访问性与状态边界，修复后提交 `feat: add inline record draft rows`。

## 7. 任务 6：持久草稿和命令恢复（G3）

**Files:** record-grid-storage、use-record-grid-entry 及测试；records-api/data-command 必要扩展；旧 editing Hook 兼容测试。

- [ ] 写 storage 反例：工作区/表/代次不同拒绝加载，服务实例变化保留；损坏 JSON/错误版本/超限信封不执行其中命令；localStorage 写失败时不发 POST。
- [ ] 写 Hook 反例：一次保存冻结 key/payload；重复点击只有一次调用；两行中一行被拒时草稿全部保留；响应成功前不能显示已保存。
- [ ] 运行确认失败，再实现版本化存储信封 `{schemaVersion,scope,draftRows,pending,receipt}`；独立于旧 `autoflow:data-edit:*` 键，不读取/执行任意未知版本 payload。
- [ ] 增加并通过状态机测试：提交后响应丢失→lookupOnly→成功收据→清理；查询失败继续未知；确认不存在→显式原请求重发；中途 Abort 不证明未接受。
- [ ] 故障注入：记录收据后清理前刷新、POST 后旧实例响应到达、新工作区已有新草稿、同工作区服务重启；均不能清错草稿、串缓存或重复 Toast。
- [ ] 处理结构变化：按 fieldId 保留输入并显式确认；数据代次变化隔离旧草稿并禁发请求。未知操作先查提交事实，不能仅因当前结构变了丢弃成功结果。
- [ ] 实现有意义草稿离开保护；pending 时仅离开视图、保留恢复入口；已有旧单条 pending 先走旧恢复流程。不要让两个 Hook 同时拥有一个编辑会话。
- [ ] 定向运行新增 storage/Hook、data-command、use-data-table-editing 测试；规格审查关注事实/草稿隔离，工程审查关注存储校验和迟到响应，修复后提交 `feat: recover inline record draft submissions`。

## 8. 任务 7：真实页面与旧入口兼容（G3）

**Files:** 已交接的 DataTableDetailPage、DataRecordsTable、RecordQueryToolbar、record-route 及测试；仅必要的旧 editing Hook 接点。

- [ ] 写页面失败测试：点击新增留在同一 hash/list，表尾出现输入；已有详情/编辑仍可用；旧 create URL replace 一次，不重复增行。
- [ ] 测试脏草稿阻止改筛选/排序/分页/选列/重新导入；放弃后原查询恢复；空白占位不弹保护。批量状态和导出只包含真实已保存记录。
- [ ] 接入组件和 Hook：页面只组合 inputs/actions；toolbar onCreate 变为 append/focus；移除当前 create form 渲染分支，保留 edit 与 legacy pending 恢复。
- [ ] 测试成功后停留列表、原查询不变、数量来自真实后端；新行不匹配当前筛选时提示清楚；失败保持每个原输入。
- [ ] 测试全局导航、项目/表页签、浏览历史和工作区切换：取消后 URL 与 UI 一致；pending 不被丢弃；只读项目不能建立可提交草稿。
- [ ] 运行项目数据领域测试、原记录路由/表单/页面测试，回归 Excel 和批量状态入口；检查页面没有新增独立表单。修复后提交 `feat: create records directly inside data table`。

**G3 退出：** 可在真实页面完成单行/多行创建与恢复。没有用模拟成功、直接 preload 调用代替 UI 流程。

## 9. 任务 8：真实 Electron 端到端与截图（G4）

**Files（新增）:** `scripts/qa-record-grid-entry.mjs`、`scripts/qa-record-grid-entry.test.mjs`、`docs/project-management/design-alignment/acceptance/record-grid-entry/manual-test.md`、`cases.json`、`runs/`。

### 工具与数据准备

- [ ] 复用现有 QA Electron/CDP 启动辅助，新增独立脚本而不覆盖正在使用的 QA 脚本。支持 `--manual` 保持运行；测试目录包含专用 marker，清理只允许本次标记目录，保留截图和报告。
- [ ] 输出实际运行命令、版本、测试工作区、服务端口和截图目录；用户不需改数据库。故障工具只在测试进程拦截响应/执行授权竞争请求，不增加生产调试 API。
- [ ] 准备隔离项目“行内录入验收”和系统身份表“资料库”：标题（必填文本）、文章链接（文本）、发布日期（日期）、数量（数字）、启用（布尔）、摘要（文本）；另建业务文本身份表与整数身份表验证类型区别。
- [ ] 核心项目、表、字段及首条记录通过 UI 建立。批量边界、并发冲突资料允许 API 准备，但每条用例标注 setup 类型；真实粘贴通过系统剪贴板写测试内容后键盘 Cmd/Ctrl+V，不用直接调用 parser 冒充 UI。

### 必测用例

每项都有：前置资料、逐步操作、预期、实际、截图、原型对应、源码/构建版本、证据类型。初始状态统一 `notRun`。

| 编号 / 规则 | 操作步骤 | 逐步预期与事实断言 | 截图 |
|---|---|---|---|
| E01 / GE-01–03 | 从项目进入资料库→点新增行→输入标题“温室光照管理笔记” | hash 不去 create；原记录可见；同表尾草稿；计数尚未增加；系统身份为保存后生成 | V01 |
| E02 / GE-04 | Tab 连续填链接/日期→Enter 进入下一行→输入第二标题→再 Enter | 焦点位置准确；尾部额外空行不计保存；两行淡色草稿；保存条 N=2 | V01/V02 |
| E03 / GE-06 | 点保存 2 行→等待→读取真实记录列表 | 只发一个 batch；新增恰好两条；状态 null；保存条消失；页面仍是列表 | V03 |
| E04 / GE-02/05 | 粘贴含“001”、false、0、中文、引号内换行的矩形资料 | 文本前导零、布尔/数值保留；仅草稿改变；Ctrl/Cmd+Z 整次撤销；恢复后能保存 | V04 |
| E05 / GE-05 | 在最后可写列粘贴两列；再粘贴超过 100 行或 1 MiB 内容 | 整次粘贴不生效、原草稿不变；提示明确；未发 POST | V05 |
| E06 / GE-02/07 | 两行只填第二行必填字段；第一行填其他字段→保存→修正 | 首次定位第一行必填格、整批零新增；修正后才一次新增两条 | V06 |
| E07 / GE-06 | 两个相同业务身份草稿→保存；再制造与另一真实写入身份冲突 | 409 指向身份格；两个场景都无部分新增；原输入保留 | V06 |
| E08 / GE-07/08 | 草稿期间用测试工具修改字段约束→保存→确认最新结构 | 拒绝旧结构；输入按 fieldId 保留；明确确认且重新校验后生成新命令 | V07 |
| E09 / GE-08 | 注入服务已提交但客户端首次响应丢失→点击查询结果→重启应用 | 待核验状态；查回同一批；重启后恰好一次新增，无重复通知或重复行 | V08/V03 |
| E10 / GE-08 | 注入请求确未到服务并使第一次查询断线→恢复查询 | 第一次保持未知不重发；可信不存在后提供原 key/payload 重发；成功只写一次 | V08 |
| E11 / GE-08/09 | 有草稿时切页签/全局菜单/后退→取消；随后确认离开并返回 | 取消后 URL/输入/焦点不变；确认离开后草稿可恢复；未提交不混成持久记录 | V09 |
| E12 / GE-01/08 | 工作区 A 有草稿→切 B 创建不同草稿→切回 A→同工作区服务重启 | 不串输入；A 原草稿仍在；旧实例响应不能清理 B；pending 可查询恢复 | V10 |
| E13 / GE-08 | 旧单条 create 未决资料→加载旧新增 URL；另做重新导入后恢复旧代次草稿 | 先恢复旧操作，不重复创建；旧代次草稿不可自动提交到新代次 | V08/V10 |
| E14 / GE-03 | 先应用“标题含温室”筛选→新增不匹配标题→保存 | 新行真实存在；列表筛选保留；提示当前列表未显示；导出仍按已应用查询 | V03 |
| E15 / GE-04 | 中文输入法候选确认、长文本、日期浮层、Escape、200% 缩放 | IME 不误增行；Escape 先关内层；无应用撑宽；底条不遮最后一行 | V11/V12 |
| E16 / 兼容 | 打开已有记录→编辑→保存；查询、批状态、Excel 导入/重新导入/导出 | 原有完整流程不退化；草稿不进入导出或状态选择 | V13 |

还必须增加自动故障用例：写入第 2 条后回滚、同 key 异请求、提交期间结构竞争、只读/跨项目准入、响应映射缺失。后端原子性用临时数据库断言，不依赖截图证明事务正确。

### 规则与用例对应

| 规格 | 主要实现任务 | 端到端证据 |
|---|---|---|
| GE-01 草稿身份与范围 | 4、6、7 | E01、E12 |
| GE-02 空行与值语义 | 2、4、5 | E03、E04、E06 |
| GE-03 布局与查询 | 5、7 | E01、E14、E16 |
| GE-04 键盘与焦点 | 5 | E02、E15 |
| GE-05 多行粘贴 | 4、5 | E04、E05 |
| GE-06 原子保存 | 2、3、6 | E03、E07；另附事务故障测试 |
| GE-07 错误协议 | 2、3、6 | E06、E07、E08 |
| GE-08 提交恢复 | 3、6、7 | E08、E09、E10、E12、E13 |
| GE-09 离开与放弃 | 6、7 | E11、E12 |

### 截图比对门槛

- [ ] V01 首先使用与选中图相同的 1487×1058 内容视口、100% 缩放；再测应用要求的 1440×1024 与 200%。记录 Electron 内容视口、原生窗口尺寸、DPR、字体、缩放、源码 HEAD/脏补丁哈希、构建哈希。
- [ ] 原型与真实截图逐状态并排，逐项检查：顶部导航、项目页头、两排页签、原表格列结构、草稿位于表尾、无新增表单、浅色草稿、活动格边框、尾部新增入口、底部保存条、横滚与错误位置。
- [ ] 十项结构检查必须全部通过；视觉人工评分按布局 35、信息层级 25、样式 25、交互状态呈现 15 分，每张适用截图至少 85 分，评分人和理由必须记录。不得靠其他页面均分掩盖失败。
- [ ] 静态选中图只覆盖正常草稿状态。其他状态记录为“按本规格新增状态”，不能宣称已有用户确认原型；提供实际截图供手动验收。
- [ ] 像素差分仅用于同环境真实截图的后续回归。候选基线不自动覆盖，不把图像生成中文字/数据差异的整图百分比当业务通过。
- [ ] 失败先修复本用例，再重跑相关回归和截图；禁止删除断言、隐藏错误、降低门槛。

### 工程检查及手动方案

- [ ] 执行以下全量命令，逐项保存退出码和报告。环境不能运行时写阻断与已执行范围，不标通过。

```bash
uv run --directory apps/backend pytest
uv run --directory apps/backend ruff check .
uv run --directory apps/backend mypy src
npm test
npm run openapi:check
npm run typecheck
npm run lint
npm run build
npm run test:scripts
npm run test:structure
node scripts/qa-record-grid-entry.mjs
git diff --check
```

- [ ] 手动方案列出安装/启动命令、`--manual` 用法、用例 E01–16 的精确点击/输入/预期、故障菜单操作、截图目录、通过/失败/未执行记录模板、隔离目录清理方法。不能只写“测试粘贴功能”。
- [ ] 保留 UI 创建、API 预置、响应测试注入、真实竞争请求、直接路由五类证据的区别；本机运行平台据实填写，Windows/其他架构/打包未运行写未执行。
- [ ] 先审 GE-01–09 完整性，再审工程质量/幂等/输入法/焦点/隔离；保存问题、修复提交及复验证据；完成后提交 `test: verify inline record creation end to end`。

## 10. 最终交付和变更控制

- [ ] 交付 G1–G4 提交、实际功能清单、真实应用截图、E01–16 结果、可启动手测方案、剩余限制。
- [ ] 更新真实目录职责、公共契约、`.ai` 阶段记录；只登记本次已验证事实，不覆盖父任务历史或宣称整个 R2/R3 完成。
- [ ] 旧创建表单消费者已移除；只有仍被编辑或历史恢复使用的共享代码保留。确认没有两个普通新增入口造成交互分裂。
- [ ] 100 行/1 MiB 限额测试记录实际机器和耗时；100×6 单元格粘贴后首轮渲染目标 ≤300ms，本地批量保存目标 ≤2s（记录 5 次数据，不用网络 mock）。未达标先分析，不自动放宽；这是实施性能目标，不是已测结论。
- [ ] 方案完成后仅交付“行尾连续新增记录”，不自动继续父线程里程碑或扩展已有记录批量编辑。

## 11. 本次计划编写的验证记录

- 源码依据：已只读核对单条创建、自带事务、Operation 恢复、标量草稿和变更证据 sequence 约束。
- 视觉依据：选中原图已原样复制，尺寸和 SHA-256 可核对；未修改其他原型。
- 文档检查：交付前检查本次新文档链接、文件归属、GE-01–09 与 E01–16 覆盖以及图片摘要。
- 业务代码：本次未修改；应用/端到端/Windows/打包验证：**未执行**。
- 该计划的详细规则仍为 proposed；在用户确认并与主线程完成文件交接前，不启动上述代码任务。


## 2026-09-14 实施记录（当前状态）

- 用户在侧对话授权“开始实施”。在 `autoflow-record-grid-entry` / `codex/record-grid-entry` 独立实现，不派发智能体，不干扰父任务。
- 从 `3bf74dd` 建立 worktree，等待原页面改动提交后快进到 `a6a0e8e`，未复制其他任务未提交文件。
- G1 已实现：createRecords 有界批量 HTTP、短事务原子保存、幂等结果查询及生成类型。没有数据库迁移。
- G2 已实现：同表草稿行、格内编辑、键盘、矩形粘贴、撤销、逐格错误、保存条。保存条固定在视口底部并预留空间，避免 200% 缩放后操作不可见。
- G3 已实现：正常新增入口改为行内录入；旧 create URL 转换，旧单条 pending 保留原恢复流程；工作区持久草稿、未知结果查询、明确未接受后的原键重发、旧代次查询与禁止跨代写入。
- 复用了 `recordValues` 的逐字段校验，没有修改旧 `record-draft.ts`、`scalar-draft.ts` 或旧编辑 Hook。路由转换需要对 App / ProjectsWorkspace 的既有 navigate 增加可选 replace 参数；不增加路由库。
- 规格/工程审查由本侧对话执行者自审。本侧对话禁止子智能体，未宣称完成独立智能体审查。
- 详细自动和端到端结果、未覆盖细项、截图与手测入口以 acceptance/record-grid-entry 下报告为准。用户手测、Windows、打包验收不标通过。

### 本轮交付核验

G1–G3 实现及自动验证完成；G4 已完成主要本机端到端，尚未达到完整退出条件。后端 773、前端 1027 项通过，工程检查通过；实际范围与未执行项见 [核验报告](../../project-management/design-alignment/acceptance/record-grid-entry/verification.json)、[手动测试](../../project-management/design-alignment/acceptance/record-grid-entry/manual-test.md)。本轮为独立分支候选交付，不合并主线，不触发父任务下一里程碑。各包在同一隔离分支顺序实现，最终形成一个可审查功能提交及其文档，没有代提交父任务改动。
