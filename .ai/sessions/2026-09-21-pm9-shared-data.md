# PM9 共享领取和数据能力后续

日期：2026-09-21。状态：confirmed / implementing。来源：用户批准、实际代码与定向测试。

C1 复用现有 lease 唯一索引和输入选择/提交事务，新增 Sheets 公共键、完整拉取身份验证及逐记录来源证据。nullable pm09_shared_sheet_identity 迁移让旧绑定等待重新拉取；终态旧锁不改写。推送证据合并保存，不抹除身份观察。旧活动 local Sheets 锁保守阻断同 Spreadsheet 新领取（旧事实未保存 sheetId，不猜测来源）。

10 项新场景及相关规则、迁移、输入/同步共 158 passed / 2 warnings / 57.88s；mypy 403、ruff 通过。直接断言范围与剩余缺口见 shared-data-follow-through.json。C1 只验证 HTTP/SQLite，释放测试明确模拟已确认终结，不冒称实际 worker。C2 query 写绕过和绑定变化现已 RED，继续修共同入口与生命周期；C3/C4/R1–R5 未完成。

f580 本机真实 public145 内核 26 passed / 279.99s，早前错误 Pro 路径尝试保留为失败配置记录。旧矩阵 35590418456 Windows 全量 3317 passed / 71 skipped / 1 failed：100ms 合成任务自动预算在第二次 pause 前耗尽；需修测试时序并复验，另两平台继续。releaseAccepted=false，不合并发布。

## C2 全入口与本地游标（confirmed）

共同来源键已用于动态 query 写和新建后的占用；新建的本地记录只在 create 事务跳过远端成员存在检查，仍竞争公共键且不触发远端新增行。相同 Task 跨两个本地绑定拥有一个物理 lease、两个本地 RecordRef 游标；pm10_shared_sheet_cursors 无损升级，存在多个游标时拒绝降级。原命令重放、拒绝冲突后无局部记录/操作均有直接断言。

解绑/改绑/归档检查原来源及目标来源的 shared held/reconciling 锁，界面 blocker 只包含当前项目表定位。来源验证采用最新兼容扫描，同时冻结绑定集合；解绑/删除同伴会要求重新拉取，不能消除已知的坏身份后放行。普通空身份拉取仍可读取有效本地行，但完整身份缺失时不能领取。不同身份列允许绑定/读取但暂不准入；普通推送失败不会撤销可靠本地领取。

147 项相关规则、数据能力/来源/生命周期/迁移回归通过（95.58s），mypy 404、ruff 通过；额外降级拒绝及游标保留断言通过。C3 完整恢复/UI、C4 两真实 worker 与 R1→R2→R5→R3→R4 继续。旧 C2 待修表述被本节 superseded。

## C3 恢复和原因展示（confirmed，2026-09-21）

生产 376b8a59：真实 worker 29 项通过；最新共享身份 3 项进一步断言 P 非空状态/Q 空状态与 owner busy=false，通过。人工继续、停止、精确所属进程失联后仅清理完成才可重领；旧人工命令拒绝，最终零活动占用。Google transport 受控，不计实网。UI 22 项及完整前端 5460/406、typecheck/lint/OpenAPI、scripts 101 通过。全后端仍运行，4 个 Android 历史升级用例硬编码 pm08，已复现新 head pm10 不符并修正测试，未改迁移实现。C4 新三平台及全量待收齐。覆盖仅 3 条 planned→partial，合计 225 有断言/26 无，191 partial/60 planned/0 verified。

## R1 表结构查询（confirmed，2026-09-21）

复用 Task scope、catalog 元数据、绑定映射和现有数据节点 RPC；显式非空字段、当前结构和只读状态属性，不创建占用或读证据。节点字段选择与输出变量接通，子流程按父权限和冻结声明交集。91 项相关回归、最新专属 14 项、UI 4 项、真实 worker data-schema 1 项（两 Task 加环境保存/恢复）通过；ruff/mypy404/typecheck/lint/OpenAPI 通过。覆盖只新增 DATA-SCHEMA-01 的具体断言，226有/25无、191partial/60planned/0verified。C候选21f8bb1e矩阵35597323657仍独立运行、不含R1；R1后续新平台验收待定。R2→R5→R3→R4 继续，不增加 M1–M3。

## R2 本地字段删除（confirmed，2026-09-21）

原 DataSchemaService 没有删除路径，现以单个显式 removedFieldIds 扩展完整草稿，抽出同 Session 提交供管理/Task 复用；修正预览末次快照与影响持久化原先不在同事务的问题。Task 自身纯删除声明排除，其他节点/Task、身份、来源映射、自动化输入引用与未决同步继续阻断。字段 ID 删除后不能复用，Task 只有当前本地 cursor 可随自己删除推进，人工新值导致的落后 cursor 不推进。节点配置使用既有 SchemaImpactDrawer 做目标预览确认，运行时 previewFieldDeletion→deleteField 仍需原影响版本。仅本地定义/值删除，不删 Google 列。180 后端定向、18 UI、真实 worker 成功/冲突 2 项、类型/lint/OpenAPI/脚本101/build通过；覆盖227有/24无，192partial/59planned/0verified。C4三平台不包含本片，R5→R3→R4继续。


### 2026-09-21 R5 来源观察（confirmed，局部证据）

普通远端值通过现有 SyncRecordMarkRow.inboundObservation 保存最近每字段观察；与 identity/outbound 证据合并。当前 generation/epoch、字段/映射与记录存在性约束后，只读 HTTP/详情显示来源值、观察时本地值和修订。普通值、状态/关联、内容修订和待发送意图不改；公式保留既有刷新。重复身份不更新观察。无采纳/回滚/云写入口。

59 项后端、18 项组件/客户端检查通过；ruff/mypy(404)、typecheck/lint/OpenAPI/build 通过。DATA-SH-06 移除对应 implementation_missing，仍 partially_verified；251 条、227 有定位断言、24 无定位断言、192 partially_verified/59 planned/0 verified 均不变。早期 PM6 记录对“远端差异可查看”的范围已明确纠正，不否定其既有服务账号实网及系统凭据证据。

C4 35597323657 @21f8bb1e：ARM 已通过；Windows 全量后端 3338 passed/74 skipped、前端 5460 passed/406 files，但真实 worker 13 failed/5 passed/11 deselected，进程失联原因待诊断；Intel 当时仍在运行。以上 C 候选不含 R1/R2/R5；不得算当前候选三平台通过。R3/R4 仍按批准顺序待实施，releaseAccepted=false。

Windows C4 诊断（confirmed）：仅失联错误码不足以定位原因。现有 CI 加显式 pm9WorkerProbe 开关，只运行选定真实 worker 场景；测试诊断仅记录协议类型/事件类型/能力操作名、异常类/稳定码和退出码，不记录请求/结果载荷。默认全量任务不启用诊断；不改变生产行为或安全边界。probe 不作为完整三平台验收。
