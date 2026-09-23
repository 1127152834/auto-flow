# PM9 D1：来源业务格式错误保留与可见诊断

日期：2026-09-22。状态：confirmed（用户于 2026-09-22 单独批准 D1），实施中。来源：data-and-state-rules.md DATA-TABLE-02、DATA-STATE-08、DATA-SH-05；当前 HTTP/SQLite/受控 Sheets 反例。

2026-09-23 实施校正：来源保留、诊断和 UI 已交付；本轮专属真实 worker 验证发现“声明坏字段仍领取”的遗漏，已在共享输入选择及提交重验复用当前字段规则修复。未使用坏字段和未选中坏行仍允许，选中声明字段的类型/必填/规则错误在 Task/lease/浏览器前拒绝。D1 worker 与原三类共享交接本机 4 项通过；新生产候选完整回归及三平台证据见 `docs/project-management/implementation/pm9/input-validation-follow-through.json`，打包完整链/实网不由本机证据替代。

## 现状与范围

以普通 number 字段映射远端文本 `not-a-number`，POST sync/pull 返回 422 INVALID_PROJECT_DATA，记录没有引入。来源身份可靠仍不能人工标记该行。原操作经 _create_record → SqlAlchemyProjectDataRecords._validate 复用严格人工值校验；同类 ExcelImportService.run 在普通单元格校验失败时使整个导入失败（此项已读代码，尚未实测）。当前 DataCellView.error 表示读取失败，RecordFieldsView 会隐藏原值，不能借用它冒充业务校验问题。

本切片只恢复原规格要求的“可靠身份、可读但业务格式不合格”的记录保留和诊断，不允许坏身份发布，不放宽人工新增/修改、自动化必需输入和项目写节点的校验。没有新执行器、数据库迁移、云端行写入或 M1–M3 授权。非有限数字、不可编码字符、非受支持日期结构等不满足 Scalar/wire 安全约束的输入仍拒绝；不通过 str()、空值或数值转换掩盖原值。

## 契约与行为

1. 来源导入先验证安全 Scalar、字段存在性和稳定身份；身份字段继续按身份及业务字段契约严格验证。只有非身份业务字段可保留格式不合格的原 Scalar。缺必需业务值保留缺失而不补空值。普通人工创建/修改保持原来的全量/修改字段校验。
2. DataRecordView 增加 `validationIssues: [{fieldId, code, rule, message}]`（当前目录下全部问题，默认空数组）。返回结构化规则与不包含原值的安全说明；缺失必需值也有 fieldId。`values` 原值仍可读。问题由当前字段定义与记录快照派生，复用 validate_value；不建立第二份错误账本，不推进任何记录/状态/关联修订，不产生出站意图。历史 Task 输入仍保留冻结内容，当前记录诊断不改历史快照。
3. 来源公式值发生不合规变化也保留实际可读 Scalar并给出业务问题；来源 API 自身读取错误仍使用现有读取失败机制。普通既有远端值仍只形成 R5 来源观察，不覆盖本地。
4. 记录详情在原值旁显示“格式不符合字段要求”和具体字段规则；读取失败与格式错误分别表达。人工状态入口继续按活动项目、身份、状态目录、版本、占用检查，不能因业务格式问题自行禁用。记录编辑只校验用户改动字段，修复后诊断自然消失。
5. 执行准备/领取只按自动化必需字段契约校验：未使用的坏格式字段不阻断其他有效输入；实际读取/使用该字段的任务仍必须通过冻结契约校验。不能用管理可读性隐式给工作流读写权。

## 实施切片与文件

按以下顺序在 PM9 工作区实现，每步测试与文档同步；批准前不改变生产行为。

- D1.1 DTO 与共享值诊断：domain/project_data/rules.py 复用现有字段/Scalar 校验，database/project_data_records.py 当前快照派生问题，http/project_data_record_schemas.py 和生成客户端更新。先写空问题、错误类型/必需缺失、当前字段变化、不改版本/队列、身份与 wire 拒绝的单元和 HTTP 检查。所有构造 DataRecordView 的入口用 rg 找全，不只修详情。
- D1.2 来源物化：project_sync/outbound.py、database/project_data_records.py、application/project_data/excel_import.py 复用同一来源值判定。真实临时 XLSX 和受控 Sheets 均用两行一好一坏验证保留；坏身份仍整次安全拒绝，旧发布状态不变；原操作恢复不重复生成记录。
- D1.3 界面与运行边界：RecordFieldsView 先组件测试再详情联调；验证原值/问题并列、改值清除问题、状态操作可用；实际 worker 验证未使用坏字段仍可执行、使用坏字段拒绝且无半 Task/lease、原成功写不丢失。不得扩大 Studio 准入。
- D1.4 候选验收：相关 source/Excel/schema/status/capability/HTTP 回归、生成检查、Ruff/mypy、前端类型/lint/组件；稳定后完整后端/前端与三平台 Actions。生产源码若变化，当前 0d7524d9 矩阵只能保留历史证据。Google 实网/三平台实机仍按授权资源单独验收。

## 验收证据与退出条件

每项映射必须指向具体断言和运行：原 Scalar/缺失值保留、结构化问题、稳定身份、独立状态和内容修订、原意图唯一、无额外云写、输入契约/占用拒绝、坏身份和非法 Scalar 拒绝。Sheets 受控传输不代替 Google 实网。DATA-TABLE-02/STATE-08/SH-05 只补已证明子条件；其余 UI/生产/外部缺口继续保留，releaseAccepted=false。
