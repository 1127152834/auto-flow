# PM9 assertion mapping review

2026-09-23 当前台账（confirmed；以 `coverage.json`、`coverage-audit.json` 及 `node scripts/verify-pm9-coverage.mjs` 核对）：251 条中 248 条有明确子范围断言，3 条未定位；205 partially_verified、46 planned、0 verified。未定位的正是 DATA-LIFE-01（待批准 L1 同主体重授权）、DATA-SH-03（待批准 M1 云端并发新增行）和 XE-G07（完整窗口/平台实机门禁）。73 条历史预定测试路径仍不存在，但 72 条已映射真实断言，XE-G07 明确保留缺测试/外部验收。DATA-LINK-02 的跨项目身份和整组关联反例已 RED→GREEN，从 planned 升 partial；真实 worker data-link-race 已证明 End 保存后的伪造项目身份修复保持未关联、正确修复仅关联且不重跑；worker 直接产生伪造 End 目标的断言仍缺，当前打包链已通过但不等于完整业务验收。新源码 c16532d7 的 Windows/ARM 完整 CI 与 ARM 隔离安装已通过；Intel 首次 CI 的测试和打包 smoke 通过，但 DMG 临时磁盘弹出失败，同源码单 job 重跑后完整成功。首轮失败保留，Intel 物理安装仍待验收。此前 dadb24a1 仍属历史源码。旧日期段落为各候选快照，最新证据见 `verification.json`、`link-boundary-follow-through.json`、`ci-link-boundary-final-follow-through.json` 和 `installed-arm-link-guard-candidate.json`；旧候选见 `ci-s4-final-follow-through.json`。

2026-09-23 本机回归收口（confirmed）：生命周期源码94f8e0a8完整后端3472 passed/74 skipped/2 warnings，796.74秒；之后defa1955二进制读取补丁单独16项+真实worker1项、Ruff/mypy407/构建/原15秒sidecar通过，未宣称同一最终本机全量快照。最终三平台35816693045进行中。已完成源生产恢复/删除/服务重启补证及运行目录清理修复；Windows真实PNG409的读取修复待原生确认。旧14df矩阵35811305102两种Mac成功、Windows失败；所有旧状态以此按hash区分。releaseAccepted=false。

2026-09-23 最新候选 defa1955（局部 confirmed，完整验收 pending）：已修复项目删除遗漏 Run 目录；源生产联合链归档→服务重建→恢复不重放→清理残留→服务重建自动续跑1项通过。随后从历史Windows真实PNG GET409定位并修复O_BINARY缺失，二进制契约/证据16项、Mac真实worker1项通过。三平台35816693045进行中；35815127474/35816258910因新缺陷修复取代而取消，不计通过。下文旧候选/计数/状态仅为历史；248/251有范围断言，203partial/48planned/0verified，releaseAccepted=false。

2026-09-23 Windows 截图后续：旧14df候选原生真实截图内容GET409，公共读取缺少O_BINARY；已修复并强化二进制fixture，本机16项与真实worker1项通过，Windows修复后复验待完成。详见 windows-artifact-binary-read.json；未开放S4既有文件能力，不提升覆盖状态。

2026-09-23 生命周期重启补证（confirmed 局部）：真实 worker 联合归档→重建服务→恢复→删除残留→再次重启沿原命令清理已通过（最终仅等待后台自动推进，1 passed/15.15秒）；修复删除遗漏项目运行目录，相关21项、Ruff/mypy407、OpenAPI、构建与原15秒sidecar通过；独立审查无P1/P2。Google/凭据与权限失败仍为受控 fixture，运行目录内文件为已知 fixture。完整回归进行中，旧矩阵35815127474不含本次补丁。PM-04/PM-05/XE-G06补断言但不升 verified；Workspace/G01–G05及外部验收保留。详见 lifecycle-restart-follow-through.json。下列旧轮次结论只对应其历史候选。

2026-09-23 XE-A17 最终本机核对（confirmed）：源码f6a5023e、测试快照9a5a80aa；完整回归3471 passed/74 skipped/1旧准入顺序断言失败（857.72秒），修正后所在文件16 passed（4.33秒）。不称为一次全绿。新三平台35815127474进行中；旧断言矩阵35814591659已取消。真实联合最终1 passed，Sheets worker五项及相关79项通过；Ruff/mypy407/OpenAPI/构建/原15秒sidecar通过。XE-G06仅补归档blocker子范围，248/251有范围断言、3未定位、203partial/48planned/0verified；其余生命周期和外部验收继续保留，releaseAccepted=false。

2026-09-23 XE-A17 收尾补证（confirmed，本段取代此前当前统计）：本机真实 HTTP/SQLite/两 worker/浏览器联合归档通过，已受理保存仅一次，未知写核验前不完成，pending 不重发；同文件 5 passed（60.11秒）。修复归档/核验门禁、任务更新缺同步意图、End 阻塞与取消清理竞态、终态实例残留；新完整回归/三平台仍在推进。台账为 248 有范围断言/3 未定位、203 partial/48 planned/0 verified；没有升级 verified。计划及详细边界见 archive-settlement-follow-through.json，releaseAccepted=false。此前候选与结果均为历史范围。

2026-09-23 本轮回归收尾（confirmed）：生产候选14dfae7c；本机后端完整3465 passed/73 skipped/2 warnings（966.88秒），前端5471通过，类型/lint/OpenAPI/Ruff/mypy407/前后端构建通过。产物sidecar首次15秒就绪超时；诊断3545ms且健康200，原15秒复测通过，但首发原因未明，不能声称修复。单次新三平台35811305102仍运行，旧c9矩阵因新增checkpoint修复取消。后续aef0f412仅测试/记录，与候选生产源码一致但其新增断言不在该矩阵。releaseAccepted=false。

2026-09-23 XE-G02 子范围复核（confirmed）：本机真实 success/manual-stop 两场景 2 passed/32 deselected（25.21 秒），分别证明有限两次参数运行/日志输出/同键重放/资源回收，以及实际人工等待后的取消和清理；独立通用核心场景证明准备内容不被后续文档编辑替换。强停、归属不明的退出核验与安装包/三平台整组门禁仍未闭合。当前 246 有范围断言/5 未定位、203 partial/48 planned/0 verified，不按数量判断完成率。

2026-09-23 XE-A19 共享核心补证（confirmed）：复用现有真实浏览器持久运行场景，SQL 核验零 Project/仅一 Run；仅 browser 能力准备项目 createRecord 文档被明确拒绝，原文档不变且随后可编辑保存，不隐式建项目。1 passed/3 deselected（11.65 秒）。仅 core/document/worker 子范围由 planned 改 partial；Studio 窗口提示/编辑体验、HTTP 联合和打包验收未完成，新断言不在已启动的14df矩阵中。最新 245 有范围断言/6 未定位、203 partial/48 planned/0 verified；先前计数为历史。

2026-09-23 XE-C07 最新补证（supersedes 此前 243/8 统计）：真实 TCP/worker 人工等待场景发现 checkpoint 未纳入公开事件投影，导致 JSON/SSE 补读 409；已补最小身份/版本契约及生成类型，内部续跑内容不公开。修复后真实断开/继续/缺口补读、8 次唯一节点访问、3 个输出、日志分页、失败截图摘要和资源回收通过；20 项后端契约/证据与25项相关前端通过，独立审查无 P1/P2。前端 EOF 去重是独立受控测试，尚非安装包 UI 断网联合证据。台账 244 有范围断言/7 未定位、202 partial/49 planned/0 verified；完整回归/新候选 CI 见 verification.json 与 event-reconnect-follow-through.json。releaseAccepted=false。

2026-09-23 最新机器统计：251 条，243 有范围断言/8 未定位，202 partial/49 planned/0 verified。DATA-TABLE-08 已改为充分授权后的目标拒绝与真实绑定拒绝；DATA-WRITE-12 新增双任务反向单记录冲突，组原子性和 worker 重试仍待补。D1 专属真实 worker 已发现并修复输入校验遗漏，本机 4 个 Sheets worker 场景通过，Google/凭据受控且非打包；新三平台待验收。下文旧证据按日期保留，精确范围以 coverage.json 为准。

日期：2026-09-21。状态：confirmed（映射审查），完整产品验收仍未完成。来源：原始设计各需求编号、现有测试函数断言及本轮运行记录。

251 条全部保留原 id、来源和预定文件；新增 `testMapping` 是当前审查结果。初审 200 条定位到实际测试断言，其余 51 条明确记录未定位到直接场景测试。部分有测试的条目也有未覆盖条件。73 条失效预定路径全部补了映射或缺测说明，没有创建空测试文件来满足路径检查。

`checks.scope` 只说明该函数实际断言的子集；`gaps` 说明未证明的条件。`test_missing` 表示本次未定位到完整场景的直接断言，不证明实现不存在。`implementation_missing` 必须有代码边界支持；`production_evidence_missing` 表示替身/领域/契约断言不能替代真实生产链；`external_acceptance_pending` 需要外部授权或机器。一个需求可同时包含多类缺口。

原有 22 条 verified 也存在未闭合条件，已逐项按记录中的缺口退回 partially_verified，原状态保存在 `statusBeforeReview`。不把历史 PM1/PM2 等阶段报告删除，也不把它们当作整个 PM9 的重新验收。未批量提升任何状态。

静态检查：`node --test scripts/verify-pm9-coverage.test.mjs`、`node scripts/verify-pm9-coverage.mjs`。检查 251 个唯一 id、实际文件/函数、分类与缺口；拒绝不存在函数、非法分类、带缺口的 verified。它不理解业务断言，不能据其通过宣称规格已实现。

补齐真实场景后，204 条具有断言映射，47 条仍未定位直接场景断言；当前 188 partial / 63 planned / 0 verified。新增场景只将直接匹配的 planned 改为 partial，未清除尚未覆盖的原始业务组合。

本轮真实场景复用 `scripts/project-runtime-smoke.mjs`，源码与打包应用调用同一入口。交付中保存对应原始 JSON；只有报告明确出现且断言通过的场景才可增加生产证据。真实 worker 的响应丢失/人工竞争使用 `test_project_batch_real_cloakbrowser.py`，明确记录故障注入边界；不将受控时钟称为实时时序性能测试。

服务账号 Sheets 与系统凭据已有 PM6 历史实网证据；本轮映射中的当前生产证据缺口不撤销该事实。OAuth、当前 PM9 打包全链、签名及实机专项仍单独待验收。`releaseAccepted=false`。

补测校正：DATA-E2E-06 仅对串行真实加列/增行/修改/状态断言提升为 partial；多个活跃 Run 的能力缺失另列 implementation_missing，不提升为 verified。FLOW-A02 仍 planned；单槽排队证据不是并发隔离正向证据。


2026-09-21 S1 更新：增加冻结子图、显式 IO、两次调用和父撤销的直接断言，XE-C02 不再是零定位断言；当前 205 条有定位断言、46 条未定位完整直接断言。188 partially_verified / 63 planned / 0 verified 不变；局部断言不替代全部资产和三平台验收。

## 2026-09-21 C1–C3 共享身份逐项复核

DATA-ID-06 新增精确公共键、本地身份和游标分离断言；DATA-SH-13 新增容量 2 的实际 worker 人工继续/取消/进程失联后按 Q 独立业务状态再领；DATA-SH-14 新增不同身份列允许保存和读取但拒绝领取的具体原因。UI 只证明已有共享原因展示及隐私，不替代该故障实际页面链。当前 225 有范围断言 / 26 未定位，191 partial / 60 planned / 0 verified；历史 73 失效预定路径不改写。C4 完整回归、新三平台及当前打包 Google 专项仍待闭合。

2026-09-21 R1：DATA-SCHEMA-01 的无断言/实现缺失已由明确结构查询测试替代，逐项指向范围见 coverage.json；当前 226 有断言 / 25 未定位，状态仍 191 partial / 60 planned / 0 verified。

2026-09-21 R2：DATA-SCHEMA-06 按字段删除具体断言从 planned→partial；DATA-SCHEMA-09 只补第二 Task 依赖保护，不冒充同键异型/新字段写回组合验证。当前 227 有断言/24 未定位，192 partial/59 planned/0 verified。


### 2026-09-21 R5 来源观察（confirmed，局部证据）

普通远端值通过现有 SyncRecordMarkRow.inboundObservation 保存最近每字段观察；与 identity/outbound 证据合并。当前 generation/epoch、字段/映射与记录存在性约束后，只读 HTTP/详情显示来源值、观察时本地值和修订。普通值、状态/关联、内容修订和待发送意图不改；公式保留既有刷新。重复身份不更新观察。无采纳/回滚/云写入口。

59 项后端、18 项组件/客户端检查通过；ruff/mypy(404)、typecheck/lint/OpenAPI/build 通过。DATA-SH-06 移除对应 implementation_missing，仍 partially_verified；251 条、227 有定位断言、24 无定位断言、192 partially_verified/59 planned/0 verified 均不变。早期 PM6 记录对“远端差异可查看”的范围已明确纠正，不否定其既有服务账号实网及系统凭据证据。

C4 35597323657 @21f8bb1e：ARM 已通过；Windows 全量后端 3338 passed/74 skipped、前端 5460 passed/406 files，但真实 worker 13 failed/5 passed/11 deselected，进程失联原因待诊断；Intel 当时仍在运行。以上 C 候选不含 R1/R2/R5；不得算当前候选三平台通过。R3/R4 仍按批准顺序待实施，releaseAccepted=false。

### 2026-09-22 R3 与 C4 更新（confirmed，局部验收）

R3 已冻结原操作 UUID、身份列归属及行证据，单次 Sheets batchUpdate 新列/值/metadata。未知响应仅核验；仅证明未发送的原计划允许重试，UUID 不重生成。原操作发布绑定与成功状态同事务；资料修订变化须重新预览影响后明确核验。复用本工作区已验证系统列不云写；同名未知归属拒绝。UUID 拉取/推值接通，文本视图和 UUID 本地键解析同一公共 lease。未决结构发送阻断其他绑定推值、领取和改绑；值发送未知先阻断结构发送。共享 GoogleAccess 使用标准库 RLock 序列化读计划到发送，并以现有 SQLite 账本保留跨请求/重启的未决围栏。没有第二执行器。

90 项后端相关检查、25 项组件/客户端通过，ruff/mypy（406）、typecheck/lint/OpenAPI/build 通过。覆盖账本 251 条中 228 有定位断言、23 未定位，193 partially_verified / 58 planned / 0 verified。DATA-ID-05 只升级 partial；真实 Google 和当前打包完整应用链仍待验收。

C4 Mac @21f8bb1e 的 ARM/Intel 全部通过；Windows @07619b6d 完整流水线 35605861737 通过：3384 后端（77 平台 skip）、5464 前端（407 文件）、21 真实 worker、源码/包链/安装包和万行写入。万行发生 8 次明确 busy 重试，不构造新的性能门槛。两份源码范围分别保留，R3 不包含在这些 CI 中。此前 C4 “Intel pending/Windows failed”当前状态由本节 supersede；失败日志仍保留历史。R4 接续，完整当前候选矩阵与一次整批复审在 R4 后执行。releaseAccepted=false。

### 2026-09-22 R4 受控增列（confirmed，局部验收）

显式选择普通本地字段、列名并确认远端写入后，原操作冻结目标/epoch/field/revision/owner，在网格末尾单次追加列、表头和归属 metadata。未知响应只核验原列；同名外部列、移动/改名/缺 metadata/非空列不猜测接管。仅确认未发送可原计划重试或取消，取消保留本地字段和值。确认事务兼容扩展 mapping、保持 generation/epoch/记录版本，并将已有新字段值放入现有队列，值发送依赖原列成功。既有冻结 Task 可以继续旧字段修改，不能因此扩大新字段权限；后续同步重验已创建列归属。

HTTP/SQLite/受控 transport 相关回归 113 passed（138.65 秒），组件/客户端 38 passed（5 文件），ruff/mypy（407）、typecheck/lint/OpenAPI/build 通过。另发现通用放弃接口跨项目及结构命令越界，两项 HTTP 反例复现，修复范围限定共享入口的项目归属与内容意图类型。覆盖账本仅 DATA-SCHEMA-07 新增具体断言并改 partial：251 条中 229 有定位断言、22 未定位，194 partially_verified / 57 planned / 0 verified。现有历史统计按日期保留。

R1/R2/R5/R3/R4 与 C1–C4 已有实现和分范围证据；最终整批独立审查、当前完整回归和三平台矩阵接续。真实 Google、当前打包完整 Sheets 链、OAuth、物理安装和签名仍未验收；S4 已存在文件安全覆盖/追加/读取与未批准 M1–M3 仍为实际缺口。releaseAccepted=false。

### 2026-09-22 整批审查修复与映射复核（confirmed，回归进行中）

一次独立审查发现 3 项 Important：UUID 公共 lease 查询未归一类型、未知值核验缺来源归属检查、推送明确发现坏身份后未失效旧领取证据。均已用直接 HTTP/SQLite 反例复现，按共享入口修复；推送与核验复用完整身份观察，可靠身份的普通推值失败不受牵连。新组合断言明确失败意图和本地新值保留、后续拉取正常、真实 Task 领取冻结本地值并继续公共排他。新增 R4 测试也直接证明加列后旧 Patch 推回原 B 列与旧 Task 权限兼容。

DATA-CLAIM-09、DATA-SCHEMA-08 仅新增上述范围映射，未证明的来源读取失败/界面提示、删除本地字段不删远端和生产端到端条件仍保留。当前 251 条中 231 有定位断言、20 未定位，196 partially_verified / 55 planned / 0 verified。完整前端 5469 passed / 409 文件 / 198.85 秒，前端源码之后未改；最终后端和三平台仍在验证。详见 shared-data-final-review.json。releaseAccepted=false。

### 2026-09-22 原生 CI 期间继续补证（confirmed）

新增两项直接业务场景，生产源码未变：DATA-LIFE-09 在真实 HTTP 归档收尾后保留未发送本地值及原意图，新推送 409、远端无写；DATA-SCHEMA-08 先由未决意图阻断本地字段删除，明确放弃后删除本地字段而同名远端列/值保持，状态与关联修订不变。两个相关完整文件 21 passed（17.71 秒），全目录 Ruff 通过。这两项为当前 Mac 本地追加证据，不混入 d75297fb 冻结 CI 的测试总数。

当前 251 条中 232 有定位断言、19 未定位；197 partially_verified / 54 planned / 0 verified。LIFE-09 的活动 worker/保存/未知写联合链、完整打包和实网条件仍保留，releaseAccepted=false。

2026-09-22 最新补证：已有坏业务值 fixture 的 HTTP 状态设置/占用 held 与 reconciling 拒绝/模拟释放后清空通过；17 项共享领取回归。D1 实现后，Sheets/XLSX 普通来源业务格式错误保留原值并派生诊断；身份与 unsafe wire scalar 严格拒绝；必填来源缺失保持缺失；Sheets 先全量预校验再物化，避免坏身份造成半批发布。真实 worker、打包完整链和实网授权仍未验收。当前机器统计 251/235 有断言/16 未定位，198 partial/53 planned/0 verified；前文 197/54、233/18 为阶段性手工统计，本节 supersede。未改变任何条目状态。当前补跑固定 0d7524d9，后补的状态场景单独保留本机范围。

### 2026-09-22 D1 review修复与三平台候选（confirmed）

D1 独立审查发现的三个重要问题已 RED→GREEN：Excel 身份字段业务格式错误不再降级为文本身份；Excel/Sheets 必填来源缺失不写入 values，由当前字段快照派生 REQUIRED_FIELD_MISSING；Sheets 先全量预校验身份和 unsafe wire scalar，再写入任何记录，晚到坏身份不会留下半批物化。D1 相关定向后端 138 passed、2 warnings；RecordFieldsView/RecordDetailPage 11 passed；Ruff 全目录、mypy 407、OpenAPI、typecheck 通过。UI 诊断为字段列表后的聚合面板，仍能区分格式问题与读取失败，记作 Minor 表达差异。

候选 ae347de9f5fc1922efa7c4af99c0e606e6bde26a 的 Actions 35677887974 在 Windows x64、macOS Intel、Apple Silicon 全部通过：各平台后端 3443/3453 passed（平台 skip 保留）、前端 5470 passed、21 个既有真实 worker 场景通过；同提交源码/打包链、五路万行写入和 1000 条/分钟合成日志报告已保存为 ci-d1-final-*.json。这证明 CI 平台链，不等于物理安装、签名、公证或真实 Google/OAuth 验收；native probe/worker probe job 被跳过。

当前台账为 251 条、236 条有明确范围断言、15 条未定位，198 partially_verified、53 planned、0 verified。D1 专门坏业务值 worker 筛选未命中，仍未宣称；S4 已存在文件覆盖/追加/读取、M1–M3、真实 Google/OAuth、完整打包 Sheets 链和三平台实机安装/签名仍是实际或外部条件缺口。releaseAccepted=false，草稿 PR 不合并、不发布。

### 2026-09-22 DATA-TABLE-08 补证

`test_system_status_is_read_only_while_business_status_field_and_status_write_coexist` 以真实 SQLite 能力服务联合断言：结构查询返回固定 `statusId` 且 `writable=false`；普通 `status` 字段可以共存；伪造系统字段的改型、删除和来源映射分别被拒绝，失败操作不留下持久事实；同一条记录仍可通过正式状态命令写入业务状态。定向文件 15 passed；此证据仍属于本机能力服务集成，不替代真实 worker、打包应用、三平台原生交互或 Google 实网验收。

2026-09-23 后续参数场景：parameter-isolation 在真实 HTTP/SQLite/worker/CloakBrowser 本机运行通过（1 passed/30 deselected，28.56s）。两个 Task 的 taskLocal 初值均为 0，前一任务写入不进入第二任务；结果可查询，无 DataLease；同名项目结果列的原记录及版本完全不变。FLOW-A01 增加范围断言，FLOW-A10 由 planned 升为 partial；当前 240 有断言/11 未定位、200 partial/51 planned/0 verified。此前一次退出 TimeoutError 已保留，根因未确认；本机最终通过不代替该场景的打包/三平台证据。

2026-09-23 FLOW-A05：同一自动化两个独立单任务批次的可选输入从有到无，真实 worker 验收 1 passed/31 deselected（37.63 秒）。第二次两次 inputs capability 输出与持久快照均空，零 lease，首次快照保持且资源回收；不是同批次、变量表达式或打包 UI 证据。独立复审无 P1/P2。最新 241 有断言/10 未定位、201 partial/50 planned/0 verified。

2026-09-23 XE-A01：parameter-single 真实 worker 场景 1 passed/32 deselected（38.06 秒）；无表、参数 first 网页填写/读取、同键重放后唯一 Batch/Task/Run、零 lease 和资源回收联合通过。仅本机源码证据，不扩大为打包 UI/三平台或 XE-G02 全部门禁。当前 242 有断言/9 未定位、201 partial/50 planned/0 verified。

2026-09-23 生命周期补审：LIFE-01/02 不能再仅写缺测试——连接无原位重授权/稳定主体契约，普通改绑无条件新建数据代次。LIFE-07 临时真实 HTTP 探针复现旧 unknown 仍在时重绑并再次云写；L0 在改绑新/旧目标及解绑复用持久值发送围栏，4 个直接反例 RED→GREEN。L0只拒绝绕过，不完成永久失权隔离；L1→L2→L3 具体规格/计划已保存，新增能力尚待批准。最新 243 有范围断言/8 未定位、202 partial/49 planned/0 verified。生产候选已改变，旧 c2 矩阵不能证明此修复，新完整矩阵见 verification.json。
2026-09-23 DATA-WRITE-13（confirmed 局部）：新增真实 worker + 受控 Sheets 来源第二表循环场景，直接断言前两条数据修改与 pending 意图在第三次字段失败后保留，动态 lease 释放、End 未运行。源码变量解析缺陷已修复，单独 Sheets 6 项与变量差异 20 项通过。该条由 planned 升为 partially_verified；仍缺打包 UI、真实 Google 送达核验和三平台该组合。现 251 条中 248 有范围断言、3 未定位，204 partial/47 planned/0 verified；releaseAccepted=false。详见 sheets-loop-partial-follow-through.json。


2026-09-23 真实 worker 伪造 End 补证（confirmed，仅本机源码）：新增 `data-link-forged-end`，由实际两次 createRecord 输出生成一条合法目标和一条仅替换 projectId 的伪造目标。原 worker/父进程能力服务拒绝整组：End 为 CAPABILITY_SCOPE_DENIED、两个项目均零环境、零 end-save 操作；两条已写数据及 linkRevision=1 保留、两条 lease 释放、进程/临时目录清理完成。与原 data-link-race 共 2 passed/33 deselected（64.70 秒）；契约/规则 33 passed、Ruff 通过。首次测试仅末尾错误的 /fixture 计数断言失败，既有数据场景实际打开 /login，修正测试后通过，无新增生产修复。CI 选择已纳入新场景；生产源码仍 c16532d7，此次新增断言不计入历史三平台结果。DATA-LINK-02 仍 partial，完整打包/跨平台反向场景及用户验收保留。251 条结构复核无未分类项，73 条预定路径缺失中 72 条已有范围映射，205 partial/46 planned/0 verified；`releaseAccepted=false`。


2026-09-23 新字段结果写回缺口（confirmed，当前 ARM 打包实测）：DATA-SCHEMA-02/09、FLOW-A14 从“仅缺测试/生产证据”纠正为 implementation_missing。T1 新增字段后写新 fieldId 被 CAPABILITY_SCOPE_DENIED 拒绝；提前静态授予未存在字段则批次 409 CAPABILITY_FACTS_INCOMPLETE。两个失败报告及可重放补丁均保留，清理通过，不计验收成功。现有打包业务脚本新增同定义复用、异型同键冲突、原结构/值不变及 T2 旧契约兼容并通过；脚本101项通过。具体字段结果来源授权、调用/分支/循环隔离及动态字段键契约见 FR1–FR3 规格/计划，尚未批准，未放宽现有权限。详见 [报告](created-field-results-follow-through.json)。251 条状态仍205 partial/46 planned/0 verified，releaseAccepted=false。
