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
- [ ] PM2 业务实现及验收（尚未执行，不能用以上审计代替）。

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
