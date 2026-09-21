# PM9 共享领取和剩余数据能力实施计划

日期：2026-09-21。状态：confirmed / implementing。授权：`.ai/decisions/2026-09-21-pm9-shared-claims-data-approved.md`。起点 e71785da，生产 f580b1c6。

规格：`../specs/2026-09-21-pm9-shared-sheets-claims.md`、`../specs/2026-09-21-pm9-remaining-data-capabilities.md`。按 C1–C4→R1→R2→R5→R3→R4；逐片 RED→GREEN、测试/代码/文档/.ai 提交，不批量提升 verified。

### Task 1: C1 公共身份和原子初始领取

文件：domain/project_runs/input_selection.py；database/project_claims.py、project_sync.py、project_sync_models.py；application/project_sync/outbound.py；tests/integration/test_project_sheets_claims.py。
接口：共同来源键解析返回公共键与绑定/身份验证事实；完整拉取证明唯一且不缺失后方可领取，公共键不含本地项目身份。
1. 将失败探针转正式回归，加入 P/Q 一胜一忙、释放后按各自状态再领、提交前绑定变化。Expected: 旧 local 键断言失败。
2. 复用 lease 唯一索引及短事务、绑定持久事实，冻结并重验来源身份。Expected: 通过，无半 Task。
3. 输入选择/数据启动/Sheets 定向 pytest、ruff/mypy。Expected: 全通过；提交及记录局部证据。

### Task 2: C2 全部占用入口与生命周期

文件：database/project_capabilities.py、project_claims.py、project_sync_impacts.py 及现有生命周期检查，cursor 模型/Alembic 迁移和 integration tests。
接口：复用 Task 1 resolver；同物理 lease 的各本地 RecordRef 保持独立 cursor 和权限。
1. query/create、跨绑定同 Task、不同身份列、改绑/解绑/归档共享占用测试。Expected: 未接入路径失败。
2. 统一占用及影响检查；未知身份阻断，普通推送失败不否定可靠身份。Expected: 测试通过，无权限扩张。
3. 定向 pytest、迁移测试、ruff/mypy。Expected: 全通过；提交。

### Task 3: C3 旧版本、恢复和原因展示

文件：共同 resolver/迁移、已有占用原因 DTO/UI 及对应 tests。
接口：旧 local Sheets held/reconciling 阻断新公共键，终态历史不重写；UI 不泄露其他项目内容。
1. 旧格式占用、失联/人工/取消竞争、隐私测试。Expected: 未识别旧键时失败。
2. 复用既有恢复机制与 UI 原因展示。Expected: 旧任务未终结不放行，终结后可领。
3. 定向 pytest/Vitest、ruff/mypy、typecheck/lint/OpenAPI。Expected: 全通过；提交。

### Task 4: C4 真实生产领取证据

文件：现有真实 CloakBrowser integration tests、生产 HTTP 验收脚本和 pm9 报告。
接口：两项目同物理行真实 worker 竞争，唯一公共锁、完整 Task、源修改次数，结束再领；Google transport 受控，实网单列。
1. 实际运行并断言，发现缺陷先 RED 再修根因。Expected: 场景通过。
2. 必要全量回归，稳定 C 候选一次三平台验证。Expected: 全通过，不据此推定物理安装通过。
3. 提交、推送及更新草稿 PR，releaseAccepted=false。

### Task 5: R1 查询表结构

文件：现有 project_data 请求/domain/service/repository/worker/prepare、节点配置及 tests。
接口：queryTableSchema 显式非空 fieldIds、冻结 grant 交集、只读当前结构；精确字段见规格。
1. 权限/字段/代次拒绝 RED；最小实现 GREEN，接配置和输出变量。
2. 真实 worker 查询后合法写入；pytest/Vitest、ruff/mypy、typecheck/lint/OpenAPI。Expected: 全通过，查询不加 lease 或推进修订；提交。

### Task 6: R2 删除字段

文件：既有 DataSchemaService/impact、project_data 能力、worker/config UI 及 tests。
接口：明确目标、table/impact revision、原 operation/digest 恢复；仅本地删除。
1. 身份/映射/其他节点和 Task/未决同步依赖、过期预览及重放 RED；复用完整草稿检查实现 GREEN。
2. 预览确认 UI、真实 worker 成功/冲突及全栈定向检查。Expected: 全通过，重放无第二次删除；提交。

### Task 7: R5 来源观察

文件：project_sync outbound.py、SyncRecordMarkRow 读写、HTTP DTO/客户端与来源详情 UI。
接口：inboundObservation 与 outbound evidence 合并保存，字段最近观察，不改本地值/状态/出站意图。
1. 普通变化、公式、push 并存、无差异、旧代次 RED；持久观察和只读 HTTP GREEN。
2. 更新 OpenAPI、详情组件/Vitest、pytest 和工程检查。Expected: 页面只读不云写；提交。

### Task 8: R3 系统 UUID 初始化

文件：现有 Sheets binding service/transport、SyncOperationRow 原命令、绑定向导及 tests。
接口：发送前持久固定 UUID/目标/归属标记/行证据，未知结果不得重新生成 UUID/列。
1. 发送前、丢响应、部分写、移动/改名/同内容歧义 RED；复用账本/发送协调实现 GREEN。
2. 同一原操作恢复 UI 与离线验收，缺授权实网保留外部待验收。
3. 全栈定向检查。Expected: 通过后才开放原 501；提交。

### Task 9: R4 受控远端增列

文件：既有 Sheets 字段/来源管理、SyncOperationRow column 操作与值发送依赖。
接口：显式请求、归属标记、原目标/epoch/field/revision；未确认列不推值、不接管同名列。
1. 丢响应、失败保留本地值、绑定变化/取消、禁止提前推值 RED；最小持久实现 GREEN。
2. 字段配置明确选项、兼容旧 Task Patch、全栈定向检查；实网单列。
3. 最终稳定候选全量、三平台、一次整批独立审查，提交和更新 PR。Expected: 未完整退出仍 releaseAccepted=false。

## Review Focus

公共键无本地身份；不同绑定不扩大权限；空/重复/变动身份失败关闭；所有领取/生命周期/旧键升级；cursor 与物理 lease 区别；未知写原命令不重发；观察不污染业务值；UUID/增列不接管外部同名数据。M1–M3、跨进程人工恢复及全部 Studio 准入均不在范围。

### R3/R4 implementation contract refinement (2026-09-21, confirmed scope)

- Reuse Google `spreadsheets.batchUpdate` to insert the explicit new column, write its header/initial UUID cells and attach `DOCUMENT` developer metadata in one atomic request. Metadata contains only the frozen operation ownership marker, no credential or local business value. Ref: https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/batchUpdate and https://developers.google.com/workspace/sheets/api/guides/metadata (read 2026-09-21).
- First persist the original public request digest separately from the generated frozen plan on the existing SyncOperationRow. Later lookups recover that plan; they never regenerate UUIDs or insert another column after an uncertain send. Verify metadata is unique and still names the original sheet/column, then compare the exact UUID set and original row evidence. Duplicate indistinguishable rows, foreign same-name columns, renamed/moved ownership, partial writes or changed target retain an actionable unresolved operation.
- R3 must also connect system RecordKey UUIDs to inbound ingestion and shared source claim normalization. Do not only remove `_identity` / `_identity_column` 501 checks: the existing parser and remote-key locator currently assume column keys. Explicitly test UUID versus text views of the same physical identity so an alias cannot obtain a second lease.
- There is no existing cross-request Spreadsheet send lock in the inspected PM9 source. Reuse the existing sync ledger's short transaction/CAS to serialize structural sends against value sends, and block binding/lifecycle changes while an uncertain structural command remains. This is required by the approved frozen-send contract, not an additional executor.
- Keep system initialization separate from ordinary binding; a failed or unknown initialization cannot publish a half-initialized local dataset. R4 extends the current binding mapping compatibly after verified column creation; it must preserve generation, existing field identities, Task patches and local values.
