# Gallery R3 独立工程与规格评审记录

- 日期：2026-09-14。
- 状态：所列源码问题已复核关闭；阶段最终视觉与完整 E2E 结论待主协调补充。
- 评审范围：R3 后端 candidate/preview/commit 实现后的独立反馈整改；前端 schema API、草稿 Hook、字段与影响抽屉、字段表格、设置及状态引用的页面装配；本轮逐属性变化摘要。
- 权威规格：`docs/superpowers/specs/2026-09-13-project-management-gallery-fidelity.md`、Gallery realignment 计划及 alignment-r3 的事务/身份/预算要求。原始 Gallery 为视觉来源；不使用已撤销的 B0 中转图。
- 独立性：本记录作者实现了后端 schema 纯校验、仓储、应用服务及对应测试；后端两项反馈由主协调/其他审查者提出，作者修复。前端评审由本记录作者只读开展，整改由主协调及其他实现者完成。不能将后端作者自身验证冒充独立代码审查。

## 后端独立反馈及整改

| 问题 | 严重性 | 实际修复 | 验证与结论 |
|---|---|---|---|
| 预览逐行重验全部已有字段，旧字段的正则超时会阻断仅改名称或新增无关字段；与“只校验变化规则”的边界不符。 | P2 | `_validate_rows` 仅对 type/required/validation 发生变化的已有字段执行 `validate_value`；未改字段值原样保留，不重新执行旧正则，不合成新的异常检查 warning。 | 先建立未改字段异常及 timeout 反例，原实现 RED；修复后 GREEN。包含旧超时不能阻断 label/new 默认回填、原异常值保持，以及变更规则时锁外并发写仍使预览失效。已关闭。 |
| 120 秒预算只在行首检查，单行大量变更字段可累计超预算后仍成功。 | P1 | 每次字段验证前后均检查 deadline，验证失败路径通过 finally 同样检查；行处理后再检查。 | 确定性时钟反例：单行两个字段各推进 70 秒，原实现未抛错为 RED，修复后 `FIELD_VALIDATION_TIMEOUT` 且不持久化预览证据为 GREEN。已关闭。 |

后端作者实际执行的定向验证包括：40 个纯候选/DTO 单元测试；后续 schema 集成最终一次为 36 passed。此前连旧 catalog、单字段变更、记录测试合跑为 78 passed；其后 deadline 新反例纳入 36 个 schema 集成，不能将两个不同时间点的计数简单相加为一次全量结果。生产文件 mypy 与定向 Ruff 均完成；阶段全量后端结果由主协调统一登记。

真实集成覆盖：完整字段身份及保护规则、1000/1001 行、4194304/4194305 字节、多个新字段同一记录只回填一次、四个写入阶段异常回滚、双候选并发、预览期间并发写、证据绑定/过期、同 key 冻结重放、跨项目拒绝、归档后的原结果恢复、旧单字段 CAS 双向互操作、代次替换、typed key/slots/status/environment/异常值保持。另通过真实 HTTP Excel 导入建立数据，再调用 schema 服务保存，核对源 XLSX SHA-256、来源元数据、身份和记录键保持。

主协调另报告状态引用投影补显式 `BEGIN`，并完成真实 WAL 并发写 RED→GREEN。作者读取当前实现确认目录、分组计数、批操作投影处于同一读取事务；该并发测试不是作者亲自执行，不重复记为独立运行证据。

## 前端独立评审与闭合

| 问题 | 严重性 | 当前闭合方式与核验范围 |
|---|---|---|
| 结果未知时，影响抽屉禁止关闭且禁用全部底栏，外部核对按钮被 Modal 隔离，用户无法恢复。 | P1 | pending 且非 busy 时允许“返回核对保存结果”，关闭影响面板仅清除展示状态，不删除原 pending；确认提交仍禁用。已读源码及新增测试，静态关闭。 |
| 持久 candidate 只检查 fields 是数组，null/缺 definition 可能崩溃；后续还发现恢复 baseline directory.items 未深验。 | P1 | schemaSave 恢复同时深验 candidate、definition、scalar、FieldDirectory、FieldView/ref/revision 与 scope；损坏存储进入 recoveryBlocked，不交给字段渲染。已静态关闭；主协调报告对应 Hook 31 tests 通过。 |
| 原始 008 的删除位置被移除，未按最新 Gallery 差异规则保留明确禁用能力。 | P2 | 字段行保留 disabled 删除、锁图标及“暂未开放”说明，不增加删除 API。已静态关闭。 |
| 字段列表只有底部修改总数，缺少逐行修改标记。 | P2 | 复用 draft.changes，对新增/已有改动分别显示“新增”“已修改”。已静态关闭。 |
| 设置成功只更新 cache，本地 table 尚未同步就由 effect 重开旧会话，下一次保存可能使用旧 revision。 | P1 | 保存成功同步更新本地 table 和 view cache，新会话从一致新 context 构建。主协调建立连续两次保存的 expectedRevision 反例并完成 RED→GREEN；作者复核当前源码关闭。 |
| 干净 inline 会话一直冻结旧字段与 generation，后台刷新或换代次后仍显示旧快照。 | P1 | clean、可离开、非 disabled/代次警告时同步最新 context；dirty 保留旧快照。重连 catalog pending/error 不卸载现有 schema 会话。作者复核关闭，主协调报告 clean 刷新与 dirty 重连测试通过。 |
| 冷恢复 schema pending，但 URL 是同表其他标签时，无核对入口且 pending 阻止切回 fields。 | P1 | 增加跨标签原字段保存核对区域，使用既有 recover 原 key 查询，不产生新 POST。作者复核关闭，主协调报告 records 标签冷恢复测试通过。 |
| 影响抽屉仅称“修改字段定义”，不能核对具体修改属性。 | P2 | 本轮改为逐属性前后值，具体复核见下一节。已静态关闭。 |

已核对的其他行为：未应用抽屉 dirty 与聚合 candidate dirty 一并上报离开保护；预览 ticket/session 与提交锁隔离迟到响应和重复新命令；未知命令沿原 key 恢复；字段 dirty 背景刷新不覆盖；来源与状态展示不编造未接通的引用数量。最终页面操作验证仍以主协调真实 E2E 为准。

## 本轮逐属性摘要复核

只读检查 `schema-draft.ts`、`schema-draft.test.ts`、`SchemaImpactDrawer.tsx`，未重复执行重测试。主协调提供该小包 typecheck、lint 及 15 tests 通过信息，以下结论来自源码和测试断言审阅：

- 已有字段显示名称、类型、必填等只显示真正改变的属性及前后值；规则按两侧 key 并集比较，新增、修改、删除约束均有对应呈现，删除显示“未设置”。
- 规则值 0 不因真假值判断丢失；未知规则 key 仍显示其原信息，不静默省略。
- 新字段显示类型、必填、规则与现有记录默认值；省略、null、false、0、空字符串和文本 `"null"` 明确区分。日期对象保留 precision/value/offset 的完整 JSON 证据，不做日期或时区转换。
- 摘要函数只读取候选并生成文本，不修改 definition、validation 或候选身份；测试显式断言输入保持。
- 抽屉单元格增加 `whitespace-pre-wrap` 和 `overflow-wrap:anywhere`，支持逐行摘要及长正则/默认值折行；这些样式的实际视觉表现仍须截图核验。

本小包未发现未闭合 P0/P1/P2。格式化测试中的合成值用于检验摘要保真，不能据此宣称不合法业务 definition/default 已获后端接受。

## 性能实测引用与实际限制

作者已实际运行 `scripts/measure-schema-commit.py` 并独立重新读取 [性能 JSON](performance/schema-commit.json)，五例通过；每次只使用程序自建临时库，结束清理，不打开用户数据库。

| 样本 | 预检 | 成功 BEGIN IMMEDIATE→COMMIT | 结果 |
|---|---:|---:|---|
| 1000 行普通回填 | 26.594 ms | 466.847 ms | 1000 条回填 |
| 1000 行、写后精确 4194304 字节 | 93.184 ms | 513.437 ms | 边界成功 |
| 1001 行 | 24.218 ms | 不适用 | 409 拒绝，零回填，原内容字节保持 |
| 写后 4194305 字节 | 78.731 ms | 不适用 | 409 拒绝，零回填，原内容字节保持 |
| 10000 行，仅规则变更 | 227.689 ms | 5.900 ms | 零回填 |

并发读取均有实际样本且无失败。默认 SQLite DELETE 模式下，精确 4 MiB 提交期间 37 次读取的 p95 为 7.622 ms，最大为 **385.117 ms**；不能把该次结果描述为提交期间完全不阻塞读取。以上为单次有限样本，不代表所有机器或无限大表。

## 主协调待补：最终视觉与 E2E 汇总

本记录没有将静态源码、单元测试或后端性能结果当作 Gallery 视觉通过，也未代替主协调汇总正在运行的 E2E。

主协调应在最终采集与复核后补充：生产版本/构建标识、最终 run 路径、原图对应与逐图结论、正常/异常/200% 状态、实际保存/冲突/未知恢复/跨范围/离开保护步骤、全量验证日志及剩余限制。历史失败 run 保留，不以覆盖旧失败的方式形成“全部通过”结论。

阶段最终结论：**待主协调补充；本文件不预判 R3 全阶段通过。**

## 运行期发现与修复（最终复验中）

- build2 `run-4VNIHo` 在200%失败：document宽782/视口720，网格子Tabs最小宽度沿字段表传播。Tabs min-w-0、字段单列网格和内部min-w-0修复；build3 `run-PcVwox` 四页200%文档宽708，内部表格滚动，未用全局隐藏横溢。
- 逐图复核不通过项保留：build3状态84（空态）、来源76（本地表，非Excel）；build4 `run-NCVFNg` 真实数据后来源91，状态78（旧多字段弹窗）。build5状态改名称优先、颜色/顺序折叠，已有值和RHF校验保留。组件18测试通过；最终图审待补。
- build4目录回归三次重连保存后UI回旧值，`run-69Ackq/failure.json` 记录真实PATCH200、新说明/修订11且独立GET一致，但UI旧说明clean。根因是table effect依赖本地table，重新吸收旧查询快照。build5同代次拒绝较低修订，保留同修订权威元数据刷新；新确定性缓存回放测试与连续重连保存测试均通过。真实smoke `run-fpOpWY` 14流程通过，UI与GET新说明一致、后续保存修订正确、双工作区和完整重启通过。不存在重复PATCH或数据库丢失。
- `npm test` 默认并行在5000ms超时后造成同文件5项失败，原日志保留；使用同一全量集合 `npm --workspace @autoflow/desktop test -- --maxWorkers=2` 134文件1122项通过，未放宽超时或删除测试。此后状态与缓存反例有新增，最终计数待最终复验。
- 原生文件完整链 `docs/migration/pm2-detail-qa/run-cqRTZI` 7项通过，CUA操作真实面板；应用/服务完整重启、真实Excel检查映射导出/重导入、源哈希不变和10000行分页。build3文件代码与后续build5相同；操作记录见native-file-observation.json。


## 120条批量部分完成：真实运行发现与闭合

- `batch-partial/run-dlaPba`：SQLite已正确提交20条、第一块100条冲突，但GET响应校验500。`REVISION_CONFLICT`携带details，HTTP共享Blocker DTO没有此字段；不是执行未完成。15个真实HTTP定向测试建立500反例并修复专用`RecordStatusBatchBlocker`，保留版本详情，不放宽其他接口。
- build5 `run-HIcfNB`真实UI三页选择120、预检后竞争修改、确认、100冲突/20修改、完整应用与服务重启查回通过，但结果描述错误“已选择0”。build6改用原持久请求数量、已知冲突中文提示；17组件定向测试通过。
- build6 `batch-partial/run-6xknNg`重新执行完整链：前后都显示120；已修改20、冲突100、未执行0。真实GET证明第一块无批量写、第二块只提交一次；重启后所有120条记录修订一致，start POST仅一次。规模资料和竞争修改明确为E2，提交和恢复为真实UI，未伪称120条均手工建立。
- 独立`gallery_g0_quality`先规格后工程复核：专用DTO向后兼容、原键/replay/restart契约、中文已知code、冻结数量、原有command/epoch/停止语义不变；无未闭合P0/P1/P2。作者报告未代替本次实际E2E。


## 最终逐图与工程收尾

build6源800fb01，应用build SHA `084c632df6e40675edd6041d2e6bae7de28a8c9c2fa1efd4af321459ce42e29e`。`runs/run-TIUvZc`12项真实检查、21图含未知保存待核对/重启成功/服务重连脏草稿、实际UI阻断与409、busy、空态和200%。独立图审分数字段89、编辑抽屉90、影响88、状态91、Excel来源91、设置90，全部达到逐画板门槛；根协调另实际查看对应应用图和原008/009/100及关键恢复/设置画面。结果属于定性结构、层级与操作位置审查，不是像素相似率或用户确认。区别与剩余留白/密度见visual-review.json、page-map.json和comparison.html，不用平均分掩盖低分。

最终全量：853后端（2条依赖弃用警告）、134文件1126前端，33脚本和3结构；Ruff、mypy201、typecheck、lint、OpenAPI、build均通过。1126是最终一次完整测试集合结果，不把前后增量加总。历史默认并行超时失败保留，最终相同集合限制2 workers未放宽超时。

独立资料审查发现并修复了手册lost语义/读取注入触发方法、Excel原生面板覆写清理、replacement路径、E12证据类型漏E4、根目录visual-review引用及文件截图元数据遗漏。报告必须分别列原生build3和最终build6注入链，不倒填未采集的原生元数据。最终回归路径与文件实测耗时见machine-report.json。

本记录前文“待补”“最终复验中”是历史执行快照；本节及机器报告最终状态共同替代其当前含义。所有用户手册用例保持未执行，平台和打包限制不改写为通过。PM3没有实施。

最终补充状态独立审查：gallery_r1_query逐张实际查看另15状态图及2批状态图，评分86–91，全部达到85及父结构要求；原评分/理由保留runs/run-TIUvZc/state-review.json。六主图与17状态分开登记，不继承父图分数冒充逐图审查。
