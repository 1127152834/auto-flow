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

Windows Job startup race candidate fix (2026-09-21, implementing; native confirmation pending): probe 35603141412 @0e0e73ba reports pre-ready OSError at windows_job.py:115 (joining parent Job), exit 1. Parent and worker both may assign the same process after a negative membership check. Two deterministic race tests fail before the fix; after failed assignment both paths now re-query membership on the exact original process/Job handles. Only confirmed membership is accepted; foreign/unreadable state still closes handles and rejects. Local related regression 70 passed/8 platform skips, final Job subset passed, ruff/mypy passed. No safety checks removed. Actual Windows probe remains required to confirm this explains the native failures.

Windows startup follow-up (2026-09-21): native probe 35603692816 @dba685ec still fails at exact Job join before ready, so membership re-query alone is not the native fix. CPython 3.11 PC/launcher.c:741–771 creates its own kill-on-close/silent-breakaway Job and assigns the interpreter after creation; Modules/getpath.py handles __PYVENV_LAUNCHER__. Native Job nesting depends on assignment order (Microsoft nested-jobs documentation). Candidate fix launches sys._base_executable directly for this interpreter's unfrozen Windows venv commands, setting the CPython launcher marker to retain the exact venv. Custom non-Python commands and frozen packaging keep their command; named Job/birth checks remain mandatory. Native prefix/import check plus real browser probe required before calling this fixed. Sources: https://raw.githubusercontent.com/python/cpython/3.11/PC/launcher.c ; https://raw.githubusercontent.com/python/cpython/3.11/Modules/getpath.py ; https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs .

2026-09-21（confirmed）：Windows 原生探针 35604286479 / 10ce00e8 成功：venv 启动 1 项及真实 worker 9 项通过。完整 Windows 35604833296 随后在 mypy 停止：Windows 条件分支直接访问未在类型存根声明的 sys._base_executable。改为显式模块字典读取（缺属性仍失败关闭），运行 mypy --platform win32 单文件通过；不将探针等同完整打包验收。

### 2026-09-22 R3 与 C4 更新（confirmed，局部验收）

R3 已冻结原操作 UUID、身份列归属及行证据，单次 Sheets batchUpdate 新列/值/metadata。未知响应仅核验；仅证明未发送的原计划允许重试，UUID 不重生成。原操作发布绑定与成功状态同事务；资料修订变化须重新预览影响后明确核验。复用本工作区已验证系统列不云写；同名未知归属拒绝。UUID 拉取/推值接通，文本视图和 UUID 本地键解析同一公共 lease。未决结构发送阻断其他绑定推值、领取和改绑；值发送未知先阻断结构发送。共享 GoogleAccess 使用标准库 RLock 序列化读计划到发送，并以现有 SQLite 账本保留跨请求/重启的未决围栏。没有第二执行器。

90 项后端相关检查、25 项组件/客户端通过，ruff/mypy（406）、typecheck/lint/OpenAPI/build 通过。覆盖账本 251 条中 228 有定位断言、23 未定位，193 partially_verified / 58 planned / 0 verified。DATA-ID-05 只升级 partial；真实 Google 和当前打包完整应用链仍待验收。

C4 Mac @21f8bb1e 的 ARM/Intel 全部通过；Windows @07619b6d 完整流水线 35605861737 通过：3384 后端（77 平台 skip）、5464 前端（407 文件）、21 真实 worker、源码/包链/安装包和万行写入。万行发生 8 次明确 busy 重试，不构造新的性能门槛。两份源码范围分别保留，R3 不包含在这些 CI 中。此前 C4 “Intel pending/Windows failed”当前状态由本节 supersede；失败日志仍保留历史。R4 接续，完整当前候选矩阵与一次整批复审在 R4 后执行。releaseAccepted=false。

2026-09-22 R3 接线修正（confirmed）：通用 sync-operations 仅列内容意图，会过滤有 ProjectOperation 的 systemIdentity；初版 UI 调用它会漏掉恢复项。真实 HTTP RED 复现，新增系统身份专用 GET 分页并复用同一仓库查询；默认内容队列语义不变。23 后端/25 UI 检查、mypy/typecheck/lint/OpenAPI 通过。最终构建/全量跟随 R4 稳定候选；不将 mock 列表测试当作后端可查询证据。

### 2026-09-22 R4 受控增列（confirmed，局部验收）

显式选择普通本地字段、列名并确认远端写入后，原操作冻结目标/epoch/field/revision/owner，在网格末尾单次追加列、表头和归属 metadata。未知响应只核验原列；同名外部列、移动/改名/缺 metadata/非空列不猜测接管。仅确认未发送可原计划重试或取消，取消保留本地字段和值。确认事务兼容扩展 mapping、保持 generation/epoch/记录版本，并将已有新字段值放入现有队列，值发送依赖原列成功。既有冻结 Task 可以继续旧字段修改，不能因此扩大新字段权限；后续同步重验已创建列归属。

HTTP/SQLite/受控 transport 相关回归 113 passed（138.65 秒），组件/客户端 38 passed（5 文件），ruff/mypy（407）、typecheck/lint/OpenAPI/build 通过。另发现通用放弃接口跨项目及结构命令越界，两项 HTTP 反例复现，修复范围限定共享入口的项目归属与内容意图类型。覆盖账本仅 DATA-SCHEMA-07 新增具体断言并改 partial：251 条中 229 有定位断言、22 未定位，194 partially_verified / 57 planned / 0 verified。现有历史统计按日期保留。

R1/R2/R5/R3/R4 与 C1–C4 已有实现和分范围证据；最终整批独立审查、当前完整回归和三平台矩阵接续。真实 Google、当前打包完整 Sheets 链、OAuth、物理安装和签名仍未验收；S4 已存在文件安全覆盖/追加/读取与未批准 M1–M3 仍为实际缺口。releaseAccepted=false。

### 2026-09-22 整批审查修复与映射复核（confirmed，回归进行中）

一次独立审查发现 3 项 Important：UUID 公共 lease 查询未归一类型、未知值核验缺来源归属检查、推送明确发现坏身份后未失效旧领取证据。均已用直接 HTTP/SQLite 反例复现，按共享入口修复；推送与核验复用完整身份观察，可靠身份的普通推值失败不受牵连。新组合断言明确失败意图和本地新值保留、后续拉取正常、真实 Task 领取冻结本地值并继续公共排他。新增 R4 测试也直接证明加列后旧 Patch 推回原 B 列与旧 Task 权限兼容。

DATA-CLAIM-09、DATA-SCHEMA-08 仅新增上述范围映射，未证明的来源读取失败/界面提示、删除本地字段不删远端和生产端到端条件仍保留。当前 251 条中 231 有定位断言、20 未定位，196 partially_verified / 55 planned / 0 verified。完整前端 5469 passed / 409 文件 / 198.85 秒，前端源码之后未改；最终后端和三平台仍在验证。详见 shared-data-final-review.json。releaseAccepted=false。

2026-09-22（confirmed）：最终本机后端 3440 passed/67 skipped（772.39 秒），完整前端 5469/409，全部工程门禁通过。d75297fb 当前源码新构建 Mac ARM DMG，SHA256 eeb378b40c41ea8dbaeef87c914176bd552cb5b95ff5035e276b1ba3665afc45；校验、只读挂载、隔离复制、认证包内侧车启动和父进程退出清理通过，临时副本已删除。无当前文件面板/凭据/Google/签名/完整卸载推断。三平台 35629585683 仍进行中，不能提前记通过。

### 2026-09-22 原生 CI 期间继续补证（confirmed）

新增两项直接业务场景，生产源码未变：DATA-LIFE-09 在真实 HTTP 归档收尾后保留未发送本地值及原意图，新推送 409、远端无写；DATA-SCHEMA-08 先由未决意图阻断本地字段删除，明确放弃后删除本地字段而同名远端列/值保持，状态与关联修订不变。两个相关完整文件 21 passed（17.71 秒），全目录 Ruff 通过。这两项为当前 Mac 本地追加证据，不混入 d75297fb 冻结 CI 的测试总数。

当前 251 条中 232 有定位断言、19 未定位；197 partially_verified / 54 planned / 0 verified。LIFE-09 的活动 worker/保存/未知写联合链、完整打包和实网条件仍保留，releaseAccepted=false。

2026-09-22 当前 CI 两个失败均保留：Windows 调度终结测试一秒总预算、ARM 真实 HTTP 控件默认一秒等待。按实际通知/HTTP 完成修正测试，生产源码不变；运行与反例见 final-review 知识记录。不得把旧矩阵或本机通过说成当前三平台全通过。

2026-09-22 后续：17 项共享领取文件通过，增加已有坏业务值的状态边界断言。Sheets 坏普通值无法物化的新缺口已复现，D1 具体规格/契约/切片已记录 proposed 并单独询问；C/R 不受阻。机器重算修正手工统计错误为 233 有断言/18 未定位/196 partial/55 planned/0 verified（此前 LIFE-09 已 partial，不能重复算升级）。

2026-09-22 继续核对：SH-02 两个顺序共享写直接断言，完整同步文件 35 passed/39.99 秒；SYNC-09 复核既有失败推值后双拉取和真实 Task 领取。仅这两项 planned→partial，最新机器统计 235/16/198 partial/53 planned/0 verified。所有后补均为测试/记录，生产源码仍 3c02b51f。

2026-09-22 D1 已获批准并实施：原值旁展示结构化格式诊断，Sheets/XLSX 安全业务 Scalar 保留；身份和非法 wire Scalar 仍拒绝。134 后端/11 UI 通过；真实 worker 过滤无命中，保持未验收。生产新候选为 b44cf86d，releaseAccepted=false。
