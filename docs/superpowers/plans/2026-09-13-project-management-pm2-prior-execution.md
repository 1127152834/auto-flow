# PM2 本地数据、Excel 与状态实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. 使用 test-driven-development、requesting-code-review、verification-before-completion。

**Goal:** 交付真实可操作的数据表五页签、本地记录/字段/状态、受控 Excel 导入替换与 XLSX 导出。
**Architecture:** 在 PM1 的单 FastAPI/SQLite 项目事务体系内新增 project_data；Excel 仅通过主进程受控选择授权，工作流继续由 Studio 唯一执行器维护。
**Tech Stack:** Python 3.11、SQLAlchemy/Alembic、openpyxl/defusedxml、Electron、React、现有 shadcn/Radix + Tailwind。

## 基线与授权

2026-09-13 confirmed：独立工作区 autoflow-project-management-implementation，分支 codex/project-management-implementation，基线 ef3178a。PM1 历史报告不修改。主目录 efb73de 的 Studio M2 仍有未提交改动，只读参考，不接管画布任务。新目标授权 PM2–PM9 自动持续推进，替代旧的逐阶段等待用户确认要求。
基线复跑日志 /tmp/autoflow-pm2-baseline-backend.log（461 passed，2 warnings）与 /tmp/autoflow-pm2-baseline-frontend.log（439 tests /72 files passed）。这只是 PM1 回归，不是 PM2 验收。

## 实施契约补充（实现细节，不改变已确认业务规则）

1. DataTable 增加 identity 联合：`{mode:'system'}` 或 `{mode:'field',fieldId:string}`。空白表默认 system；字段身份从该字段值推导 typed RecordKey，不允许客户端另传矛盾 recordKey。所有记录写入 values 为 `{fieldId,value}[]`，拒绝重复字段以及 source/readable/error 注入。身份字段不可通过普通 PATCH 改变。
2. 新 Excel 表使用项目级 `POST /table-imports/excel`，请求含 name/description/inspectionId/fingerprint/sheetId/mapping/identity；原子创建表及代次，不先留下空壳。既有表 `POST /tables/{tableId}/imports/excel` 只表示 replaceDataset，必须有 expectedDatasetGeneration、expectedTableRevision、impactRevision。修正 PM0 createTable 与含 tableId 路由的歧义。
3. 映射为 `{columnIndex,target:{kind:'existing',fieldId}|{kind:'new',definition:FieldWrite}}`；identity 为 `{mode:'system'}` 或 `{mode:'column',columnIndex}`。每来源列/目标字段唯一，业务身份必须映射且全量校验。新增表只能 new；替换保留显式映射的 fieldId，不按名称自动猜。
4. 检查响应为 `{operation,inspection}`，同步完成 200；原 key 查询找回结果。ExcelInspection 增加 issues、各 sheet ignoredEmptyRowCount、identityCandidates，公式缺缓存为明确错误，预览不代替提交前全量验证。
5. 文件桥仍只向 renderer 返回 token/displayName/kind/expiresAt。主进程保留选择登记，通过已有 hostToken 认证的 internal HTTP 通道把受控授权传给当前 sidecar；公开接口不可登记路径。授权绑定 workspace/instance/window/project/purpose；登记与消费有固定身份，首次 inspect 消费 token 后 inspection 持有路径与指纹，提交重新验证，不二次消费。工作区切换/服务重启使旧授权过期，已发布结果通过 Operation 查询，不盲重放文件写入。
6. 所有新增 revision 从 1 开始；datasetGeneration 为 UUID。实际内容变化推进 contentRevision；状态实际变化推进 statusRevision，显式清空状态每次推进以撤销旧预期；linkRevision 独立。表/字段/状态目录结构各自修订，不用表修订冒充记录修订。状态相同非 null 的普通设置不推进。
7. 名称 trim 后 1–120 Unicode 码点，描述 0–1000；表/状态名称 casefold 唯一。字段 key trim 后 1–120、禁止控制字符、区分大小写、点号是字面值；字段显示名称 1–120。状态色 #RRGGBB，order 为非负 JSON 安全整数，允许重复并以 statusId 收尾。
8. 标量类型严格且不隐式转换；布尔不是数值。number 有限且不超过 JSON 安全整数表示约束；date 使用显式 DateScalar，value不带时区，独立offset保存来源偏移；保留 date/datetime 精度与原 offset。字符串校验按 Unicode 码点；数字范围仅用于 number，长度/pattern 仅用于 string。pattern 使用受限 Python 风格正则语法（后端权威），长度≤256、重复计数≤10000；采用 regex 引擎并限制每次匹配50ms，超时返回422而不阻塞服务；前端不自行解释不同方言。
9. Impact 预检持久化独立确认记录，10 分钟有效，绑定操作、项目、目标、变化摘要、版本及当前代次；提交短事务内重算，变化/过期 412。不创建业务 Operation、不领取 lease。
10. XLSX 导出允许 active/archived，其余生命周期禁止；仅新文件、整表或当前过滤、显式选列/状态，不写原文件。查询按解析后的 filter/orderBy 规范化；状态排序 (order,statusId)，目录按 updatedAt DESC/tableId ASC，记录默认 typed key 稳定排序。

## 文件责任与执行包

所有路径相对此工作区；下列未存在的文件均为拟新增。每包先失败测试，再实现，再定向验证、独立规格审查与工程审查；主协调只提交明确归属文件。

### 包 A1：身份和标量领域规则（数据智能体）

文件：`apps/backend/src/autoflow/domain/project_data/{__init__,identity,rules}.py`；`apps/backend/tests/unit/test_project_data_rules.py`。
- [ ] 写失败测试：text 001/text 1/integer 1 三个不同键；bool/float/越界/非规范 UUID/路径多次编码拒绝。
- [ ] `uv run --directory apps/backend pytest tests/unit/test_project_data_rules.py -q`，记录缺少实现的失败。
- [ ] 实现 `RecordKey` 冻结 dataclass、`record_key(value)`、`encode_record_key(key)`、`decode_record_key(encoded,key_type)`、`system_record_key()`；不将文本 trim，不丢前导零，严格 base64url UTF-8 一次解码及重新编码比对。
- [ ] 实现 `validate_field(definition)` 返回规范 FieldWrite；`validate_value(definition,value)` 校验并返回未隐式转换的标量。失败为 ProjectError 422，details 包含字段/规则原因。日期保留精度与 offset。
- [ ] 覆盖必填/null、类型不匹配、Unicode、非法规则、不可控 pattern、日期 offset、非有限值；Ruff/mypy 定向通过并审查。

示例验收：
```python
assert record_key('001') != record_key('1')
assert record_key('1') != record_key(1)
assert decode_record_key(encode_record_key(record_key('a/b%中文')), 'text') == record_key('a/b%中文')
```

### 包 B1：Excel 安全解析和导出适配（文件智能体，可与 A1 并行）

文件：`apps/backend/src/autoflow/infrastructure/filesystem/project_excel.py`；`apps/backend/tests/unit/test_project_excel_adapter.py`。依赖 pyproject.toml/uv.lock 仅主协调修改。
- [ ] 写临时 XLSX 测试：文本 001/重复标题/空行/缓存公式缺失/多 sheet/合并单元格/文件变化/ZIP 限额/公式注入导出，先运行观察失败。
- [ ] 迁移旧 commit 324748a 的安全读取思路：64 MiB 压缩、256 MiB 解压、32 MiB sharedStrings、20 万行、500 列、1000 万单元格、120 秒，defusedxml + openpyxl readonly 双读。只接基础设施层可信 Path，不提供 HTTP raw path。
- [ ] 定义 `inspect_workbook(path)` -> 数据类（fingerprint、filename、sheets 含稳定 sheetId、headers、sample、rowCount、ignoredEmptyRowCount、issues）；`read_sheet(path,sheet_id,expected_fingerprint)` -> 行迭代与完整校验；失败 ProjectError。SHA256 指纹检查文件替换/符号链接，不猜多级表头或汇总。
- [ ] 定义 `write_workbook(path,headers,rows)` 新建 XLSX；字符串始终以文本写出含 =/+ 前缀，不让业务数据变公式，日期标量按契约保留。临时同目录文件完成后无覆盖发布，失败清理自己的临时文件。
- [ ] 运行 unit 文件、Ruff/mypy；记录 parser 验证不等于 import/API/IPC 验证。

### 包 A2：持久化与事务（主协调）

文件：`infrastructure/database/project_data_models.py`（相对 backend/src/autoflow）、`migrations/env.py` 导入登记、`migrations/versions/pm02_project_data.py`、`tests/integration/test_project_data_migrations.py`；随后 `infrastructure/database/project_data.py`、`application/project_data/{tables,records}.py`、`domain/project_data/models.py`、`tests/integration/test_project_data_repository.py`。
- [ ] 失败测试：空库和 pm01 升级，保留既有项目/资源；同项目 typed key 唯一、跨代次不混同，字段 key 同表唯一，状态与记录归属约束。
- [ ] 迁移从 pm01_projects 派生（执行前核对 head），真实表：project_data_tables/generations/fields/statuses/records/changes/impacts。JSON 存标量值，身份/版本/引用/查询索引为独立列；保留旧代次与人工变更事实。
- [ ] 仓储短 BEGIN IMMEDIATE 原子持久化命令与 ProjectOperationRow；先幂等摘要再生命周期/CAS，所有请求复验项目归属。完成表/字段/状态/记录 CRUD、查询以及固定目标块状态变更。无新增通用后台框架。
- [ ] 测试同名竞争、幂等快照、CAS、状态独立、显式清空、逻辑删除、只读生命周期、影响时效、批块冲突/取消。

### 包 A3：真实 HTTP 与操作查询（主协调集成）

文件：`adapters/http/project_data.py`、`project_data_schemas.py`、现有 `project_schemas.py`、`bootstrap/app.py`；`tests/contract/test_project_data.py`；唯一生成 `apps/desktop/src/renderer/shared/api/generated.ts`。
- [ ] 从 A2 行为写真实 HTTP 契约测试，覆盖路由所有参数与错误码、资源归属、QuiesceGate、Idempotency-Key、操作查询。
- [ ] Pydantic 采用现有 camelCase、extra forbid；操作枚举只开放真实命令，统一查询结果可展示不同资源快照。GET 分页真实 total，base64 filter/orderBy 严格解析，服务端执行筛选。
- [ ] 接通数据能力后才将 data 改 available；概览真实计数，不开放未来能力。
- [ ] 用仓库 openapi 脚本生成并 check，不手写生成 DTO。

### 包 B2：文件 IPC、inspection 和原子发布（主协调；适配器审查通过后）

文件：`apps/desktop/src/shared/project-files.ts`、`main/project-files/{controller,registry}.ts`、preload/主进程装配及 `tests/project-files.test.ts`；backend `application/project_data/imports.py`、`adapters/http/project_files.py`、`tests/integration/test_project_excel.py`。
- [ ] 失败测试取消 null、伪 renderer path、跨 window/workspace/project、过期/重放 token、错误 hostToken、指纹变化、提交丢响应。
- [ ] 选择/授权/消费严格绑定；inspect 固定 operation，导入临时候选全量验证、一次事务发布表/字段/代次/记录/结果，失败保留原表。用旧算法验证完整列身份，不能仅检查20行预览。
- [ ] 替换影响包括人工变化/状态/关联及未来真实引用提供方；活动阻断以真实事实判断。异步操作先持久接受，后台执行可查询；重启结果未知先查发布证据。
- [ ] 导出只写受控输出、新文件，记录成功事实；失败/取消不得显示成功。测试 001、同值三身份、100k、无缓存公式、零行表、保留旧代次、损坏/取消无半表。

### 包 C1：领域组件先行（前端智能体；真实 DTO 后正式联调）

文件：`apps/desktop/src/renderer/domains/project-data/components/{DataTableFormDialog,FieldEditorDialog,StatusEditorDialog,RecordEditorDialog,RecordFilterEditor,DataRecordsTable,ExcelImportDialog,ExportDialog,MutationImpactDialog}.tsx`；对应 tests。
- [ ] 先行为测试，再用现有 Button/Input/Select/Checkbox/Dialog/FormField 组装组件；不新增重复控件库。
- [ ] 表单脏数据保护、字段逐项 PATCH、版本冲突保留输入、只读、批量固定目标、状态空值可见；日期/数字编辑明确类型、长值不撑宽。
- [ ] 导入分选择/检查/映射/影响/进度/结果，显示全量验证错误与源文件变化；导出选整表/过滤/字段/状态，不要求用户输入任意路径。
- [ ] Vitest 覆盖键盘、Escape、焦点恢复、请求中禁重复、冲突不关闭和取消非成功。

### 包 C2：页面与上下文集成（主协调）

文件：`domains/project-data/{api,types}.ts`、`pages/{DataTableDirectoryPage,DataTableDetailPage}.tsx`；`domains/projects/pages/ProjectsWorkspace.tsx`、hash navigation；`tests/DataTableDetailPage.test.tsx`。
- [ ] 五页签：数据记录/字段与校验/数据状态/来源设置/数据表设置；数据页真实 API，查询带 workspace/instance/project/table/generation/filter，取消读取及迟到响应隔离。
- [ ] 搜索分页列可见、跨页返回恢复；所有修改带原 operation key 丢响应先查；新工作区清理上下文，同工作区恢复保留草稿。
- [ ] 归档只读允许导出；未实现 Sheets 连接入口留待 PM6，不展示假成功。表删除按 PM8 接通，字段删除按 PM4；本阶段不伪造这些动作。

### 包 D：完整阶段核验与证据

- [ ] 运行 pytest、Ruff、mypy、Vitest、npm run openapi:check/typecheck/lint/build/test:scripts/test:structure 和 git diff --check；只执行仓库实际脚本，记录命令退出码。
- [ ] 真实 Electron 隔离工作区：空表→字段→记录→状态→筛选→批状态→Excel导入→修改→重导确认→导出→重启；制造 CAS、源变、无缓存公式和数据代次失效。
- [ ] 记录截图、源文件 hash、导出单元格类型、200%缩放和键盘；Windows/macOS未运行架构明示未执行。
- [ ] 更新 coverage.md/json/execution-ledger、PM2验证报告、PROJECT_STRUCTURE 与 .ai；48/178/18/7编号集合不变，不修改 PM0/PM1 历史通过报告。独立审查闭合后提交并进入 PM3。

## 当前完成记录

- [x] 隔离工作区与 PM1 基线验证。
- [x] 旧项目和冻结契约只读审计；旧 Sheets 留 PM6，旧项目未发现 XLSX 导出实现。
- [ ] PM2 完整业务与真实应用验收（已有核心及组件分包交付，剩余页面、删除/批状态和受控文件流程不能用基础包验证代替）。

## A2b/A2c 当前执行细化（2026-09-13）

A1、B1、A2a表资料和C1表资料组件已分别通过独立规格/工程复核并提交；完整PM2仍在实施中。前端组件13项、全量前端461项、后端602项为本次基础包证据，不是数据页面验收。

- [ ] A2b（pm2_data_rules_impl）：`application/project_data/catalog.py`负责字段/状态命令规范化，`domain/project_data/catalog.py`负责目录端口及验证，`infrastructure/database/project_data_catalog.py`负责列表、字段创建、状态创建/编辑和短事务。共享已验证事务辅助仅在出现第二实际消费者后提取到`project_data_commands.py`，现有表测试不得回退。运行`uv run --directory apps/backend pytest tests/integration/test_project_data_catalog.py tests/integration/test_project_data_repository.py -q`，先保存缺实现失败，再实现并重复验证。字段默认填充必须全量验证、只推进有实际写入的contentRevision，逐行保存变更；状态目录不改记录当前状态。实际Sheets映射前，mapped策略明确412。
- [ ] A2c（主协调）：`infrastructure/database/project_data_impacts.py`负责已存字段修改的影响预检和同事务复验；测试`tests/integration/test_project_data_impacts.py`。预检通过完整FieldRef定位当前代次与字段；保存规范change摘要、table/field修订、当前有效记录的身份/内容修订/受影响值的事实摘要、10分钟过期时间。报告列出不兼容记录（限量明细加总量）及公式/身份字段阻断。`preview_field_update(project_id,ref,definition)`返回ImpactReport，不建Operation；`require_field_update(session,project_id,ref,definition,impact_revision)`由实际字段编辑仓储在BEGIN IMMEDIATE中调用，重新读取并比较，失败412、资源丢失404或代次410，阻断不允许提交。记录在其他字段上有更新也需重新确认，不隐藏事实变化。
- [ ] A2c失败测试包括：预检不建Operation；错误项目/字段/代次；规范请求重现；改值/增行/删行/新tableRevision后旧确认失效；超过10分钟失效；不同变更不共享确认；不可转换值与公式/身份改型列出阻断；无外部动作；caller rollback不留副作用。执行定向pytest、Ruff、mypy后送独立规格和工程审查。
- [ ] 主协调将A2b真实handler接入现有project_data router（GET/POST fields、GET/POST/PATCH statuses），扩展真实Operation结果；A2c进入字段PATCH时同时开放mutation-impact，生成唯一DTO；禁止仅添加无消费者的空接口。随后接记录与批量状态，最后数据五页签和文件IPC/导入页面。

### A2d 记录写入和状态（2026-09-13，下一执行包）

- 责任：pm2_data_rules_impl只写`application/project_data/records.py`、`domain/project_data/records.py`、`infrastructure/database/project_data_records.py`及`tests/integration/test_project_data_records.py`。主协调负责HTTP/生成类型/后续查询筛选与impact集成。
- [ ] 失败测试后实现`DataRecordService.create(project_id,table_id,key,payload)`、`get(project_id,table_id,dataset_generation,encoded_record_key,record_key_type)`、`update(project_id,table_id,encoded_record_key,key,payload)`和`set_status`同update签名；命令返回(snapshot,Operation,replayed)，GET返回DataRecord。字段已由A2b真实目录提供，不依赖前端mock。
- [ ] 请求严格使用冻结API：values为`{fieldId,value}[]`，不能传CellValue权限/来源属性；身份由table.identity决定。无默认业务状态，statusId与environment初始化null，3种修订初始1。新系统UUID只在第一次提交生效；同key找回原快照。
- [ ] 先比幂等完整目标/摘要，再校验项目/当前代次/版本；全字段必填和标量规则、禁止公式/只读字段写、身份字段不可静默改变RecordRef。局部PATCH保留其他字段，无变化不推进contentRevision。状态明确null每次推进statusRevision，同非null不变不推进；前态条件与同表状态scope严格校验。
- [ ] 验证typed001/1/integer1、原key响应恢复、不同target同key冲突、人工CAS、代次410、删除行404、跨表状态、生命周期只读、写入与Operation/完整RecordRef证据的故障原子回滚。执行`uv run --directory apps/backend pytest tests/integration/test_project_data_records.py -q`，随后定向Ruff/mypy，再独立规格/工程审查。
- 依赖边界：本分支尚无可执行项目Task/lease，不能声称已验收占用条件；PM4接真实占用guard。来源只开放可靠local/excel，Sheets写入及外部同步仍在PM6。记录DELETE/影响确认和固定批量状态仍是当前PM2未完成工作，不因本包通过而省略。

### A2e 字段影响确认与实际编辑闭环（2026-09-13）

- 责任：pm2_excel_adapter_impl在已提交catalog基础上扩展`application/project_data/catalog.py`、`domain/project_data/catalog.py`、`infrastructure/database/project_data_catalog.py`；新增`tests/integration/test_project_data_field_changes.py`。root独占HTTP/schema/generated/装配/文档；不碰记录包。
- [ ] `preview_field_update(project_id,ref,definition)`代理到已实现impact预检，返回真实报告；`update_field(project_id,table_id,field_id,key,payload)`使用完整definition、expectedTableRevision/FieldRevision/impactRevision，返回(result,Operation,replayed)。请求缺少或非法属性422；目标UUID/修订安全范围严格验证。
- [ ] 更新摘要含明确action、项目/表/字段目标及全部规范请求（包含impactRevision）。事务先查幂等，再项目写准入、当前字段及CAS；从当前代次构造FieldRef，在同一BEGIN IMMEDIATE调用`require_field_update`后立即改字段、修订与完整嵌套资源证据。确认过期或事实变化412；不可兼容值、公式/只读或身份字段改型拒绝。不修改业务值，不推进record三类修订。更换字面key仍须同代次唯一。无变化不推进table/field修订，仍保存原始操作结果供恢复。
- [ ] 先失败测试：正常预检→修改→query/replay原结果；预检后改值/增行/表修订导致拒绝；两个请求CAS只有一个成功；同key不同field不重放；scope/lifecycle/formula/identity/类型冲突；修改后故障rollback同时撤销字段、表修订、operation/change；metadata修改保持record values/status/link和旧快照。执行`uv run --directory apps/backend pytest tests/integration/test_project_data_field_changes.py tests/integration/test_project_data_impacts.py -q`并定向Ruff/mypy，最后独立规格/工程审查。
- [ ] root随后开放`POST /api/v1/projects/{projectId}/mutation-impact`的已实现updateField动作和`PATCH /tables/{tableId}/fields/{fieldId}`，字段响应为{field,tableRevision}，op.result为{action:'update',field,tableRevision}；生成类型并接领域表单。未来delete动作另行实现，当前不得接受后返回假报告。

## C1b 状态编辑组件执行卡（2026-09-13）

前置：真实 DataStatusCreate/Patch/View 已生成；仅交付组件，正式页面由 C2 接入。负责人 pm2_data_rules_impl，修改边界为 domains/project-data/components/StatusEditorDialog.tsx、status-form-schema.ts、tests/StatusEditorDialog.test.tsx；不改共享控件、API、生成文件或 App。

1. 先写失败行为测试：新建/编辑合法值、trim 后 1–120 Unicode 码点、#RRGGBB 色值、非负安全整数顺序、只读、保存中防重复、失败保留、脏表单关闭确认、同会话刷新不覆盖输入、换会话迟到响应隔离。
2. 复用现有 Modal/FormField/Input/NumberInput/Button/AlertDialog 及 RHF/Zod；暖灰与黏土棕，颜色选择使用统一按钮色板及可填写十六进制文本，不调用系统颜色面板。名称/颜色/顺序均可编辑；编辑仅提交真实变化的字段，不把默认值写成未改字段。
3. 组件 props 使用 workspace/project/status/formSession 合成 sessionKey（不含 instance）；父层持有关闭和命令身份，onSubmit 成功不擅自关闭；请求代次仅在 React 提交阶段更新，兼容 Suspense；busy 禁止关闭和丢弃。暴露 onDirtyChange 给未来导航保护，卸载清理。
4. 先组件 Vitest，再 typecheck/lint，独立规格审查后工程复核。验收只证明组件行为，不登记状态页面已交付。

## A2f 记录查询执行卡（2026-09-13）

来源：冻结 api-contracts.md §2/§3.3；旧提交324748a的 automation_conditions.py、automation_preview.py 及对应测试。旧空白字符串合并null、naive日期补UTC、简单CAST文本排序不适用于新契约，不照搬。负责人 pm2_excel_adapter_impl；主协调负责随后HTTP和生成类型。

文件：拟新增 domain/project_data/query.py、application/project_data/queries.py、infrastructure/database/project_data_queries.py、tests/unit/test_project_data_query.py、tests/integration/test_project_data_queries.py。已有记录写入模块只读复用快照和scope helper；无迁移、无App改动。

1. 失败测试先覆盖封闭表达式、字段/状态引用、类型、null、日期比较、稳定分页与读取快照，然后实现查询用例。filter/orderBy为一次严格canonical base64url UTF8 JSON（无padding），拒绝重复JSON键、NaN/Infinity、surrogate、超限、未知键/操作符；filter最大深度5、每组50项、叶子100，编码输入各≤64KiB，排序≤8项且目标唯一；页码正安全整数，pageSize默认50、上限200。
2. all空组为true、any空组为false。isNull/isNotNull禁止value；其他比较必须非null且类型正确；状态eq/neq必须合法当前表statusId，null操作禁止statusId。string支持eq/neq/contains/startsWith和null；number/date支持eq/neq/range和null；boolean支持eq/neq和null。字段/状态引用失效422。
3. 缺项及显式null仅在筛选isNull中同视为空（返回快照仍区分），空字符串和空白均不为空。普通比较面对null/不兼容值一律false，包括neq。字符串大小写敏感、不trim。日期保持源precision/value/offset；比较只在相同precision和同为无时区/有时区的类别内：date按日期，naive datetime按字面值，aware datetime按真实UTC时间比较（仅比较过程，不重写保存值，不用机器时区）；类别不可比false。
4. 排序按字段类型比较，字符串Unicode码点、number数值、boolean false<true；日期分date/naive datetime/aware datetime明确固定类别，然后在类别内上述排序。null/缺失固定last不随desc倒置。status按order/statusId，系统createdAt/updatedAt为UTC时间。最终稳定typed RecordKey按text/integer/uuid类别固定升序，integer用数值，文本保留前导零；任何显式排序都追加该稳定tie。
5. 服务端在完整有效集合上筛选、排序后分页，不先分页再筛选，不把全记录载入Python列表；可用现有SQLite/SQLAlchemy及只读连接受控函数，不新增依赖。表归属/生命周期/currentGeneration/deleted约束必须有效；total和items来自同一显式只读事务快照。返回 {items,total,page,pageSize,sort}，sort为有效orderBy规范JSON（含最终recordKey asc收尾；无显式排序为该收尾），不依赖对象键输入顺序。items复用保真记录快照；当前_snapshot把缺项合并null的缺陷由独立修复包先纠正，不改写历史Operation。
6. 测试跨页筛选、同序稳定、NULL DESC仍last、日期精度/已知偏移/机器时区不参与、typed001/1/int1、归属404/旧代次410/归档读、并发写时total/items一致，以及大量数据只实例化一页。独立规格→工程审查通过后由主协调添加GET collection真实HTTP、生成类型和契约测试。

## A2d/A2e 实际完成记录（2026-09-13）

- [x] 记录显式命令、同事务字段影响复验与六项真实HTTP新增，三个独立提交cc86607/3630e78/7a2986f。
- [x] 规格→工程→修复复核：记录标量与keyType、字段消费者并发/回滚覆盖、最后类型边界全部闭合。
- [x] 670项后端全量（最终注解前）+33项最终定向、461项前端、Ruff/mypy163、OpenAPI/typecheck/lint/build/scripts18/structure3通过。
- [ ] PM2完整页面与真实应用验收。A2f、C1b进入实施；本记录不提升完整功能编号通过状态。

## A3b 字段/状态前端命令接入执行卡（2026-09-13）

主协调新增 domains/project-data/catalog-api.ts 及相邻 catalog-api.test.ts；不与C1b组件文件交叉。使用真实生成类型，固定project/table/generation上下文，字段/状态目录支持AbortSignal，字段影响纯预检不建Operation。创建/编辑命令使用调用方原key；保存请求复制快照避免等待恢复时被草稿修改。

先失败测试：丢响应查询匹配原Operation，操作kind/action/项目/表/字段/代次/状态身份不匹配必须结果未知且不重发；只有明确OPERATION_NOT_FOUND可用原key原body重发一次，确认422/409/412不盲重发，查询不可用保持未知。resume路径先查询；成功返回原快照。以真实生成字段/状态DTO区分原操作包装结果与直接HTTP响应。定向Vitest及typecheck/lint，独立规格后工程审查。该客户端不直接写缓存或显示Toast，跨实例迟到响应的界面隔离由正式页面协调。

### A2d 保真投影纠正（2026-09-13）

A2f规格审查发现既有记录_snapshot把缺fieldId投影为显式null，与冻结RecordSnapshot事实契约不符。pm2_rules_spec_review转为修复实施者，仅修改共享_snapshot和记录integration/HTTP测试；先RED证明create/新增可选字段/GET的缺项与显式null区别，再修复实际存在键的投影，PATCH明确null仍输出，历史Operation保持原快照不迁移。独立复审由其他智能体承担。旧通过报告保留但不能视为该未覆盖边界的通过证明。

## A2f/C1b/A3b 实际完成记录（2026-09-13）

- [x] A2f：5137c1b核心、068d9e3 HTTP；类型边界、任意小数秒、默认排序负载、分页sort、同快照和池清理竞态均经独立复核闭合。
- [x] C1b：5a90c55状态组件；12项覆盖invalid草稿/空PATCH/dirty清理/readonly/码点/数值边界。
- [x] A3b：beb6a3b字段/状态客户端原命令恢复；17项新测试通过。
- [x] 最终自动回归：后端698、前端490；Ruff/mypy166、OpenAPI、typecheck/lint/build、scripts18/structure3通过。
- [ ] PM2完整页面/文件IPC/实际应用仍待交付，下一步继续C1与B2、删除影响和固定目标批状态。B2只读接入依据见`.ai/knowledge/2026-09-13-project-files-baseline.md`。

## C1c/C1d/A3c 本轮执行卡（2026-09-13）

基线8556f81，上一目标轮已提交实际代码并验证，属于progress；本轮继续实现，无外部阻塞。共享组件先行，正式页面随后接入。

### C1c 类型值编辑（pm2_data_rules_impl）

新文件限定 `domains/project-data/scalar-draft.ts`、`scalar-draft.test.ts`、`components/ScalarValueEditor.tsx`及相邻测试。导出 `ScalarDraft={presence:'missing'|'null'|'value';text:string;boolean:boolean;precision:'date'|'datetime';offset:string}`、`scalarDraft(value)`、`parseScalarDraft(type,draft)`，值类型从生成DataCellWrite.value派生；缺项返回undefined，明确清空返回null。所有原始输入包括非法中间态都通过onChange回传draft，不能隐去dirty。

ScalarValueEditor props固定为id/label/type/draft/onChange、disabled/readOnly/allowMissing可选。复用Input/Textarea/Select等统一控件，清晰区分不填写/清空/填写值；不使用系统select/date面板。字符串保留空白与空串；数字空输入/NaN/Infinity/不安全整数拒绝；布尔独立；日期保precision/value/offset，date不带offset，datetime强制完整秒、允许任意小数秒；无时区不得转电脑时区。仅做格式/类型校验，字段正则权威仍在服务端。先失败测试四类型、三种presence、闰日、时区、任意精度、只读、原始非法draft回传，再实现、定向验证、独立复核。

### C1d 字段编辑（pm2_excel_adapter_impl）

新文件限定 `field-form-schema.ts`、`components/FieldEditorDialog.tsx`及相邻测试。复用C1c稳定接口、现有Modal/Select/Checkbox/Input/RHF。新建/编辑名称、key、类型、必填；string的minLength/maxLength/pattern，number的minimum/maximum，其余无额外规则；不在前端解释Python正则。创建可显式填写existingRecordDefault，sourceColumnPolicy固定真实localOnly；不展示未实现的mapped成功按钮。编辑先调用onPreview(definition)，展示真实影响/blockers，只有无阻断的确认可调用onSubmit({definition,impactRevision})；草稿变化废弃旧确认，busy期间禁关闭。原字段formula/readonly/identity约束给出原因，禁止不允许的类型/规则编辑，服务端仍权威。

组件用workspace/project/table/field/formSession的sessionKey（不含instance），脏输入在同会话后台刷新时保持，换会话/关闭/卸载使迟到preview/save失效。onSubmit成功不自行关闭；onDirtyChange在关闭/卸载清理；无变化编辑不发请求。先RED测创建默认值、规则切换、预检阻断/过期、dirty/异步/只读，再实现和独立审查。组件阶段不伪造正式页面。

### A3c 记录客户端（主协调）

新增 `records-api.ts`及测试，直接使用真实生成DataRecordCreate/Patch/StatusWrite/Page/View。完整project/table/generation作用域；记录键按UTF8规范base64url编码且区分type，查询filter/orderBy只编码一次；读请求可取消。create/update/status原key与不可变body，恢复校验kind、完整RecordRef及操作project/key/status；只有明确OPERATION_NOT_FOUND才原身份重发一次。客户端不直接修改缓存/Toast，页面稍后承担实例和会话隔离。定向Vitest、typecheck/lint并独立审查，后续正式页面调用真实API。

A3c复用补充：将已验证的目录命令恢复机制收敛到`data-command.ts`，供catalog和records两个真实消费者使用；DataCommandUncertain从原api.ts保持兼容再导出。表资料API行为保持现状。新增helper不是第二操作框架，只负责固定请求快照、原key查询、匹配结果或一次确认后重发；原catalog17项回归必须通过。

## C1e 记录编辑执行卡（2026-09-13）

前置为C1c标量编辑、真实DataRecordView/Create/Patch与A3c客户端；不开放未实现删除。主协调负责`record-draft.ts`及相邻测试，独立智能体负责`components/RecordEditorDialog.tsx`及相邻测试；父页面随后C2装配。

1. draft以fieldId定位，复用scalarDraft/parseScalarDraft，保留missing/null/空串/空白/日期原精度。`createRecordDraft(fields,record?)`和`recordValues(fields,drafts,record?,identityFieldId?)`返回真实DataCellWrite[]；编辑只提交真实改变值，原missing选择missing不写入。字段公式/只读、不可读单元格与编辑态身份字段禁止写，创建身份值由正常业务字段输入。
2. 先RED测试创建必填缺项/null/空串、码点长度和数字范围、只发改变的字段、显式null、身份/公式/不可读字段、日期保真和非法数值。通过`RecordDraftError.fieldId`定位字段错误，不在前端重实现Python正则，服务端仍执行权威格式规则。记录草稿不包含业务状态、关联、修订或source/readable属性，父级绑定冻结RecordRef与contentRevision。
3. 组件props为open/mode/sessionKey/fields/initialRecord?/identityFieldId?/saving/readonly/error/onOpenChange/onSubmit(values)/onDirtyChange。同workspace/project/table/generation/record/session保持脏草稿，后台刷新只更新无改动表单；提交冻结本次values和身份，由父级命令管理原key及实例隔离。关闭/换会话/卸载撤销迟到界面结果；本地验证错误聚焦对应输入，失败保留输入。保存中禁止重复及关闭，成功不自动关闭；编辑无变化禁提交。
4. 记录信息区展示真实typed身份和不可编辑原因；大尺寸Modal内单主滚动区，四种类型使用ScalarValueEditor，长文本不撑宽；不会给无字段表造虚假业务列，空结构仍可创建系统身份记录。
5. 组件失败测试→实现→Vitest/typecheck/lint→独立规格→工程→修复复核→提交。仅组件完成不登记正式数据页已验收。

## C1f 记录表格执行卡（2026-09-13）

主协调限定新增`components/DataRecordsTable.tsx`及相邻测试。真实DataRecordPage/FieldView/StatusView作为受控props；分页回调只请求父层服务端页，不做本地过滤分页。复用Table/Pagination/Button/Badge/Skeleton，容器水平滚动，长值单元格截断但保留可访问文本，详情通过onOpen(record)查看。visibleFieldIds控制业务列，身份/状态/操作固定；初始全量列由父级选择，不伪造未实现的同步或占用状态。

先RED覆盖text001/text1/integer1显示身份与回调、missing/null/空串/false/日期原精度、不可读不泄漏、状态空值/目录失效、分页、加载/空/无匹配/刷新失败保留旧页、readonly禁止写。onCreate/onStatusChange可选，仅接通真实消费者时显示；onOpen保持真实RecordRef。完成定向Vitest/typecheck/lint及独立规格→工程审查，C2真实页面挂载后再做应用验收。

## A3d 表资料命令恢复收敛（2026-09-13）

C2接入前代码复查发现旧表客户端未冻结body且未核验Operation自身projectId；目录/记录已通过createDataCommand解决相同问题。主协调仅改api.ts/api.test.ts复用该已验证helper，保留外部API签名和table资源/结果guard。先RED：异步失败期间调用方改name后原key重发仍应原值、Operation本身project不符时拒绝恢复；补update目标不匹配测试。通过后定向全API测试、类型/lint并由独立智能体规格→工程审查；无新端点/DTO。

## C1c–C1f/A3c–A3d 实际完成记录（2026-09-13）

- [x] 七项实际代码提交：bc3aa24、8c25641、113f0c7、d37cb1c、ad8a5d7、dc9ddf2、737ce3e；每包独立规格→工程→修复复核完成。
- [x] 最终564前端测试/86文件；TypeScript、ESLint、build通过，OpenAPI check、scripts18/structure3通过。后端无本轮源码变化，未重复后端全量，不伪报新结果。
- [x] 原命令快照、NaN保真、脏草稿原始数据基线、重复/迟到命令、错误焦点/ARIA及列宽计算问题闭合。
- [ ] 正式数据页面、完整PM2 Electron验收仍未交付；继续筛选组件/C2与删除/固定批状态/B2。
- [x] 下一删除包只读盘点已纠正历史FK问题：状态采用软删除保留旧引用，不暗清tombstone或旧代次；具体迁移/guard/块日志进入下一详细执行卡。

## A2g/C1g/C2 下一执行卡（2026-09-13）

起点f46f869，工作区干净；上一目标轮为progress（七项代码提交与564测试证据），无本地外部阻塞。先补迁移与真实页面，不改Studio或主目录。

### A2g1 状态历史存储（主协调）

文件：ORM project_data_models.py、新迁移`infrastructure/database/migrations/versions/pm02_status_tombstones.py`（revision同名，parent=pm02_project_data）、`tests/integration/test_project_data_status_migration.py`，旧migration测试仅更新当前head和显式INSERT列。新增deleted默认false；删除原全表name_key唯一，改活动行部分唯一索引。使用已有Alembic短事务及batch重建保留FK，禁止改历史迁移。downgrade发现墓碑时明确拒绝，不能复活已删除状态。

先RED：已有pm02数据库含当前/旧generation/删除记录的状态引用，升级保持记录和FK；活动同名拒绝，墓碑同名新UUID允许；注入重建失败全回滚且能再升级；空库升级；无墓碑可降级，有墓碑不允许丢删除事实。uv run pytest两个migration文件→实现→Ruff/mypy→独立审查。

### A2g2 删除命令和真实状态准入（pm2_data_rules_impl）

仅backend：新增application/project_data/deletions.py、domain/project_data/deletions.py、infrastructure/database/project_data_deletions.py及tests/integration/test_project_data_deletions.py；修改现catalog/records/queries仓储的所有DataStatusRow活动查询及其定向回归。迁移/ORM由root独占；HTTP/生成类型也root。

导出DataDeletionService(repository)的preview_status(project_id,table_id,status_id)、preview_record(project_id,table_id,dataset_generation,encoded_record_key,record_key_type)、delete_status(project_id,table_id,status_id,key,payload)、delete_record(project_id,table_id,encoded_record_key,key,payload)。command返回(result,Operation,replayed)，preview返回冻结ImpactReport形状；依现有commands helper，不新建任务执行框架。repository持有sessionFactory。

DELETE status payload严格expectedStatusRevision/expectedTableRevision/impactRevision；DELETE record严格datasetGeneration/recordKeyType/expectedContentRevision/expectedStatusRevision/expectedLinkRevision/impactRevision。完整target/action参与规范摘要，原Operation查询先于CAS和deleted判断。所有当前local/excel写入在一个BEGIN IMMEDIATE内复验scope/lifecycle/currentGeneration、版本、10分钟impact、真实引用后提交tombstone+Operation+DataChange。其他source或尚不可解释的关联/slot影响明确阻断，不伪报外部影响已检查。

status impact blocker只计当前generation的未删除记录及当前实际存在的槽/结构依赖，不把旧行当永久阻断。status删除标deleted并推进statusRevision/tableRevision，结果{action:'delete',statusId,deleted:true,tableRevision}；旧行/旧Operation保持原值。record标deleted，仅updatedAt变化，不隐式推进三revision或清状态/关联；结果{target:{type:'record',recordRef},deleted:true}，DataChange保留完整before/after快照。记录槽中已存在完整RecordRef引用必须查全当前有效表，真实关联环境未支持删除清理则阻断。

预检不得建Operation。报告绑定action/完整target/currentGeneration、项目生命周期、tableRevision、目标修订与当前引用事实；提交重建digest，变更/过期412。current refs动态变化、两个删除竞争、其他项目/旧generation、同key响应恢复、表中途write故障rollback、墓碑名称复用及状态list/update/setStatus/filter均不再接受墓碑须测试。后续Task/Sheets/automation模型接入时同步扩展真实guard，当前不能标记这些跨模块能力通过。执行定向pytest、Ruff/mypy后独立规格→工程审查。

### C1g 记录筛选和排序（pm2_excel_adapter_impl）

只新增renderer/domains/project-data/record-query.ts、record-query.test.ts、components/RecordFilterEditor.tsx及相邻测试。对照后端domain/project_data/query.py准确使用all/any/not/compare/status及orderBy字段/systemField结构；标量类型从生成DataCellWrite继承，不更改生成文件。

组件是受控草稿，支持组（全部/任一）、反向条件、添加/删除条件和组；最多depth5、每组50/总叶100，排序≤8且目标唯一，业务字段与状态允许操作由类型决定。空all明确全部记录，空any不允许UI无意制造无匹配而不提示；null操作不传value/statusId，普通比较不得传null。日期复用ScalarValueEditor不转本机时区，不在JS做业务过滤；应用只把合法filter/orderBy交父层，修改条件不自动发请求。暴露onDirtyChange/disabled，输入invalid草稿仍保护，不把错误值转null，长字段名/选项用真实Select自有面板。

先RED真实组件交互及纯模型序列化：嵌套and/or/not，字符串/number/bool/date/null/status操作，换字段/运算符清不适用值，失效引用保留可修复提示，排序去重和上限，取消恢复父值，apply校验不发错误payload。之后实现、Vitest/typecheck/lint、独立两阶段审查。父级API负责已有base64url传输，组件不得双编码。

### C2a 真实数据入口与目录（主协调）

新增domains/project-data/pages/DataTableDirectoryPage.tsx及test；接入真实createProjectDataApi和已审DataTableDirectory/FormDialog/Select/Input/Pagination。目录状态包含q/sourceKind/sort/page，workspace/instance/project/query构成查询键；AbortSignal取消读取。编辑冻结原tableRevision；结果不明用原key恢复，禁止将新草稿混入旧命令。迟到响应通过commit期scope/ticket防止关闭新表单或Toast串上下文。同工作区重连保留草稿，新工作区清理。表单补onDirtyChange和请求状态回调/恢复动作的最小真实需求；全局离开统一父级guard。

App route扩展为#/projects/{projectId}/data/{tableId}/{records|fields|statuses|source|settings}，只在目标页面可用时允许打开。目录和表内页面按真实API逐步挂载，不给未实现模块加假按钮/假0。组件测试使用合成API响应，正式页面直接请求后端。完成导航/关闭/恢复联调后，再将本地数据能力标为available并做真实Electron；本执行包单独不宣告完整PM2。

### A2g/C1g/C2b 实际完成（2026-09-13）

- [x] 历史状态墓碑迁移、删除预检/命令/HTTP、目录表单、筛选组件与五页签读取均完成独立规格/工程审查。
- [x] 719后端、606前端全量；类型/lint/build、OpenAPI、scripts18/structure3通过。
- [x] macOS arm64真实目录创建/编辑/冲突/重连/重启及PM1既有模块回归；报告pm2-directory-deletions-verification.json。
- [ ] C2c九项写入UI、A2h耐久批状态、B2文件/Excel发布继续；不将当前读页等同PM2完成。
