# 项目上下文

2026-09-24 XE-C06/XE-G02归属不明核验修复（confirmed本机源码/新包子范围，三平台pending）：生产cb040daf修复参数/数据批次在Task核验中仍显示stopping，并通过既有停止操作保留停止意图，避免重新领取及状态版本抖动。四个反例先失败，相关50项通过；真实普通/已知/未知归属强停3项通过（92.10秒），Ruff/mypy408及映射4项/251引用通过。串行完整后端3497 passed/84 skipped/2 warnings（900.44秒）；新未签名ARM包完整桌面passed/22截图，已目视核对3张。真实worker1004条/31410ms、万行43624ms/0busy、固定1000条合成输入60016ms均为单次本机观察。归属证明缺失期间保留进程/目录/容量/原命令，恢复后原命令完成。Windows Job和打包核验UI仍缺；旧35902129697三平台job成功但不含当前源码，CLI401/日志403仍阻断新矩阵与产物复核。251条状态不升级，releaseAccepted=false。详见unknown-owner-follow-through.json。

2026-09-24 XE-G02强停补证（confirmed本机子范围）：参数真实worker在普通停止后模拟下行通道丢失，实际30秒宽限期内409，公开门禁到期才强停；原生birth身份/进程退出、执行代次撤销、interrupted未知结果、人工取消、临时目录/容量回收及原命令终态查询重放通过，无后续节点/额外Task。最终普通停止+强停2 passed/34 deselected（74.42秒），Ruff通过；既有CI选择新增场景并collect35/46（非运行）。早期夹具/终态/DTO时间比较错误全部保留，不称产品修复。归属不明核验、打包UI与新增三平台仍待验；无生产改动，251条状态不变，releaseAccepted=false。详见force-stop-follow-through.json。

2026-09-24 DATA-WRITE-12审计勘误（confirmed缺口，G1–G3 proposed）：领域/服务/worker/Studio仅单条updateRecord，仓库每条独立提交；运行契约检查拒绝两条RecordRef数组（VALIDATION_ERROR）。单条反向冲突及原命令重放2项通过，不是组原子验收。将该组子条件由test_missing纠正为implementation_missing，新增G1–G3具体规格/计划等待确认；无业务代码修改。251条仍249有断言/2未定位、206partial/45planned/0verified；按需求去重缺口241生产/17实现/8测试/24外部（可重叠），releaseAccepted=false。见group-write-audit.json。

2026-09-24 同行改绑补证（confirmed局部）：公开A→B→A身份列替换产生新代次/epoch；异namespace时断网和完整本地拉取均拒绝领取。修复完整拉取后两真实worker各冻结正确当前代次/原值，人工继续各写一版本和一pending意图，零远端写入、旧失败批次不重启。最终相关3 passed/7 deselected/2 warnings（32.46秒），Ruff通过；CI原选择collect34/45且含新用例（非运行）。仅关闭DATA-CLAIM-09已列明的test_missing，保留生产/外部缺口；总计249/2、206partial/45planned/0verified，缺口计数241生产/16实现/9测试/24外部（可重叠）。本片无生产修改、不重复全量和打包；新原生运行仍待认证，releaseAccepted=false。详见peer-rebind-follow-through.json。

2026-09-24 同行来源补证（confirmed局部）：新增真实HTTP/SQLite/worker验证坏身份同行解除绑定后、剩余表拉取失败仍拒绝领取；修复完整拉取后显式新批次才执行，旧失败批次不重启。最终1 passed/10.63秒，CI原选择已收集新用例（33/44，非运行结果）；无生产变更，不重复全量/打包。见peer-outage-follow-through.json；新原生验证仍受认证阻断，releaseAccepted=false。

2026-09-24 当前补丁1c676965（confirmed本机全量/ARM打包，原生新矩阵待验）：首次来源读取失败的空缓存被误报noMatch，已将共享来源身份校验前移至候选扫描，必要/可选输入均明确configurationError。42相关、6边界、2真实worker及Ruff/mypy408通过；完整后端串行3493 passed/80 skipped/2 warnings（778.49秒）；后端构建/ARM打包及完整桌面22截图通过。该生产补丁不在35902129697/35895754111中，两轮旧CI继续保留。详见partial-source-follow-through.json；releaseAccepted=false。

2026-09-24 旧候选三平台完成：35895754111@25bb8ab2整体success，日志和三个原生产物已核对。Mac后端3486/78skip、Windows3478/86skip；三平台前端5473/409文件、真实worker30/11deselected。Windows桌面worker604条/分钟，万行582160ms；Intel1725条/分钟，万行125601ms，均0busy；固定合成负载另列，不声明新性能门槛。该结果仅覆盖生产69baeeb2；不覆盖51e8991e和1c676965。详见ci-metadata-click-follow-through.json，releaseAccepted=false。

2026-09-24 旧候选 ARM CI 产物复核（confirmed 局部）：35895754111@25bb8ab2 的 artifact10769571016 已下载并校验 SHA256；打包 API、business-combinations、完整桌面均 passed，22截图中必填提示/紧凑重开/恢复文档3张已目视核对。真实 worker1004条/38623ms（1560条/分钟），万行67095ms、0busy，固定合成1000条/60189ms；均为该次观测。详见 ci-metadata-click-follow-through.json。该证据不覆盖新生产51e8991e或新增两个 worker 场景；新矩阵35902129697仍进行中，台账状态不变，releaseAccepted=false。

2026-09-24 最新CI（confirmed调度，验收pending）：已推送a317e1f8，实际新矩阵35902129697同headSha、生产51e8991e，包含断网与反向写两个新增真实worker案例，三平台in_progress。旧35895754111@25bb8ab2继续，ARM job107299145250已success，Windows/Intel仍运行。新候选稳定后单次调度，取代此前等待旧矩阵全部结束的安排，无取消、无相同源码重复。PR仍草稿、releaseAccepted=false。

2026-09-24 DATA-WRITE-12补证（confirmed子范围）：新增两真实worker固定A/B先写，再反向query/update均LEASE_BUSY进入人工错误分支；冻结原输入v1、当前值/游标v2、双方lease及A/B两条pending意图不变，stop后释放。最终1项12.89秒通过；首次未声明筛选字段422夹具问题保留并改用既有fixedRecord。无生产改动，仍51e8991e；CI选择32/43包含本轮两新增案例。组原子性/配置重试/打包/Windows/Intel仍待验，opposing-writes-follow-through.json。

2026-09-24 来源断网切片（confirmed 定向/打包，本机完整复验通过、原生后续未收口；supersedes 下文“当前”候选）：生产51e8991e、证据669c01c0已推送草稿PR #1。lastPulledAt/latestPull修复来源拉取卡从出站列表推断拉取的错误；受控Google断网可靠缓存真实worker成功、重复身份后再断网零Task通过。全前端5474/409、102脚本、4映射/251引用、类型/lint/OpenAPI/构建和新ARM完整桌面22截图通过。首轮全后端3483通过/79跳过/4项进程时限失败保留，原样6项复查通过，串行全量3487通过/79跳过（836.98秒）；不据复跑推断根因修复。旧矩阵35895754111@25bb8ab2仍在运行，不包含51e8991e生产修复。详见source-outage-follow-through.json。251条249有断言/2未定位，206partial/45planned/0verified；releaseAccepted=false。

2026-09-24 并行补证/CI诊断（confirmed局部）：ARM正式打包API通过2/3次循环变量隔离与精确五条写入、唯一End声明输出关联、并行人工串行交接和停止保留前写。公开事件不提供内部scope、同workflow重复绑定两次脚本错误已修正并保留失败报告。当前69baeeb2三平台35886627514的ARM在打包必填提示失败，截图节点未选中，metadata HTTP断言和后端3486/前端5473通过；旧点击helper对覆盖目标误点已由隔离Electron复现并修复，102脚本/4映射及完整ARM打包桌面通过。最终三平台均失败：Intel同为未选中节点，Windows为紧凑重开窗口隐藏就绪文字。恢复视口及显式展开面板已复现通过，最终完整新版桌面通过；全部旧job结束后已触发三平台35895754111，源码25bb8ab2（生产仍69baeeb2），结果待完成。详见parallel-packaged-follow-through.json和ci-metadata-click-follow-through.json。251条状态未升级，releaseAccepted=false。

2026-09-24 Profile冻结补证与代理勘误（confirmed子范围）：ARM正式打包API/真实worker证明旧批次两个Task保留原根文档、UA/语言/时区及实际启动seed，新批次使用公开编辑后的新值。Canvas实测不变，错误的必变断言已更正并保留负向报告。现有资源类/SQLite诊断证实代理新成员与改动端点进入旧快照，ENV-05/XE-A20/XE-C02增加implementation_missing，P1–P3规格/计划待确认。完整打包API/ARM桌面、101脚本/4映射/251引用通过；生产仍69baeeb2，三平台35886627514继续且不含本次新脚本断言。249有断言/2未定位、206partial/45planned/0verified不变，releaseAccepted=false。详见resource-freeze-follow-through.json。

2026-09-24 子流程打包补证（confirmed子范围）：正式ARM应用/sidecar公开HTTP与真实worker完成准备后改文档、两个Task各两次冻结调用、变量隔离与声明输出、根End双记录关联；子流程等待后公开stop父批次保留首条记录/取消人工项/不执行后续写及End；父节点较宽字段权限不能被受限子节点借用，返回CAPABILITY_SCOPE_DENIED且保留父提交。完整API/桌面均通过，101脚本/4映射通过。生产仍69baeeb2，运行中35886627514不包含新增脚本断言，不重启；其他资产/Profile/代理组合与Windows/Intel同场景打包证据保留。249有断言/2未定位、206partial/45planned/0verified不变，releaseAccepted=false。详见subflow-packaged-follow-through.json。

2026-09-24 必填规则生产修复（confirmed本机）：正式metadata404已由共用DTO路由和随包冻结资源修复，实际ARM空网址提示/项目规则未覆盖提示通过；来源227仅69有规则。17后端定向、45前端、3486全后端/78skipped、101脚本、4映射、Ruff/mypy408/typecheck/lint/OpenAPI/构建与完整ARM桌面通过。原后台页面两帧测量两次失败，诊断hidden后前置显示并确认可见，保留5秒阈值，最终5ms；负向报告保留。见studio-metadata-follow-through.json。249有断言/2未定位、206partial/45planned/0verified不变，生产69baeeb2的三平台35886627514已触发、结果待完成；releaseAccepted=false。

2026-09-23 XE-G07窗口子范围（confirmed）：当前ARM包实际窗口复用/恢复、越权打开拒绝、脏稿取消/保存关闭、显式重新打开同文档且Run不重复通过；主进程11、脚本101、映射4通过。AU-06/XE-G01/XE-G07项目会话关联与停靠明确为实现缺失，W1–W3规格/计划待确认；新增窗口断言后的完整ARM桌面脚本通过，详见 studio-window-follow-through.json。249/251有范围断言、2未定位，206partial/45planned/0verified；73条缺预定文件全部已有子范围映射，不等于完整覆盖。生产仍632caf6d，新断言不在现有CI35881272086，不重复流水线，releaseAccepted=false。

2026-09-23 XE-A19打包Studio收口（confirmed本机子范围）：实际零Project通用网页运行、项目上下文提示、独立启动422不生成Run，以及编辑保存保留grant/参数通过。已修复旧运行历史遮住操作反馈、打开文档后误发新建请求两处缺陷；最终定向50、全前端5473（409文件/208.97秒）、101脚本、类型/lint、4项映射、构建/ARM打包与最终完整桌面通过。五路10000行47223ms/0busy、固定1000条合成输入60022ms/最大滞后35ms为单次观察。源码632caf6d新三平台35881272086进行中；旧35874897768不含此修复，已确认取消，不计完整通过。见 `.ai/knowledge/2026-09-23-pm9-standalone-studio.md` / `standalone-studio-follow-through.json`；必填规则元数据404与外部发行门禁保留，251条205partial/46planned/0verified，releaseAccepted=false。

2026-09-23 AU-08残留更正（confirmed局部）：5346已通过的快照子范围不证明文件全清理。实际打包删除留下cancelled/resolved人工事项和浏览器失败PNG；人工事项清理/未结束阻断已修复，38后端/6前端/101脚本/Ruff/mypy407通过，新包证实人工项消失但PNG仍在。AD1–AD3持久文件删除恢复规格/计划待确认，旧CI35871462256取消；eb50e1ef全后端3483/78skip、ARM新包完整桌面通过，新CI35874897768进行中。详见 `.ai/knowledge/2026-09-23-pm9-automation-delete-residue.md`；releaseAccepted=false。

2026-09-23 AU-08删除补证与修复（confirmed局部，本机完整通过、三平台进行中）：ARM真实已安装包的独立文档保留、人工等待阻断、旧影响清单拒绝和原键恢复通过；随后直接SQLite断言发现并修复快照影响范围过宽及先删批次导致快照残留。34后端/6前端/Ruff/mypy407通过，5346ceca完整后端3479/78skip、新ARM打包全桌面通过；三平台35871462256运行中，按 `pm9/automation-deletion-follow-through.json` 更新。项目所有权deleteOwned仍未实现；AU-08保持partial，releaseAccepted=false。

2026-09-23 当前字段能力勘误（confirmed）：c16532d7 ARM 打包真实 worker 证明创建新字段后写入受 frozen grant 阻断，预先授权未存在 fieldId 也被拒。DATA-SCHEMA-02/09、FLOW-A14确属实现缺失；同定义复用/异型冲突/T2兼容已补打包证据通过，不能代替新字段写入。新增 FR1–FR3 字段结果权限规格/计划为 proposed，见 `.ai/knowledge/2026-09-23-pm9-created-field-results.md`。此前“已批准功能均有实现”不能覆盖该新反例；releaseAccepted=false。

2026-09-23 End 权限边界补证（confirmed 本机范围）：真实 worker 生成合法/伪造项目记录混合目标，原权限门禁在保存前拒绝整组，已提交数据保留、零环境保存和关联、lease/进程释放。关联两场景2 passed、契约/规则33 passed、Ruff通过；详见 `pm9/link-boundary-follow-through.json`。仅测试/CI选择/文档更新，生产源码仍c16532d7；新增断言不计入此前CI，完整验收仍pending，releaseAccepted=false。

2026-09-23 DATA-LINK-02 新候选（confirmed 本机与三平台 CI 范围，物理发行待验）：生产环境关联仓库预检与提交均增加 `recordRef.projectId` 权威项目核对；伪造外部项目标签但保留本地行键的直接 HTTP 反例 RED→GREEN。本机全后端 3479 passed/77 skipped，契约/规则 33 passed，真实浏览器 data-link-race 1 passed（实际 End 保存后伪造身份修复保持未关联、正确修复不重跑），Ruff/mypy407 通过；251 条台账变为 248 有范围断言、3 未定位、205 partial/46 planned/0 verified。当前 c16532d7 的 Windows/ARM CI 与 ARM 隔离安装已通过；Intel 首次全部测试及打包 smoke 通过但 DMG 临时盘弹出 Resource busy，同源码单 job 重跑后完整成功；首轮失败证据保留，Intel 实机仍待验收。上一 dadb24a1 仍为历史源码。详情见 `docs/project-management/implementation/pm9/link-boundary-follow-through.json`；`releaseAccepted=false`。下文旧候选和统计按各自哈希保留历史。

2026-09-23 本机回归收口（confirmed）：生命周期源码94f8e0a8完整后端3472 passed/74 skipped/2 warnings，796.74秒；之后defa1955二进制读取补丁单独16项+真实worker1项、Ruff/mypy407/构建/原15秒sidecar通过，未宣称同一最终本机全量快照。最终三平台35816693045进行中。已完成源生产恢复/删除/服务重启补证及运行目录清理修复；Windows真实PNG409的读取修复待原生确认。旧14df矩阵35811305102两种Mac成功、Windows失败；所有旧状态以此按hash区分。releaseAccepted=false。

2026-09-23 最新候选 defa1955（局部 confirmed，完整验收 pending）：已修复项目删除遗漏 Run 目录；源生产联合链归档→服务重建→恢复不重放→清理残留→服务重建自动续跑1项通过。随后从历史Windows真实PNG GET409定位并修复O_BINARY缺失，二进制契约/证据16项、Mac真实worker1项通过。三平台35816693045进行中；35815127474/35816258910因新缺陷修复取代而取消，不计通过。下文旧候选/计数/状态仅为历史；248/251有范围断言，203partial/48planned/0verified，releaseAccepted=false。

2026-09-23 XE-A17 最终本机核对（confirmed）：源码f6a5023e、测试快照9a5a80aa；完整回归3471 passed/74 skipped/1旧准入顺序断言失败（857.72秒），修正后所在文件16 passed（4.33秒）。不称为一次全绿。新三平台35815127474进行中；旧断言矩阵35814591659已取消。真实联合最终1 passed，Sheets worker五项及相关79项通过；Ruff/mypy407/OpenAPI/构建/原15秒sidecar通过。XE-G06仅补归档blocker子范围，248/251有范围断言、3未定位、203partial/48planned/0verified；其余生命周期和外部验收继续保留，releaseAccepted=false。

2026-09-23 XE-A17（confirmed，当前修复取代前段候选）：归档联合场景通过，本机真实两 worker/浏览器/HTTP/SQLite，Google transport 受控；保存仅一次、取消清理、unknown 原核验、pending 不补发。相关79 passed/3 skipped；真实Sheets5passed、人工到期竞争复测1passed；完整回归与新矩阵尚未闭合。248/251有范围断言，3未定位，203partial/48planned/0verified。详见 docs/project-management/implementation/pm9/archive-settlement-follow-through.json。L1–L3/M1–M3未经批准，Windows既有文件安全输出仍缺失，releaseAccepted=false。

2026-09-23 本轮回归收尾（confirmed）：生产候选14dfae7c；本机后端完整3465 passed/73 skipped/2 warnings（966.88秒），前端5471通过，类型/lint/OpenAPI/Ruff/mypy407/前后端构建通过。产物sidecar首次15秒就绪超时；诊断3545ms且健康200，原15秒复测通过，但首发原因未明，不能声称修复。单次新三平台35811305102仍运行，旧c9矩阵因新增checkpoint修复取消。后续aef0f412仅测试/记录，与候选生产源码一致但其新增断言不在该矩阵。releaseAccepted=false。

2026-09-23 XE-G02 子范围复核（confirmed）：本机真实 success/manual-stop 两场景 2 passed/32 deselected（25.21 秒），分别证明有限两次参数运行/日志输出/同键重放/资源回收，以及实际人工等待后的取消和清理；独立通用核心场景证明准备内容不被后续文档编辑替换。强停、归属不明的退出核验与安装包/三平台整组门禁仍未闭合。当前 246 有范围断言/5 未定位、203 partial/48 planned/0 verified，不按数量判断完成率。

2026-09-23 XE-A19 共享核心补证（confirmed）：复用现有真实浏览器持久运行场景，SQL 核验零 Project/仅一 Run；仅 browser 能力准备项目 createRecord 文档被明确拒绝，原文档不变且随后可编辑保存，不隐式建项目。1 passed/3 deselected（11.65 秒）。仅 core/document/worker 子范围由 planned 改 partial；Studio 窗口提示/编辑体验、HTTP 联合和打包验收未完成，新断言不在已启动的14df矩阵中。最新 245 有范围断言/6 未定位、203 partial/48 planned/0 verified；先前计数为历史。

2026-09-23 XE-C07 最新补证（confirmed，来源：event-reconnect-follow-through.json）（supersedes 此前 243/8 统计）：真实 TCP/worker 人工等待场景发现 checkpoint 未纳入公开事件投影，导致 JSON/SSE 补读 409；已补最小身份/版本契约及生成类型，内部续跑内容不公开。修复后真实断开/继续/缺口补读、8 次唯一节点访问、3 个输出、日志分页、失败截图摘要和资源回收通过；20 项后端契约/证据与25项相关前端通过，独立审查无 P1/P2。前端 EOF 去重是独立受控测试，尚非安装包 UI 断网联合证据。台账 244 有范围断言/7 未定位、202 partial/49 planned/0 verified；完整回归/新候选 CI 见 verification.json 与 event-reconnect-follow-through.json。releaseAccepted=false。

2026-09-23 L0 最新补审（confirmed，优先于下文 c2 摘要）：旧未知值写可被改绑绕过已复现，三处共享发送围栏修复与4项反例通过，相关回归/新候选矩阵见 `pm9/lifecycle-fence-follow-through.json` 与 verification.json；原c2矩阵不覆盖新生产代码。台账243有断言/8未定位、202 partial/49 planned/0 verified。L1–L3连接恢复/保留身份/隔离新契约已写规格和计划，尚未批准；当前仅安全拒绝，不能声称永久失权处置完成。

2026-09-23 最新 PM9 状态（confirmed；来源 `pm9/input-validation-follow-through.json`，较下文历史摘要优先）：实施仍在独立 pm9-runtime worktree/分支，草稿 PR #1。生产修复 c2d91c5d 补齐 D1 声明输入值的选择/提交校验；未使用坏字段不阻断。全后端 3460 passed/68 skipped，89 定向、4 Sheets 真实 worker、Ruff/mypy407/OpenAPI/101 脚本与后端构建通过；新矩阵 35806853292 仍进行中。后续独立本机 worker 补循环部分成功、参数变量隔离、同名结果不隐式写回、可选输入由有到无和无表参数单任务，当前 242 有范围断言/9 未定位、201 partial/50 planned/0 verified。一次 worker 退出超时尚未查明，不以重跑成功宣称根因修复。S4 既有文件、未批准 M1–M3、打包完整 Sheets/Google/OAuth、签名及实机专项继续保留；PM6 历史实网有效。releaseAccepted=false，不合并发布。最新 CI 状态以 verification.json 为准。

- 项目：AutoFlow
- 目标平台：Windows、macOS
- 目标：在新架构中迁移 browser-automation 的功能；项目管理已形成完整设计，PM1项目入口在独立实施分支交付；之后按用户验收逐阶段实施。
- WebRPA：仅作为能力和实现思路参考，重写能力，不做运行时集成或兼容层。
- 前端视觉方向：保留第三个原型的暖灰画布、黏土棕强调色；2026-09-12 用户明确浏览器配置采用单主内容区，无模块侧栏，内核管理从配置表单以弹窗进入。早期该模块“分栏工作台”的描述已 superseded。
- 前端技术约束：React、shadcn/ui、Tailwind CSS，组件先于页面。
- 协作要求：先规格和实施计划，经确认后再开始功能实现；前后端按垂直功能切片一起开发。
- 2026-09-12（confirmed，来源：用户在项目管理审查后的明确纠正）：项目管理先形成相对完整的功能规格、跨模块业务规则、交互和总体实施计划，再小步开发。最小执行链仅是实施验收步骤；关键业务设计不留到各切片开发时临时决定。详见 `.ai/decisions/2026-09-12-project-management-complete-design-first.md`。
- 2026-09-12（confirmed，来源：用户对数据流与环境保留的明确说明）：每表系统维护业务状态；记录再次使用由当前状态和工作流条件决定，不能加消费类型或本批历史排除。工作流可读写多表、增删记录与字段/列，显式决定业务状态变化。结束节点“保留当前环境”包含保存登录上下文并关联相关数据行，不要求额外 Bind 节点。具体关联范围、冲突和恢复为设计推荐；见 `.ai/decisions/2026-09-12-project-data-workflow-semantics.md` 和 `docs/project-management/design/README.md`。此前冲突建议已 superseded。
- 2026-09-13（confirmed，来源：用户对完整设计稿回复“没问题”并要求里程碑计划）：`906deda` 完整设计作为规划基线，包括已有推荐的空白本地表、单表 XLSX 导出和失败后续快捷入口。当前仍只规划，PM0–PM9覆盖全模块，Studio能力按具体契约衔接；见 `.ai/decisions/2026-09-13-project-management-design-approved.md` 与 `docs/superpowers/plans/2026-09-13-project-management-milestones.md`。
- 2026-09-12（confirmed，来源：用户明确实施指令）：代理模块已从 `codex/proxy-management@0ad2fd2` 选择性接入浏览器主线；全局导航和浏览器启动到代理组的调用仍由后续浏览器任务完成。详见 `docs/migration/proxy-management-status.md`。

- 2026-09-12（confirmed，来源：本轮用户授权及隔离worktree验收）：模型管理在 `codex/model-management` / `../autoflow-model-management` 实现，已通过baseline合并验收；保留旧供应商左栏、三步接入与split编辑，凭据仅写系统存储。验收边界见 `docs/migration/model-management-verification.md`。

- 2026-09-12（confirmed，来源：用户合并指令与隔离合并测试）：模型与代理迁移通过0003_merge_proxy_models汇合；不得改写两边已存在的0002版本。接入浏览器客户端06153ca及代理预算修复4a91407后，304个后端、128个前端测试通过，合并边界见docs/migration/model-management-baseline-merge.md。

- 2026-09-12（confirmed，来源：用户对模型选择、模型列表和设计理念的补充要求）：模型管理进入整体重设计研究，参考成熟产品的任务组织与设计语言；旧布局是现有实现记录，不再限制提出新方案。具体新布局尚为 proposed，见 docs/prototype/model-management/redesign-brief.md。继续先原型与规格、后实施，沿用 shadcn/ui + Tailwind。

- 2026-09-12（confirmed，来源：用户最新范围收缩指令）：上一条整体重设计方向 superseded；用户取消原型和整体 UI 改造，认可现有布局，只调整模型管理首页的模型数量提示位置。重设计简报仅留历史，不继续出图或实施其信息架构。

- 2026-09-12（confirmed，来源：浏览器计划 Task1–10 独立复审及源代码）：浏览器 UI 使用 desktop shared shadcn/Radix + Tailwind、领域组件、RHF/Zod；查询上下文统一 ApiProvider。同一工作区重连保留编辑树，实际换目录才重置。CloakBrowser wrapper 固定0.5.9，只有其内核能力；后端 worker 处理下载与取消，License 使用共享系统凭据存储。最终页面/平台状态见 docs/migration/browser-management-validation.md。

- 2026-09-12（confirmed，来源：授权实网、脱敏 fixture 和 CUA）：ProxyPanel 列表/凭据/到期字段已接通；SOCKS5 检测通过，HTTP CONNECT 实网超时。数据面密码按需取用且不落库，API Key 保留系统存储。旧“列表一律拒绝”的限制 superseded；远程管理写操作仍未实现。见 docs/migration/proxypanel-live-verification.md。

- 2026-09-13（confirmed，来源：用户明确实施PM0计划）：整体里程碑及PM0执行已授权，旧“当前只规划”的阶段描述 superseded。先在codex/project-management-design完成契约、传输、FX-01–07及覆盖账本，逐里程碑用户验收；PM1才交付页面/API。主目录Studio M1在交付前提交为b2e95b3，包含工作流文档CRUD和0005迁移；旧“只有about:blank/全为WIP”的当前事实 superseded，Run仍不可执行。见 `.ai/decisions/2026-09-13-project-management-pm0-authorized.md`。

- 2026-09-13（confirmed，来源：用户PM1实施授权、真实源码与自动/本机Electron验证）：`codex/project-management-pm1`从1f80f97+PM0构建，已实现项目目录/表单/上下文和10项HTTP；pm01_projects从0005派生，两张表原子保存项目与幂等快照。其余业务能力明确notImplemented。统一控件选择性接入1fb58e1，保留最新基线Studio M1与会话桥；没有第二执行器。见PM1执行卡和机器核验。PM1等待用户验收，旧“项目尚无业务实现”的当前描述superseded，PM2+未开始。

- 2026-09-13（superseded，历史用户持续目标；已被后续 PM2 修订计划覆盖）：PM2–PM9曾授权在独立implementation工作区持续实施，旧逐阶段暂停规则superseded；排除画布编辑器，保留真实核心运行依赖。PM2执行卡已建立，业务实现尚未验收。

- 2026-09-13（confirmed，实际源码与独立审查）：PM2基础包已交付typed身份、原子持久结构、XLSX流式适配、表资料API与组件，字段/状态目录进入真实HTTP集成，字段影响确认已有持久事实绑定。完整记录、五页签、文件IPC仍实施中。主线9490924现有正式Studio M2，旧“核心仍全部WIP”现状superseded；实施分支尚未接入，PM3须核对契约与0006/pm02迁移汇合。证据见pm2-review-foundation.md及current-baseline.md。

- 2026-09-13（confirmed，实际源码/独立审查/自动验证）：PM2记录create/get/update/显式状态与字段影响preview/PATCH已由cc86607、3630e78、7a2986f交付；670后端全量及最后类型增量33定向、461前端回归通过。仍无正式数据页面、文件IPC或运行闭环；详见pm2-records-fields-verification.json，不将基础命令等同完整PM2。

- 2026-09-13（confirmed，提交及核验）：PM2服务端记录筛选/排序/分页和16项数据HTTP已交付，字段/状态客户端与状态组件已提交；最后查询连接池清理竞态修复后698后端/490前端全量通过。最新报告pm2-query-editor-verification.json；尚无正式数据页面/Excel IPC/批状态，不得宣布PM2完成。B2主进程/内部通道盘点完成，旧picker直接返path不能照搬。

- 2026-09-13（confirmed，实际代码/独立审查/最终自动验证）：PM2记录客户端、共享命令恢复、四类型值编辑、字段影响编辑、冻结记录草稿与记录表格已提交至737ce3e；最终564前端/86文件通过，typecheck/lint/build及OpenAPI/scripts/structure通过。后端本轮无源码变化，698测试仍指上轮报告。正式数据五页签和文件IPC尚未挂载，PM2不完整；最新pm2-editors-verification.json，继续C2/删除与耐久批状态/B2。状态删除不能物理清除历史FK引用，下一包采用软删除保持历史事实。

- 2026-09-13（confirmed，实际代码与自动/隔离Electron核验）：PM2状态历史墓碑和删除HTTP已交付，head pm02_status_tombstones；正式数据目录与五页签读取已接通。719后端/606前端及本机macOS arm64目录创建/编辑/冲突/重连/重启、已有模块回归通过。旧“正式数据页未挂载”当前结论superseded；记录/字段/状态写UI、批状态、Excel发布仍待C2c/A2h/B2完成，PM2整体未完成。报告pm2-directory-deletions-verification.json；后续共享命令每次原key重发须动态校验scope/只读准入。

- 2026-09-13（confirmed，来源：用户后续批准 PM2 修订实施计划）：当前只实施 PM2，完成后停在 PM2 验收点，不自动进入 PM3。此前连续实施 PM2–PM9 的授权记录已 superseded。原编辑任务六个 WIP 文件仍等待原任务提交；后续接管须依据明确交接。现有组件、后台及目录导入证据不替代详情页完整验收。

- 2026-09-13（confirmed，用户明确交接）：原编辑任务已结束，原六个 WIP 正式由当前任务接管，保留后完成 PM2 集成和验收。此前等待原任务提交的阻塞已解除，PM2 完成后仍不自动进入 PM3。

## PM2 本机完整交付（2026-09-13，confirmed）

来源：pm2-verification.json、四组真实Electron验收。用户确认原编辑任务结束后已完成整合；旧等待记录superseded。记录/字段/状态/表资料编辑、批状态、Excel新建/替换/导出及恢复已接通真实页面。760后端、833前端全量与工程检查通过。编辑命令先持久化再HTTP，稳定工作区身份恢复，旧代次拒绝串写，脏草稿不能静默切代。10000行界面导入4396ms/翻页158ms仅本机单次实测。Windows/x64/打包未执行；原生面板与全流程测试注入范围分开。完成后停PM2验收，不开始PM3；主线Studio迁移分叉仍需后续集成。

2026-09-13最终只读核对主项目HEAD为2b5365e（Studio条件/循环/变量等已继续推进），并有其他任务WIP；此实施分支未合并这些内容。后续主线集成须重新核对实际迁移/共享类型/Studio能力，不把旧M2快照作为现状。数据能力契约最终仅data=available，其余五项未实现；修正提交d05bbe1。

## 项目管理原型对齐复审（2026-09-13，confirmed）

来源：用户指定主项目 gallery.html 要求重新对齐，并明确“导航按照现状，用顶部导航，不要换成侧边”。当前暂停PM3草案的实施推进。PM2功能核验保留，不能将它解释为原型视觉已验收。已确认记录筛选常驻、详情Modal/整页缺失、编辑载体、字段卡片等实际偏差；纠偏建议尚待形成完整对齐规格与确认。旧仓324748a的autoflow-desktop内有自动化四页签/聚合保存/资源解析/项目数据实现与测试代码，应先提取适配，不能因当前工作树删除而判定从未实现。报告见docs/project-management/reviews/2026-09-13-prototype-alignment/README.md；原型112个唯一内容只实际视觉复核20张，本次7张应用截图不是全模块验收。

## 项目管理完整对齐规格（2026-09-13）

来源：`docs/project-management/design-alignment/`及完整prototype-alignment-design规格。confirmed：已看最新阅读集91张和同日候选2张，19历史排除；前轮20图审阅是历史记录，不再代表累计覆盖。顶部全局导航保留；目录卡片、独立记录详情/编辑、字段统一草稿为对齐方向。环境“删除影响预览”原图实际是完成页，不能替代预检。PM2已实现文件/批状态能力保留，字段删除仍未实现；当前外链桥仍需补。

proposed：本轮完整规格尚未确认，6组补图未生成；参数定义归Studio/core、聚合字段提交及其有界回填预算是建议，不得当已批准能力。R1–R3纠偏可独立于参数裁定；R4/PM3须先裁定稳定参数身份/快照/覆盖并同步PM0 DTO。未知操作先查询由已批准PM1/PM2规则明确，本轮只勘误PM0旧文案，不改历史报告。没有新增业务实现或跨平台验证。

## 对齐设计批准与执行计划（2026-09-13，confirmed）

来源：用户“ok没问题，开始设计后续实施计划”及 `.ai/decisions/2026-09-13-project-alignment-design-approved.md`。4688353设计的推荐参数权威和有界聚合回填已确认，旧“待用户确认”当前状态superseded；缺图/业务实现不因此完成。已形成B0+R1/R2/R3三个切片计划，主入口`docs/superpowers/plans/2026-09-13-project-management-alignment-implementation.md`。本轮仅文档；PM3保留工程准入，参数归属不再阻塞用户决策。

## 原始Gallery直接还原（2026-09-13，confirmed）

用户明确只有全局左菜单改现有顶部导航，其他页面布局/交互跟随gallery具体原PNG。B0衍生图不再是视觉依据；“B0视觉通过”等当前交付解释superseded，功能证据仍只适用其原版本。R1视觉重开，R2部分实现且视觉未通过，R3未完成。当前修订计划与边界见 `.ai/decisions/2026-09-13-project-gallery-only-navigation-change.md`。原图索引共112文件，latest91；本轮重新看17图，其余不冒称再次视觉审阅。


### Gallery G0 执行记录（2026-09-13，confirmed）

用户已授权连续执行。共享Frame及页面装配完成；真实表名面包屑、200%页签换行与保存栏可见性修正。run-AatYpG真实隔离应用14项smoke通过，规格与工程问题闭合。这里只验收共用结构，R1目录与查询、R2原表单/详情、R3聚合字段仍需继续；单字段截图及B0历史评分不能证明全页还原。详见docs/project-management/design-alignment/acceptance/gallery-g0/review.md。

### Gallery R1 退出（2026-09-14，confirmed）

来源：acceptance/gallery-r1/machine-report.json、review.md及原PNG并排。a6a0e8e恢复原目录、项目头、同卡片记录表/工具/查询Popover；997前端测试、32后端定向及真实E2E通过，原图逐页至少85且硬结构通过。R1可进入R2，但用户手动/Windows/打包未执行，不能解释为项目管理全部完成。R2继续原003–007全页与确认；R3聚合字段仍待实施，PM3不在授权推进范围。

### Gallery R2 退出（2026-09-14，confirmed）

来源：acceptance/gallery-r2/machine-report.json、review.md、run-msXqcI真实E2E及原003–007。实现a08c2fe，保留真实typed身份/单命令恢复，通栏新增编辑、自有日历、详情左右区、居中未保存/删除确认。127文件1030前端、38后端、29脚本、3结构及PM2回归通过；逐页86/88/89/91/88。原生http/https外链已验证；原生文件面板完整闭环、R3、Windows、打包、用户手测未执行。连续授权允许进入R3，不进入PM3。

### Gallery R3 实现与验收证据（2026-09-14，confirmed）

来源：本实施分支e467035/b2d1543/800fb01、`docs/project-management/design-alignment/acceptance/gallery-r3/`。R3已实现原008/009/100/010/012/014结构、完整字段草稿及原子保存、真实状态引用、来源和设置。853后端/1126前端、33脚本/3结构与工程检查通过；真实120条部分结果修复了仓储已提交但HTTP拒绝details导致500、结果选择数清零的实际问题。最终同版本截图和回归见machine-report，不将历史B0或小测试冒称完整视觉验收。

原生Excel完整链实际操作于build3，文件实现后续未改；最终build6使用独立真实IPC/HTTP/SQLite文件回归并明确E4选择注入。Windows、其他架构、打包版本和用户手测未执行。记录`gallery-delivery.md`作为统一交付入口，R3后停止，PM3未开始。旧“R3仍未实施”的当前描述由本节取代；旧报告自身不改写。

## 行内新增记录侧分支（2026-09-14，confirmed）

来源：侧对话用户选择“行尾连续录入”并授权实施；分支 codex/record-grid-entry，基线 a6a0e8e。正常新增改为同表草稿行及一次有界原子保存，旧编辑和旧 pending 恢复保留。这只变更新增交互，不替代父任务其他页面设计。实现与候选证据位于该独立分支，未合并主线；G4 组合恢复 E2E、原生输入法及独立视觉评分仍待完成。


## 主项目整合：行内新增与 R2/R3（2026-09-14，confirmed 代码范围）

来源：`361d4fd`、`dcb1831` 与主线 `cda081d` 的整合。保留最新 WebRPA Studio 前端及其独立窗口，不恢复已退役的 Studio 后端执行器。正常新增记录使用同表草稿行和批量保存；已有记录继续详情/编辑页面，字段继续 R3 聚合草稿与原子保存。本节替代前述“行内新增尚未合入”“Studio/PM迁移尚未汇合”的当前状态；历史报告保持原样，旧 G4 未验收项目不自动转为通过。

- `bootstrap/project_http_routes.py` 同时供真实应用与无副作用 OpenAPI 导出注册项目路由。
- `0009_merge_project_data` 汇合 `0008_workflow_debug` 与 `pm02_schema_drafts`，不重写历史迁移。
- `app/ApiProvider` 每个工作区维持一个 QueryClient；服务重连按实例隔离查询键并刷新活动查询，避免既有 observer 与新缓存分离，保留本地草稿；工作区变化由 App 的 workspace key 隔离。
- 合并核验见 `docs/project-management/design-alignment/acceptance/main-integration/`；源分支保留。


## PM3 独立分支持久执行契约（2026-09-15，confirmed）

来源：`docs/project-management/implementation/pm3/task3-verification.json`。用户已批准 PM3 计划并多次授权继续，历史“不进入 PM3”不再是当前授权边界。工作区固定 `autoflow-project-management-pm3`，主目录只读。Task 2 当前 WebRPA 文档已提交 ffa8df2；Task 3 PreparedContent/CoreRun/RunEvent 与 0011 迁移完成双审、1193 后端测试及工程检查。有历史证据时禁止有损降级；旧只读快照可查询但不能派发。当前进入 Task 4 真实 CloakBrowser worker；不能将持久契约验收冒称网页执行/前端或整个 PM3 通过。

## PM3 管理功能优先（2026-09-15，confirmed）

来源：用户明确调整执行组织，随后排除 Studio demo 联合测试。保留 Task 2/3 与 Task 4 有效成果；自动化管理后端与组件并行推进，原执行卡更新顺序和责任。Studio transport/画布/bridge 联调暂停，不作为管理验收前置。真实管理页面 E2E、截图以及管理端运行所需幂等/原子性/停止/撤权/恢复不变。先完成 Studio 保存运行 UI 的旧门槛 superseded，历史证据保留；不进入 PM4。

### 2026-09-15 PM3 管理配置优先（confirmed）

用户明确 Studio 是 demo，不做联合测试。管理自动化配置持久化、五项 HTTP 与操作恢复已装配；只读工作流目录来自 WorkflowService，不能当作 Studio 集成。当时 resource/capability 适配未完成；resource 在后续 d28dca7 接入，此旧 resource 结论 superseded，capability 仍未接入，因此不把保存配置展示为运行可用。详见 PM3 原执行卡及 management-backend-verification.json。主项目仍只读。

### 2026-09-15 PM3 管理配置接入（confirmed）

来源：PM3 独立工作区代码、管理 HTTP contract 与 `docs/project-management/implementation/pm3/management-runs/run-eSwQYK/result.json`。

- 用户明确取消 Studio demo 联合测试。管理目录/四页签通过真实工作流 ID 关联；QA 工作流经真实服务准备，不伪造 Studio 保存或运行结果。
- 管理界面在 `renderer/domains/project-automations`；查询按工作区/实例/项目隔离，命令恢复身份按工作区/项目/表单持久保存。参数说明保持可省略，模型选择有省略/null/指定三态。
- 内层筛选/排序草稿必须参与外层 dirty/valid 与 resetKey，不能以应用前的旧查询提交整体配置。业务字段查询仅用已绑定字段；状态与系统排序不依赖绑定。
- 项目内创建成功替换 URL 使用 `preserveGuard:true`，防止未卸载页面失去离开保护；真实工作区替换保持默认清除旧 guard。
- 管理配置保存、工作流结构校验、运行准入为不同事实。此次管理 QA 不代表批次/运行管理已交付；PM4 未开始。

## PM3 参数批次原子启动（2026-09-15，confirmed）

来源：`implementation/pm3/batches/task11-review.md`、实际代码及有界独立审查。Batch、独立Task输入快照、queued CoreRun、PreparedContent及启动Operation在同一调用者Session提交；Task只投影CoreRun。物理COMMIT失败会失效连接，响应丢失仍按原键找回接受结果。此为Task11后端基础包，尚无管理端启动入口；Task12–16继续。Studio demo联调不在本次范围；不进入PM4。

## PM3 管理功能交付（2026-09-15，confirmed）

来源：`docs/project-management/implementation/pm3/verification.json`、当前源码修订 `bdff9dd` 和真实 Electron 证据。前段“尚无管理端入口/Task12–16继续”由本节取代。

- 自动化管理、参数批次、批次与任务目录、持久日志/输出/截图、普通停止、30秒后强停、旧执行代次撤权、原键恢复、重启查询及双工作区隔离已连接真实 FastAPI、SQLite 与 CloakBrowser。
- 强停测试只对隔离 Electron 后代树中唯一且命令匹配的真实 workflow worker 做受控 SIGSTOP；UI 仍执行真实普通停止、宽限、强停和清理。当前HEAD直接证据为 `pm3/qa-runs/uuid-runs-1789458500247/result.json`。
- 项目模块不复制执行器；核心继续拥有 Workflow/PreparedContent/CoreRun/RunEvent/worker。用户排除 Studio demo UI 联调，不把该路径标为通过。
- PM3 当前授权管理范围通过；原完整 PM3 合同仍 partially_verified。项目数据型执行、持久环境、人工、统计和生命周期属于 PM4–PM8，未提前实现。用户手测、Windows、其他架构及打包未执行。

## PM4 A/B/C/F 管理能力交付（2026-09-16，confirmed）

来源：实施分支提交 `11e44be`、`48e5919`、`64606a2`、`f092551`、`1cc5112`、`c911b6a`、`b4dabf28`，以及 `docs/project-management/implementation/pm4/{a,b,c}-verification.md`、`pm4/verification.json`。

- V1/A/B/C 已交付真实管理侧多表输入、原子领取、本地记录/状态/字段 capability 和有限/不限批次调度；记录复用仅看当前业务状态与工作流条件，不保存批内排除集合。
- 原始输入快照保持不可变；Task 已确认写入推进独立游标；人工再次修改后旧版本写冲突。结果不明按原 operation 身份查询，旧 executionGeneration 无权继续写或释放占用。
- 权威 Electron 证据由真实 FastAPI、SQLite、项目数据服务和 UI 构成，但执行步骤由隔离 fake executor 驱动。不得把它写成真实生产执行核心、CloakBrowser 或 Studio 可用。
- PM4 管理功能交付状态为 delivered、验证状态为 partially_verified：当前源码业务 E2E `f-QHALLW` 绑定 `f07bb83b`，完成第二自动化读取、有限/不限管理链、三类候选态及日志搜索 Enter；`f-4QcXFG` 保留前一提交候选的全量工程与 19 张截图审查，旧 `f-dJVKnL` 为历史候选。`d3a397cf`、`f07bb83b` 补齐人工删除和 Excel 重新导入的活动 lease 保护并通过定向回归；当前源码的 19 张截图同视口视觉复审和阶段全量检查均已通过。PM3 管理前端定向回归 16 文件/121 项、管理后端定向回归 139 项已通过；会启动真实 CloakBrowser/生产执行核心的 `qa-project-management-pm3.mjs` 按边界未执行。真实生产执行核心、CloakBrowser、Studio、Windows、其他架构、打包及用户手测未执行。边界固定为“管理侧通过，真实执行核心接入待验收”；不进入 PM5。

## 有效分支归并（2026-09-17，confirmed）

来源：用户要求整理所有未合并分支，并确认只合入有效能力；源码差异审计、能力矩阵、树不变归并检查和最终验证记录见 `docs/migration/branch-integration/`。

- `codex/project-management-pm3@2bac1b14`、`pm4@fbda6f17`、`pm5@fbda6f17` 的有效项目执行能力经 `a5c5ed98` 接入；项目运行表使用 `project_workflow_*` 命名与当前 Studio 运行时并存，迁移由 `0013_merge_project_runtime.py` 汇合。
- Android 分支的设备持久化、生命周期、环境、批量创建、控制台及手动控制已接入。旧分支的工作流分配/接管直接依赖已退役运行时，因此当前接口明确返回不可用错误，不伪造兼容性。
- UI 控件、全局表格与代理管理已完成能力核对；当前更新实现优先，缺失的独立控件被移植，历史分支以树不变归并纳入提交图。
- `codex/m6-unfinished-checkpoint-20260913@59ae8d44` 与 `codex/studio-before-removal-20260913@4eda2074` 保持排除：前者是未完成检查点，后者是退役前快照，二者均不是当前产品能力来源。

## PM9 基线与发行验收（2026-09-20，confirmed）

来源：本次 Git 归并、`docs/project-management/implementation/pm9/verification.json` 与用户平台安排。

- 有效 Studio checkpoint、Android 规划已合入 `codex/architecture-baseline@8e5564e0` 并推送；已退役两个历史快照继续排除。PM9 基于该基线在 `codex/project-management-pm9` 实施。
- 生产源码/打包 HTTP 与 Electron 管理链、万行数据测量通过；后端 3159 passed / 15 skipped、前端 5445 passed、脚本 94 passed；真实 CloakBrowser 四节点/批次/重建测试 8 passed。
- PM9 仍 in_progress；生产项目执行器尚未接入完整图、项目数据节点、End 和人工检查点。已提交 R1–R4 架构规格等待用户确认，不能将管理侧/四节点证据扩写为完整执行通过。
- 用户指定 Windows x64/macOS Intel 使用现有 GitHub Actions，缺少的实机证据明确待验收。本机 arm64 DMG 已构建但无签名、公证或手工安装证据；CI 实际状态见 PM9 报告。

## PM9 生产运行时补交付（2026-09-20，confirmed）

来源：用户 R1–R4 确认、`docs/project-management/implementation/pm9/verification.json`、正式 Studio HTTP/真实 worker/CloakBrowser/打包 Electron。

前节“仅四节点、等待架构确认、生产图/数据/End/人工未接入”已 superseded。工作隔离在 `codex/project-management-pm9-runtime`，基线仍为 `codex/architecture-baseline@8e5564e0`。

- 共享图、固定身份数据 RPC、End 关闭后保存关联、人工存活 owner 延续已接通；worker 消失会撤权并取消人工项，不自动重放。包含循环或人工节点的并行图暂在准备阶段拒绝。
- 本机后端候选 b72938b8 全量 3195 passed / 23 skipped；CI 候选 66a428aa 前端 5455 passed（405 文件）。最新候选另以报告记录。新增平台边界与配置回归另列报告。12 场景真实浏览器包括登录复用、人工继续/终结/超时/停止/重启/进程丢失和旧人工命令重试。
- 打包 Electron 万行记录显示每页 50 条、1004 条真实日志分页；另以 60 秒内 1000 条固定合成日志输入验证实际 HTTP 分页、同步记录翻页与 JS 堆采样（最新本机 d59607f3，60.031 秒生成/读回 1000 条，最大批次延迟 41 ms）。合成输入与 worker 吞吐分别记录，不构成所有硬件或持续负载承诺。
- 同提交三平台 Actions、实网 Sheets、签名/公证/物理安装证据仍以 PM9 报告逐项为准。历史阶段的隔离 QA 证据不自动升级。

2026-09-21（confirmed，来源：Windows Actions 35530376377 原生堆栈与真实持锁 HTTP 回归）：五路并发创建记录触发 `BEGIN IMMEDIATE` 的 SQLite 写竞争，旧 HTTP 错误映射为 500。d59607f3 复用共享竞争判定，返回 503 DATABASE_BUSY / Retry-After: 1；测量脚本仅对该明确响应以原命令身份最多尝试 10 次，其他错误直接失败。生产事务和所有权规则不变。本机新打包的五路单条写入一万行通过，busyRetries=0；三平台候选结果以 verification.json 为准。

2026-09-21 最终候选 d59607f3（confirmed；来源：Actions 35531206432 三个原生 job 全部 success）：Windows 后端 3180 passed / 57 skipped；Intel/ARM 各 3214 passed / 23 skipped；前端各 5455 passed / 405 文件。源码及打包真实执行链、原规模五路万条、固定 1000 条/分钟合成输入、安装包构建及上传全部通过。Windows 万条耗时 725733 ms，发生 1 次明确 503 忙重试且保留原键，最终正好 10000 条；真实 worker 1004 条耗时 112121 ms（537 条/分钟），不能把独立合成输入通过写成 worker 达到千条/分钟。Windows/Intel/ARM 合成 1000 条全部读回，分别 60105/60038/60055 ms，最大批次延迟 143/181/202 ms。实网 Sheets、物理安装/原生专项、签名公证和历史完整规格余项仍待验收，releaseAccepted=false。

2026-09-21 PM9 后续（confirmed；来源：follow-through.json 与 Actions 35560163432）：新增候选 52936b6a 修复人工继续/到期 CAS 两种交错、通用操作账本环境 DTO 500、已关闭候选保存失败与占用恢复。251 条覆盖映射/73 个失效预定路径已核对；203 条有实际断言、48 条无直接场景，186 partial/65 planned/0 verified。18 本机真实浏览器场景、最终占用 30 定向与旧候选真实链通过。ARM 新 CI 全通过且该 DMG 在本机隔离复制启动通过；当前其他平台状态以 verification/follow-through 为准，旧 d596 三平台不代表新代码验证。四项新增运行能力已补规格/文件级计划并经复审，仍 awaiting confirmation。历史 PM6 服务账号 Sheets 实网和凭据证据有效；缺当前 PM9 打包完整链与 OAuth 等专项。releaseAccepted=false。

2026-09-21 后续校正（confirmed，取代上段计数/能力分类）：当前 204 条有断言、47 条无直接场景，187 partial/64 planned/0 verified。52936b6a Windows 与 ARM CI 全通过，Intel 首次前端等待失败、原 SHA 第二次运行进行中。ARM 包串行字段/新增行/修改/状态链通过，但 dispatcher 与 worker 单 owner/capacity=1、资源保护锁也不支持多 Run；FLOW-A02/DATA-E2E-06 并发为 implementation_missing。独立补充方案 2026-09-21-pm9-multi-run-capacity.md 已提交单独确认；未修改安全锁或开放并发。最新平台结果仍以 verification.json 为准。

2026-09-21 最新校正（confirmed，来源 input-environment-follow-through.json）：XE-A23 真实包链暴露输入环境启动仍要求默认 Profile，修复为实际领取事务冻结所选环境 Profile、忽略无关默认配置、解析失败不创建 Task/lease。54 定向、ruff/mypy/OpenAPI、100 脚本、PyInstaller 和完整真实人员/邮箱/账号恢复链通过，独立复审无 P1/P2。人员预先关联另一环境且全程关联/数据版本不变；邮箱原筛选不再创建 Task，新账号仅一条。当前 204 有断言/47 无直接场景，188 partial/63 planned/0 verified。新增生产改动需要新三平台矩阵；52936b6a Windows/ARM 成功保留，Intel attempt 2 因新候选取消。S1–S5 架构仍待确认，releaseAccepted=false。

2026-09-22 PM9 最新状态（confirmed；来源 shared-data-follow-through.json、shared-data-final-review.json、coverage-audit.json）：上文 S1–S5/共享 C1–C4/R1–R5 待确认或实施中的状态已由用户批准与后续实现 supersede。全部授权切片已接通；S4 仅安全新文件/Job 所有权子集，既有文件覆盖/追加/读取仍拒绝。一次整批 C/R 审查 3 Important 已 RED→GREEN 修复，0 Critical/Minor；本机完整后端 3440/67、前端 5469/409 通过。后续仅测试/证据改变，当前生产源码 3c02b51f；原生 CI d75297fb 的 Intel 继续，Windows/ARM 修正测试后以 0d7524d9 补跑，结果以 verification.json 为准。235 有范围断言/16 未定位/198 partial/53 planned/0 verified；D1 普通来源业务格式错误保留与诊断已获批准并实现：安全来源 Scalar 在 Sheets/XLSX 保留原值并派生 validationIssues，身份、人工写入和 unsafe wire Scalar 仍严格；当前候选 5d1f4608，三平台 Actions 35638303073 待完成，真实 worker/打包完整链/实网授权/实机安装仍待验收。M1–M3 未批准；Google 当前授权/打包完整链、签名与三平台实机专项仍外部条件，PM6 历史实网证据有效。releaseAccepted=false，不合并或发布。
