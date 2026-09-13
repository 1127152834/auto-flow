# 项目管理按原始 Gallery 还原 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: 使用 superpowers:subagent-driven-development 分包，规格审查后工程审查；交付使用 verification-before-completion。以下复选框为执行任务，当前不得视为已完成。

**Goal:** 只把原型全局菜单改为现有顶部导航，恢复原始内容结构与交互，重新交付R1、完成R2和R3。

**Architecture:** 保留现有React领域组件、真实API、命令恢复和隔离状态；先修页面组合，不重写数据层。R3聚合接口沿用已批准事务设计。

**Tech Stack:** Electron、React/TypeScript、Tailwind、Radix/shadcn、RHF、TanStack Query、FastAPI/SQLite、Vitest、pytest、Electron/CDP及原生电脑操作。

---

日期2026-09-13；基线df263df。状态：本轮文档修订，未实施。权威规格：[原始原型还原规格](../specs/2026-09-13-project-management-gallery-fidelity.md)。本文件替代旧计划中的视觉基准和相关页面组合任务；不替代正确的后端事务/身份/恢复任务。工作区仍为 `/Users/zhangtiancheng/Documents/projects/autoflow-project-management-implementation`，主项目与旧仓只读。

## A. 计划变化与保留

| 原安排 | 修订 |
|---|---|
| B0作为实施/截图基准 | 取消该用途；直接绑定gallery latest原PNG |
| R1视觉完成，继续R2 | 重开R1视觉验收；保留原功能测试证据，不回滚已正确业务 |
| 紧凑项目头、独立表页签、表头y≤380 | 废止；按原图项目头→项目页签→一体内容卡片组织 |
| 新增/编辑与详情共享左右分栏 | 拆开呈现：详情按003分栏；新增004/编辑005通栏 |
| R3字段/来源/设置按B0延展 | 直接按008/009/010/012/014/100-field-impact组织，既有聚合合同不改 |
| 每阶段完整测试后自动进入下阶段 | 保留此前连续授权；当前先交付修订计划。计划进入实施后仍必须逐阶段过门槛，最终停R3 |

执行顺序：**G0 原图绑定和共用结构 → R1重验 → R2还原及完整操作 → R3字段/数据闭环 → 最终全链验收**。不安排新的生成图阶段。

## B. 文件责任

所有 `renderer/` 路径前缀为 `apps/desktop/src/renderer/`。新增路径明确写Create；主协调独占页面装配、共享CSS/API生成/迁移/公共账本。实现智能体一次领取一个文件边界清晰的包。

| 包 | 修改范围 | 负责人/依赖 |
|---|---|---|
| G0 | `domains/projects/components/ProjectHeader.tsx`、`ProjectTabs.tsx`；Create `domains/project-data/components/DataTablePageFrame.tsx`及.test.tsx；`domains/projects/pages/ProjectsWorkspace.tsx`、`project-data/pages/DataTableDetailPage.tsx`；只必要领域样式 | 前端组件智能体做Frame；主协调装配；先于R1/R2 |
| R1 | projects `ProjectCard.tsx`、`ProjectDirectory.tsx`、`ProjectDirectoryPage.tsx`；project-data `DataTableDirectory.tsx`、`DataTableDirectoryPage.tsx`、`DataRecordsTable.tsx`、`RecordQueryToolbar.tsx`、`RecordFilterEditor.tsx`、`DataTableFormDialog.tsx`及相邻测试 | 组件→页面；保留HTTP与查询合同 |
| R2 | `RecordEditPage.tsx`、`RecordDetailPage.tsx`、`RecordEditorForm.tsx`、`RecordFieldsView.tsx`、`ScalarValueEditor.tsx`、`RecordStatusDialog.tsx`、`DataDeletionDialog.tsx`及相邻测试；现有`record-route.ts`、`record-return-state.ts`、`use-data-table-editing.ts`只按真实缺陷修复 | 前端组件智能体；主协调持有路由/恢复装配 |
| R3后端 | 原R3-01–05完整文件范围：schema DTO/domain/repository/application/http、守卫迁移、状态usage、生成API类型与对应unit/integration/contract测试 | 后端智能体；迁移及生成由主协调串行集成 |
| R3前端 | 原R3-06–07的SchemaEditor/FieldDrawer/ImpactDrawer/schema-draft、DataStatusTable/TableSettingsForm，现有SourcePanel、Excel向导/导出/批状态组件 | 接口完成后组件→页面；不提前生成mock正式页 |
| QA | `scripts/qa-project-alignment-r1.mjs`、`qa-project-alignment-r2.mjs`、`smoke-project-data.mjs`、`smoke-pm2-detail-flows.mjs`；Create `scripts/verify-gallery-baseline.mjs`及.test.mjs；Create `acceptance/gallery-r1/`、`gallery-r2/`、`gallery-r3/`证据目录 | QA智能体；暂停中的未提交脚本先登记交接，不覆盖 |

不对共享组件目录整体重写；ScalarValueEditor等多消费者先检查默认行为，页面专用呈现不改变原Dialog/复杂筛选语义。参考旧仓功能前，定位其真实源码/提交与测试，登记“直接复用/适配/不可复用原因”；不因旧代码不在工作树就认定不存在，不把旧样例数据带进正式应用。

## G0：冻结原图并修复共用结构

- [ ] 重新核对HEAD、dirty、QA进程及文件责任；保留当前未提交QA/外链脚本与历史run，不执行git reset或整目录覆盖。
- [ ] 检查 `gallery-baseline/source-manifest.json` 每个原文件的hash/尺寸/标题。112个图库引用中latest91个、候选与历史21个；same-day-variants/history不自动升级成基准。latest内原标“修订候选”的图保留其历史标签，作为本修订计划拟采用来源随计划审阅，不伪称历史已批准。逐个当前实现页面登记来源；只看过的图标为已看。
- [ ] 在每阶段 `page-map.json` 中登记路由、原PNG、入口、退出、当前对应组件、原图区域、必要业务差异与证据类型；所有未执行证据为null。字段删除、Sheets、全部目录等按规格§4登记，不以“尺寸适配”掩盖功能差异。
- [ ] 写 `DataTablePageFrame.test.tsx` 反例：内容卡片内同时包含表头、五个页签和子页；004/005表单无complementary区，003保留状态区；顶部项目名称与说明可见，表页签不在外卡片之外。
- [ ] 运行组件测试确认旧结构失败。实现展示Frame，只接收header/tabs/notice/children/footer插槽，不请求API、不持有业务草稿；沿用项目头和Tab行为。装配放回原图中的区域，不造第二路由层。
- [ ] 创建项目与表后从UI进入列表/新增/详情/编辑，按001–005各拍一张真实结构图。检验内容包裹关系、标题与页签、主次按钮、100%比例、200%不裁切；先规格审查再工程审查。
- [ ] 在隔离分支提交G0明确文件。G0没有通过，不批量迁移余下页面。

测试命令（后续各包使用实际路径参数，不从根误传给未知runner）：

```bash
npm test --workspace @autoflow/desktop -- DataTablePageFrame.test.tsx ProjectHeader.test.tsx DataTableDetailPage.test.tsx
npm run typecheck
npm run lint
npm run build
```

## R1：目录、记录列表和查询重新验收

- [ ] ProjectDirectory保留最近/全部独立查询和偏好，恢复原图两列卡片比例、图标块/名称/描述/时间/更多及底部全部入口；时间标签必须与实际值一致。全部状态为原图衍生，单独登记，不引用B0紧凑条目证明。
- [ ] DataTableDirectory恢复原卡片数量层级、来源/状态/底部分隔与打开动作；不填假统计。新建表Modal对齐016，保留空白本地表实际能力。
- [ ] Records恢复002同卡片的数量/搜索/筛选/显示列/新增、表内查看/编辑/更多及底部分页。现有导出/批状态/排序与指定字段搜索入口按page-map登记，保留能力、不再新增常驻第二栏。
- [ ] Filter复用当前表达式编辑器，017的基本条件/状态与清空、取消、应用顺序保持；复杂AND/OR/NOT切换不丢树、不截短。无变化应用不请求，取消/Escape/遮罩只丢草稿，选列不触发后端读取。
- [ ] 写/运行目录、卡片、工具条与查询反例；保留原有效查询与导出一致、菜单不误打开、工作区状态隔离测试。不得删除因结构变化失败的业务断言。
- [ ] 完成T01–04、T12–14和PM2回归，按原PNG并排检查每个页面及打开浮层图，GF全部通过。重新生成R1报告与manual-test.md，不覆盖旧报告；双审无阻断后独立提交并进入R2。

## R2：按原图修复记录整页

- [ ] RecordEditPage去掉B0右侧状态/异常说明卡与卡片外标题；创建/编辑标题放在同一外卡片左上，表级页签在右；保留原表单session和onSubmit路径。
- [ ] RecordEditorForm按004/005恢复通栏标签/输入行、帮助、分隔、日期入口、摘要Textarea。补顶部错误数和逐字段错误定位、底栏修改数/取消/保存；输入格式不能破坏null、空串、0、false、日期精度与异常单元格证据。保存中/结果未知仍冻结原提交。
- [ ] RecordDetailPage只按003保留左右区：左业务字段，右项目内状态及原元信息；取消B0额外时间卡，恢复编辑+更多操作关系。受控外链继续使用已完成主进程校验。
- [ ] 未保存确认对齐006，包含当前记录/修改字段与继续编辑；007删除确认显示对象、影响、来源文件不受影响、取消和确认。真实未知结果只能查询原操作，不能用重新布局引入第二writer。
- [ ] 冲突/恢复等未有专图的状态先完成原页面位置映射；不得直接沿用B0对照分栏并声明还原。请求身份、session撤权及CAS反例保留，错误恢复不得换键盲重发。
- [ ] 逐条执行T05–09和T12–14；截图至少含详情、状态下拉、新增、编辑、校验、未保存、删除取消/进行中、冲突与未知恢复。缺图状态检验正确性及与父页面一致性，不给虚假“原图匹配分”。
- [ ] 两个真实工作区和同工作区服务恢复实测，浏览器历史前进/后退取消后URL与表单一致；返回恢复完整query、列、分页、滚动、来源行焦点。双审及R2退出门槛通过后独立提交。

## R3：字段、状态、来源和设置完整闭环

后端严格执行原R3-01–05（按当前真实路径重新核对），包括新增字段聚合preview/commit、真实usage、迁移顺序、全字段候选、版本守卫、Operation原子性、≤1000行与写后整行JSON≤4MiB预算。旧单字段接口与历史结果保留。

- [ ] 后端先写失败测试再实现，完整类型只在真实handler接通后生成。预览后记录/状态/结构变更均使提交冲突；字段/回填/Operation任何一处故障均回滚整次。
- [ ] 字段页直接按008表格，009右抽屉；应用只更新本地candidate，取消不改变父草稿；外层“保存字段”才预览。影响抽屉按100-field-impact的分段结构列真实变化与阻断，未来引用显示不可用，不伪造0。
- [ ] 字段删除仍不在本阶段合同；对应位置明确暂未开放。系统身份/不可写/公式字段受保护，不得因原图有删除字样新增未批准破坏操作。
- [ ] 010状态页用真实引用信息填表；创建/重命名弹窗和删除保护保持原交互。012来源用事实表和重导入影响区；014设置为页内表单、取消/保存及离开保护。
- [ ] 已有Excel导入/重导入/导出及批状态保留完整入口和持久恢复。没有原图的每步以对应父页及公共控件编写状态映射，再实施，不用B0替换整页。
- [ ] 完成T10–14、性能/原子性自动测试、真实文件选择与表格文件内容核对；重新跑R1→R2→R3完整链。逐包审查、最后全量检查；独立提交后停R3，不进入PM3。

## C. 端到端逐条验收目录

每条拆成具体case，报告字段固定为 `id, fixture, steps, expected, actual, screenshotIds, source, sourceHash, revision, evidenceType, status`。下表是必测最小范围；正式manual-test.md将每一步点击/输入/预期和故障命令写全。用户手测结果初始为“未执行”。

| 用例 | 前置与具体步骤 | 必须证明的事实/截图 |
|---|---|---|
| T01 | UI新建“内容采集A/B”；从全部先开A再B；返回；点击A更多编辑并取消 | 最近顺序真实；菜单不触发打开；原目录卡片/底部入口图 |
| T02 | UI建“资料库”，说明“保存文章资料”；修改说明后打开并返回 | 真实卡片更新、原项目头和表内容结构、原创建Modal |
| T03 | QA工具仅在标记工作区准备52项目/120记录；搜索、排序、第二页打开返回 | 条件/页码/滚动恢复；筛选、排序、选列取消不生效，应用才改变 |
| T04 | 选择标题搜“温室”；叠加业务状态；清空搜索；选列；导出当前筛选 | AND语义与导出记录一致；选列没有新的记录查询；Popover不撑宽 |
| T05 | UI建记录编号/标题/文章链接/发布日期/摘要字段；UI新增R019；保存到本地→详情 | 004通栏布局、003详情布局；只有一次真实新增；原来源文件未变 |
| T06 | 编辑R019；清空必填标题、修改摘要；保存；改正标题再保存 | 005顶部错误摘要+行错误+焦点；错误零PATCH，摘要保留；成功后详情新事实 |
| T07 | 未保存时点取消/表页签/项目页签/全局导航；浏览器back/forward；选继续编辑 | 006确认；原输入和URL恢复一致；选择丢弃才离开 |
| T08 | 从列表更多删除→取消，再进入详情更多删除→确认 | 007内容、影响范围和操作位置；取消无DELETE，确认一次；不修改来源 |
| T09 | UI编辑后QA用真实HTTP竞争修改；提交冲突；保留/重新编辑；丢响应并重载后核验 | 原输入/typed身份不串；采用最新revision才重发；不明结果原key查询；故障注入明确标注 |
| T10 | UI改两个字段；抽屉应用、取消另一字段；外层预检；外部改记录后确认；再次预检保存 | 008/009/impact；抽屉零写入；冲突无部分保存；成功原子一次，状态/link不变 |
| T11 | UI建状态并单条/批量设置清空；制造块冲突；删除被引用状态 | 引用真实、块内原子；区分修改/冲突/未执行；重启查询不重复写 |
| T12 | 原生选择合成XLSX→检查/映射/导入→本地编辑→重导入→筛选选列导出 | 源hash不变；新代次不继承旧状态；导出实际内容/前导零/日期正确；原生操作与preload注入分开 |
| T13 | R019草稿服务重启；未知保存时重载；切换第二真实工作区再回；重启应用 | 记录草稿与业务事实不串；同工作区保留；切换期间禁写；历史晚响应不污染 |
| T14 | 各正式页100%/200%、长文本、Tab/Enter/Escape；详情点击真实HTTP/HTTPS外链 | 布局/内部滚动/焦点恢复；OS浏览器实际打开；其他协议/子frame拒绝自动测；已有浏览器/代理/模型/设置/Studio入口回归 |

核心流程E1=从真实UI开始；E2=真实API准备规模数据/竞争修改/事实核对；E3=直接路由/preload入口，不冒充用户导航；E4=合成故障/响应注入，不冒充真实系统故障。每个case可包含多种，逐步骤标注，不把整个run统一抹成E1。

## D. 截图及退出条件

- 每张原图先定位其应用内容区边界，登记裁切坐标；保留完整原图及实图并排。侧菜单改顶部的几何差异单列，不能裁掉项目头或卡片底栏。记录原图尺寸与实际1440×1024 CDP内容视口、原生窗口尺寸，额外拍200%。
- 正常状态在Toast自然消失且字体加载完成后拍；加载/保存中用明确延迟或真实处理中捕获，延迟注入单列；错误/弹窗/下拉逐一截图。不能以缓存读取未触发loading的失败脚本判产品通过。
- GF硬性关系全部通过才评分；每页≥85但结构错误直接不通过。新页面匹配不能用目录平均分抵消。应用截图差分候选不自动覆盖，B0历史图不再参与评分。
- `verify-gallery-baseline` 只核验原文件hash、映射引用、必测状态和证据文件；不能自动把人工视觉或业务验收设passed。纯文档检查不算功能通过。
- 每阶段必须有源码提交、自动日志、双审问题闭合、真实E2E、原图对照、实际截图、手测方案。普通缺陷修复并复验；无法自行解决才报告阻断。Windows/其他架构/打包未执行如实记录。

R1/R2适用检查：

```bash
npm test
npm run openapi:check
npm run typecheck
npm run lint
npm run build
npm run test:scripts
npm run test:structure
node scripts/qa-project-alignment-r1.mjs
node scripts/qa-project-alignment-r2.mjs
node scripts/smoke-project-data.mjs
node scripts/smoke-pm2-detail-flows.mjs
git diff --check
```

R3最终增加原计划全量 `uv run --directory apps/backend pytest`、`ruff check .`、`mypy src`（后两者也通过uv同目录执行）、`smoke-project-alignment.mjs`及`measure-schema-commit.py`；新增脚本须先按原R3-08实际交付，不能本轮声称存在/已执行。

## E. 本轮计划静态核验

- 已只读重新查看17张原图（其中004来自用户附图），登记全部112个图库源文件与91个latest，SHA/尺寸均来自实际文件。
- 未重新运行应用；没有新的页面匹配评分或业务通过结论。
- 历史B0视觉结论撤销其当前权威性；保留原报告内容及实际自动测试事实。
- 本轮只改规格、计划、原图索引与协作状态，代码与QA进行中改动原样保留。
