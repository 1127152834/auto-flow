# R2 静态规格与工程审查

日期：2026-09-14（Asia/Shanghai）。状态：**静态审查闭合；视觉 pending；完整 E2E 未通过；R2 阶段未验收**。

代码基线：`8ccf9690ad78e1d031754bf7bab6540e21a759d5`。审查对象为 `autoflow-project-management-implementation` 工作区中的 R2 未提交改动，不是该 HEAD 已包含的成果。审查置信度：高。

## 范围与结论

`gallery_g0_quality` 完成多轮只读规格审查，`continuous_r1_spec` 完成独立工程复核；截至本记录，双方静态结论均为**无剩余 P0/P1/P2 阻断**。工程复核结论由主协调转交，本记录不把它写成本审查者独立重跑的测试结果。

范围包括 RecordEditorForm、ScalarValueEditor、record-draft、CalendarDateInput、RecordFieldsView、RecordDetailPage、RecordStatusDialog 的 inline 模式、DataDeletionDialog、RecordUnsavedDialog，以及 DataTableDetailPage、项目页头和返回导航的 R2 装配。排除 record-grid-entry、R3 字段聚合及其他并行任务。

唯一视觉规格来源为主项目 Gallery 的 latest 原图：003 详情、004 新增、005 编辑校验、006 未保存确认、007 删除确认。依据[Gallery fidelity 规格](../../../../superpowers/specs/2026-09-13-project-management-gallery-fidelity.md)及已批准业务规则核对源码；左侧全局导航改为顶部、真实来源能力与动态字段差异按既定授权处理。没有使用 B0 画面作为基线，也没有按字段名称硬编码“摘要”或示例记录编号。

## 已关闭的问题及源码证据

以下链接均指当前工作区文件；对应测试是修复证据入口，不代表每条均由本文作者独立运行。

| 问题 | 最终修复与静态核对 | 源码／测试 |
|---|---|---|
| Textarea 被统一 44px 高度压缩；missing/null 时无多行切换入口 | 固定高度选择器限定 input/button；Textarea 保留三行及最小高度。多行选择位于可展开辅助区，missing/null 可进入；保留已有换行，禁止有损切回单行 | [ScalarValueEditor.tsx](../../../../../apps/desktop/src/renderer/domains/project-data/components/ScalarValueEditor.tsx)、[测试](../../../../../apps/desktop/src/renderer/domains/project-data/components/ScalarValueEditor.test.tsx) |
| 编辑身份显示为纯文本 | 恢复带锁只读输入；250px 标签列与字段分隔保留，系统生成身份不伪造示例键；编辑请求仍排除身份字段 | [RecordEditorForm.tsx](../../../../../apps/desktop/src/renderer/domains/project-data/components/RecordEditorForm.tsx)、[测试](../../../../../apps/desktop/src/renderer/domains/project-data/components/RecordEditorForm.test.tsx) |
| 错误摘要缺失或出现在身份行之后 | 表单首项显示全部字段错误数量，逐字段错误保留，提交聚焦首错；测试检查摘要在身份行之前 | [RecordEditorForm.tsx](../../../../../apps/desktop/src/renderer/domains/project-data/components/RecordEditorForm.tsx)、[测试](../../../../../apps/desktop/src/renderer/domains/project-data/components/RecordEditorForm.test.tsx) |
| helper 覆盖 missing/null/空串状态；只读时无法查看 | “未填写／空值／空字符串”与帮助文字并列；允许只读展开查看，状态及精度控件继续只读，不触发值修改 | [ScalarValueEditor.tsx](../../../../../apps/desktop/src/renderer/domains/project-data/components/ScalarValueEditor.tsx)、[测试](../../../../../apps/desktop/src/renderer/domains/project-data/components/ScalarValueEditor.test.tsx) |
| 未保存弹窗显示内部 fieldId | 使用冻结 recordEditor.fields 中的名称映射，保留真实修改与错误字段集合，不根据刷新后的字段目录替换草稿上下文 | [DataTableDetailPage.tsx](../../../../../apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.tsx)、[装配测试](../../../../../apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.test.tsx) |
| 身份字段排第一时遗漏业务标题 | 选择业务摘要时跳过与记录键同值的字符串，继续寻找后续可读、无错误的业务值；详情、删除和未保存确认复用该展示 | [DataTableDetailPage.tsx](../../../../../apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.tsx)、[装配测试](../../../../../apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.test.tsx) |
| 详情菜单展开后不响应禁用状态 | 删除菜单项与触发器同步响应 readonly/disabled/loading/缺失字段；root 回调另检查 writable、disabled、读取中和 canLeave | [RecordDetailPage.tsx](../../../../../apps/desktop/src/renderer/domains/project-data/pages/RecordDetailPage.tsx)、[测试](../../../../../apps/desktop/src/renderer/domains/project-data/pages/RecordDetailPage.test.tsx) |
| 草稿摘要逐字段重复建立 Map／基线 | 共享分析函数一次构建记录索引并收集写值与错误；摘要一次构建基线。字段顺序、首错、保护字段与语义修改计数保持；补 200 字段用例 | [record-draft.ts](../../../../../apps/desktop/src/renderer/domains/project-data/record-draft.ts)、[测试](../../../../../apps/desktop/src/renderer/domains/project-data/record-draft.test.ts) |
| 日历被锁定后解锁自动重开 | locked 生效时清除 open，解锁不恢复旧浮层；日期仍保留原始文本、本地年月日及成熟键盘交互 | [calendar-date-input.tsx](../../../../../apps/desktop/src/renderer/shared/components/ui/calendar-date-input.tsx)、[测试](../../../../../apps/desktop/src/renderer/shared/components/ui/calendar-date-input.test.tsx) |
| 未保存弹窗 relative 覆盖共享 fixed | 移除 relative，保留共享 AlertDialog 的 fixed 居中定位；继续编辑默认焦点、Escape 取消及显式丢弃动作保持 | [RecordUnsavedDialog.tsx](../../../../../apps/desktop/src/renderer/domains/project-data/components/RecordUnsavedDialog.tsx)、[测试](../../../../../apps/desktop/src/renderer/domains/project-data/components/RecordUnsavedDialog.test.tsx) |

## 保留的业务合同

- 值与草稿：missing、null、空字符串、0、false 分别处理；PATCH omission 不解释为 null。保留日期 datetime 精度、小数及 offset。公式、只读、不可读和编辑身份字段不进入写请求；不因布局变化改写异常单元格。dirty、错误集合和冻结提交快照继续使用真实数据语义。
- 详情：业务字段与项目内状态分区，最近修改位于状态区，移除额外时间卡；完整 typed 身份保留，业务身份行不重复。链接复制与打开继续使用已有受控外链路径。证据：[RecordFieldsView.tsx](../../../../../apps/desktop/src/renderer/domains/project-data/components/RecordFieldsView.tsx)、[测试](../../../../../apps/desktop/src/renderer/domains/project-data/components/RecordFieldsView.test.tsx)。
- 状态与删除：状态选择、清空、取消与恢复沿用既有会话；删除确认要求真实预检，无 blocker，完整 RecordRef、代次及 revisions 匹配。未知结果核对原操作，不产生第二 writer。证据：[RecordStatusDialog.test.tsx](../../../../../apps/desktop/src/renderer/domains/project-data/components/RecordStatusDialog.test.tsx)、[DataDeletionDialog.test.tsx](../../../../../apps/desktop/src/renderer/domains/project-data/components/DataDeletionDialog.test.tsx)、[use-data-table-editing.ts](../../../../../apps/desktop/src/renderer/domains/project-data/use-data-table-editing.ts)。
- 导航与恢复：同一离开 guard／resolver 处理取消及丢弃；保存锁、session、instance/request epoch 和迟到响应隔离保持。新增记录路由回顶不在输入时重复执行，返回列表保留查询、分页、列、滚动和来源行上下文。证据：[DataTableDetailPage.test.tsx](../../../../../apps/desktop/src/renderer/domains/project-data/pages/DataTableDetailPage.test.tsx)、[RecordPages.test.tsx](../../../../../apps/desktop/src/renderer/domains/project-data/pages/RecordPages.test.tsx)。
- 404：仅 `RECORD_NOT_FOUND` 映射为中文缺失记录提示；重试保留，缺失记录不可编辑；其他错误不伪装成 404。对应反例与修复验证见下表。

## 已核对的测试日志

以下是主协调执行、本记录作者读取核对的日志；没有在本次文档任务中重复运行。`/tmp` 是当前机器临时证据路径，不应视为已归档的长期仓库附件。全量结果与其后追加定向结果分别记录，不合并编造新的全量计数。

| 验证 | 结果 | 日志 |
|---|---|---|
| 全量前端 | 127 个测试文件、1025 项通过 | `/tmp/gallery-r2-vitest-final.log` |
| 404 追加定向 | 1 个测试文件、42 项通过 | `/tmp/r2-404-green.log`；此前反例保留 `/tmp/r2-404-red.log` |
| 后端 records/deletions | 38 项通过，2 条依赖弃用警告 | `/tmp/gallery-r2-backend.log`；源码测试位于 `apps/backend/tests/{contract,integration}/test_project_data_{records,deletions}.py` |

类型检查、lint 及组件定向结果由主协调另行维护；本文不把未逐一读取的日志计作独立核验。

## 真实 E2E：未通过，日历 Enter 诊断中

[run-kh6Hdw/result.json](runs/run-kh6Hdw/result.json) 明确为 `result: failed`、`visualReview: pending`，并记录基线、dirty 文件、构建及脚本哈希。该 run 的已完成检查包括：

- 正常新增→详情→编辑→保存→状态设置／清空→返回，以及错误校验和取消离开保留草稿。
- 真实竞争 409 保留输入、取消比较不覆盖、明确采用新版本后单次提交。
- 真实写入后响应丢失，完整应用重启恢复原操作，修订未重复增加。
- 同工作区服务重启／重连保留草稿、两个真实工作区隔离。
- 删除取消保留目标，真实影响确认后仅删除目标，其他记录不变。

这些是该 run 记录的分项结果，不能代替整个 E2E 通过。最终失败为日历操作后的日期断言：实际 `2026-09-13`，预期 `2026-09-14`。主协调正在诊断真实日历 Enter 路径；本记录不推断产品实现与测试驱动哪一方是根因。失败证据保留，不覆盖成成功。响应延迟、文件选择及故障注入按 result.json 的来源标记解释，不能冒充全部纯 UI 操作。

## 视觉审查：pending

003–007 的最终截图逐对比对、GF 结构检查、布局／信息／样式／操作评分均由主协调后续补充。此处不提供分数，不把源码检查或截图文件存在计作视觉通过。200% 响应式衍生证据须独立记录，不伪造原图匹配评分。

用户手测未执行；R2 完整 E2E、最终视觉和阶段退出结论仍待完成。[page-map.json](page-map.json) 当前保持 `implementation-started-not-accepted`。静态双审闭合不构成进入 R3 的阶段验收结论。


## 2026-09-14 视觉复核与整改（最终截图待复核）

独立视觉审查逐对查看 run-JsFQxl 与原始003–007：003=86、004=84、005=84、006=91、007=80。主要结构GF通过不能抵消单页低于85；本轮没有据此宣称R2通过。

- 004：三条先前字段创建Toast污染正常基准；修改QA等待自然退出，并补同状态底部截图。
- 005：显示校验错误后保存仍呈主按钮；RecordEditorForm新增可见错误回调，外层和内部普通保存禁用，修正清错后恢复，原结果恢复按钮不锁。逐字段错误为红色14px并带警告图标。
- 007：真实RECORD_DELETE/record资源影响映射中文“影响范围：1条本地记录”，不解析/伪造入站引用数量；其他影响/阻断保留。收紧对象说明留白，等待Toast退出再拍。
- 富标题Modal内容区原标签会序列化为对象，改为关联标题；独立工程复核发现Content需同步自定义titleId，已补aria-labelledby。最初相关测试13失败完整保留日志；修正后5文件87测试通过，未删除失败断言。

最终构建：build7。最终全量/端到端与视觉复核尚在进行。源文件哈希见source-manifest.json。


## 最终复核（2026-09-14）

实现a08c2fe。run-msXqcI完整E2E通过，50张状态截图、21项检查，截图来源/viewport/zoom/DPR/font/build逐项记录。独立原图终审003/004/005/006/007=86/88/89/91/88，GF适用结构全部通过；004/005顶部与底部共同核验，未用平均分。前轮84/84/80与失败截图保留。无未闭合P0/P1/P2，剩余P3为部分辅助文字、边框与间距细节。

127文件1030项前端、38项后端记录/删除、29脚本、3结构以及类型/lint/build/OpenAPI通过。PM2目录14流程与Excel/批状态7流程在最终build7重跑通过。原生外链在run-TRJwrL经CUA点击http/https，Chrome实际目标与HTTP服务证据已保存。文件选择注入不冒充原生面板（后者R3执行）。

日期失败先是CDP Enter缺少字符事件；修复后在真实页面等待选中日聚焦、方向键移到次日、Enter提交和数值改变均通过，未通过程序setValue或click绕过键盘断言。

R2允许进入R3。用户手测、Windows/其他架构/打包未执行；候选视觉基线未经用户签收。

补充清单闭合：同build7的run-NpRXl4再次完整E2E通过，补充浏览器后退/前进真实导航取消URL与草稿一致、删除进行中禁重复/禁关闭、状态下拉打开截图。主图终审仍引用run-msXqcI，补充图不冒称额外原型评分。
