# PM9 生产运行时实施卡

2026-09-24 End结果恢复收口（confirmed本机完整回归/新包，三平台in_progress）：生产ee2524af以现有账本恢复原End/child保存ID、原目标与当前关联阶段，明确替换授权、累计冲突版本，父结果未落定或读取未知时也不允许重复保存。25后端/14前端定向及两项P2的RED→GREEN/独立复审通过；最终后端3506 passed/90 skipped/2依赖警告（741.38秒）、前端5481 passed/409文件（180.77秒）、103脚本、Ruff/mypy408、类型/lint/OpenAPI、4映射/251引用通过。显式build后未签名ARM完整桌面26截图通过并目视核对End修复/刷新：真实输入环境g1/session1→End更新同环境g2/session9→第三Task恢复，新关联修复不重跑/不重复保存/不改失败历史；Profile未改，不解决I1–I3。首次旧前端打包失败、中断回归和夹具错误均保留。新三平台push35935288512@d19d120e运行中，同仓库draft PR重复矩阵跳过；dispatch401仍在。251为212partial/39planned/0verified，249有断言/2未定位，73缺预定路径有子范围映射，重叠缺口241生产/19实现/8测试/24外部不变；releaseAccepted=false。见end-link-repair-follow-through.json。

2026-09-24 DATA-E2E-03人工版本/部分失败联合补证（confirmed本机源码子范围）：FX-04初始业务夹具7/3/2，真实TCP HTTP/SQLite/worker/CloakBrowser两链分别证明任务写内容7→8、状态3→4和游标8/4/2，以及人工窗口PATCH到内容8后旧字段/旧内容状态写均REVISION_CONFLICT、游标仍7/3/2且原输入不变；声明人工分支继续不吸收人工新值。两链先前createRecord均保留，后续真实缺失元素超时失败后完整记录快照不变，公开写入摘要只含成功提交，End未执行，两条lease/目录/容量回收。最终2 passed/24.56秒，相关15 passed/4.36秒，Ruff通过；首轮三操作合并grant被422拒绝，修正为各节点精确授权，未改生产。CI选择collect2/53非执行，fresh CLI401；打包UI/Sheets出站联合/新三平台仍待验。仅E2E-03 planned→partial，WRITE-05/08/09补映射；251为210partial/41planned/0verified、249有断言/2未定位，缺口241生产/19实现/8测试/24外部不变。生产仍a7059dc6，不重跑无变化全量/构建；releaseAccepted=false。见manual-write-conflict-follow-through.json。

2026-09-24 DATA-CLAIM-14不限领取补证（confirmed本机源码子范围）：保存默认上限1、公开启动maxTasks=null，单一最终态A01由真实TCP HTTP/SQLite/worker/CloakBrowser连续成功5Task，第6Task人工等待时公开停止为cancelled；六次同RecordRef/内容版本1/状态版本2，完整原记录不变，每次只持有本Run一条lease，最终6条全部释放。原停止命令查询/重放一致，停止后三轮真实调度无新增Task，工作目录/容量清空。真实1 passed/28.11秒，相关50 passed/26.99秒，Ruff通过；保存策略null和时间格式比较的夹具错误保留，不称产品修复。CI两处选择已包含新用例，collect1/51不是执行；fresh CLI401，新三平台/打包UI说明与停止验收保留。生产仍a7059dc6，不重复无改动全量/构建。251仍209partial/42planned/0verified，249有断言/2未定位及241生产/19实现/8测试/24外部缺口不变；releaseAccepted=false。见unlimited-reclaim-follow-through.json。

2026-09-24 DATA-E2E-01/CLAIM-12真实Excel链补证（confirmed本机源码子范围）：正式文件选择授权→TCP HTTP inspect/import将FX-01三表导入且初始状态null；显式初始化后，真实worker三Task依次处理W01/W02/W03、A01保持可用、只读查询D01并把组合值写入/读回网页；第二批按已完成筛选且不写状态，连续三Task重复W01/A01。每次只持有本Task两条lease，前Task已释放，D从无lease；每批6条最终释放，W状态版本2→3且内容/关联版本不变，A/D完整快照及原Excel hash不变。最终真实场景1 passed/51.11秒，相关67 passed/2依赖警告/72.23秒，Ruff通过；保留代理502和inspect预期状态码夹具修正。生产源码仍a7059dc6，复用其完整3505/86/2及ARM24图原范围，不重跑无改动全量/构建。仅E2E-01 planned→partial，CLAIM-12补实际映射；251合计209partial/42planned/0verified、249有断言/2未定位，缺口241生产/19实现/8测试/24外部不变。新三平台及打包/原生导入界面验收仍待补，CLI401；releaseAccepted=false。见excel-multi-input-follow-through.json。

2026-09-24 DATA-CLAIM-03启动失败修复（confirmed本机源码/新包回归子范围）：a7059dc6修正真实子进程finished/failed在ready前被误判interrupted；只接受启动前失败/取消，保留身份、清理、退出与所有权检查。真实2场景证明失败占名额、非空状态/值/版本不变、释放后同记录可再取及同键无重复；8项协议反向/终态检查通过，相关81 passed/3 skipped。最终完整后端3505 passed, 86 skipped, 2 warnings in 911.71s，Ruff/mypy408、4映射/251引用、后端构建与未签名ARM完整桌面passed/24截图；清理界面已目视复核。前端未变，保留7b896163的5475/409原范围。仅DATA-CLAIM-03 planned→partial，合计208partial/43planned/0verified、249有断言/2未定位，缺口241生产/19实现/8测试/24外部不变。CLI401仍阻断当前新矩阵，打包启动失败UI与系统性资源故障受阻组合待补；releaseAccepted=false。见startup-failure-follow-through.json。

已执行切片 DATA-CLAIM-14（本机源码通过，见顶部专项报告）：仅A01必要输入，显式置完成状态后按最终态筛选，maxTasks=null且流程不再写状态；通过真实worker至少连续成功5Task，再公开停止批次。核对原停止命令恢复、停止后任务数稳定、原输入/状态不变和lease/进程回收；复用已批准输入/停止契约、TCP HTTP和现有本地表服务夹具；Excel来源由独立前一切片验证。DATA-E2E-01本机源码切片已执行，打包与跨平台证据继续保留缺口。

已执行切片 DATA-E2E-03（本机源码通过，见顶部专项）：先核对已有人工反向冲突与部分失败断言，再用同一真实worker串联任务自身版本推进、人工新值冲突、后续节点失败后已成功修改仍保留；只补缺失联合条件，不批量升级状态。

当前End切片：ee2524af实现持久结果恢复、原目标与显式授权、累计冲突版本和禁止重复保存；DATA-E2E-02/XE-C10/XE-C18已补实际断言，最终本机全量/审查后打包与d19d120e三平台结果继续收集。旧独立断言与审查前包的通过均保留原范围，持久身份I1–I3未改变。

DATA-E2E-05本机子切片已完成（2026-09-24）：按现有契约完成pending/unknown归档→后端重启→恢复→显式处置→换源联合测试。实际复用TestClient生产ASGI HTTP、SQLite、受控Google传输/凭据及真实CloakBrowser worker，未采用原拟TCP服务测试夹具；不把ASGI调用说成TCP/Electron或实网。5项归档联合及52项同步恢复通过，原任务/意图不重投、旧epoch不写新源、新generation不继承状态/环境、历史事实保留。证据joint-external-acceptance.json，DATA-E2E-05仅partial。

后续按用户顺序执行：1）当前打包实网，已有脚本新增--executable/--output-dir，取得授权服务账号/测试表后执行原读写及凭据删除链；OAuth、UUID/增列和完整业务联合链分别补证。2）签名/公证：取得Apple Developer ID+公证授权、Windows签名服务/证书资源后，使用现有electron-builder签名配置构建并验签；不得将ad-hoc或关闭安全策略当通过。3）实机：本机ARM当前DMG校验/隔离安装/健康/父退出已通过；Finder、启用Gatekeeper下启动、原生专项/卸载补验；Windows/Intel待连接入口。无需重复询问已授权范围；仅缺外部资源时保留待验收，持续完成可执行项。

日期：2026-09-20；状态：in_progress；来源：用户明确确认 R1–R4 规格。规格：`../specs/2026-09-20-pm9-production-runtime-integration.md`。基点 `88d812a2`。

### Task 1: 共享图调度与历史浏览器行为

保留项目 Run/Task、冻结内容和确认事件协议；worker 使用 WorkflowRuntime。验证分支、节点访问身份、提交失败阻止副作用、停止与真实浏览器八场景。预期全部通过，原 chain/v1 可直接执行。

Ruling: 实际对照发现 Studio 同名输入节点会覆盖文本，且变量解析不接受 UUID。项目注册器复用现有四节点动作（不复制实现），由共享 Runtime 统一图调度，保持已保存内容的追加和 UUID 参数语义。未来若统一动作语义须另做文档版本迁移，不静默改变历史运行。

### Task 2: 项目数据能力与图准备

开放已装配控制流和项目节点；冻结完整图。worker JSONL 请求携带访问身份和稳定 commandId，父进程从 Run/Task 事实获取权限并调用现有 capability 服务；不信任 worker 自报项目或代次。测试跨项目拒绝、旧代次拒绝、未提交访问拒绝、重复命令只写一次与真实进程闭环。组件先实现后接入 Studio。

### Task 3: End、人工与环境

复用环境实例、End ledger 与人工命令；确认关闭后保存并关联，失败保持真实待核验状态。持久检查点不重放已完成动作。验证登录保持、人工恢复/终止/超时/重启和旧代次撤权。

### Task 4: 发行验证

源码及打包真实链、三平台 CI、容量和失败后续/统计/生命周期核验。真实 Sheets 与缺少的实机证据保留待验收；完整工程检查和整分支独立审查后更新 PM9 覆盖，禁止冒称未运行项完成。

## 执行账本

- R1 适配器新增三个回归先失败后通过；原 worker 单元/图适配 20 项通过，真实 CloakBrowser 8 项通过（45.25 秒）。ruff 通过，mypy 393 文件通过；打包验证随最终 worker 协议一起执行。
- 预检：R2 消费 R1 的 nodeVisitId 及事件提交确认；R3 消费 R2 的固定请求身份与父进程权限检查；R4 消费所有切片最终同一版本产物。不得在 RPC 中绕开事件确认或新建第二套数据库状态。

- R2 数据/图切片：父进程固定能力路由、冻结表授权、访问提交确认、稳定命令身份、graph/v2 与旧 chain/v1 兼容已接通；真实浏览器多表条件写入通过（2 个 Task、2 条结果，18.82 秒）。目标后端和变量差分 130 项、前端配置/范围/注册/往返 459 项通过；类型与 lint 通过。
- R2 Ruling: 使用已有 `test_project_batch_real_cloakbrowser.py` 增加真实多表场景，复用实际 bootstrap/HTTP/进程/浏览器夹具，不复制另一个完整测试脚手架。自定义模块与其他尚未接入项目端口的节点仍在准备阶段拒绝；不得仅扩目录使其假装可执行。
- 协作隔离：发现 Studio 任务同目录写入后，将 23 个 PM9 工作文件逐一校验迁入 `/Users/zhangtiancheng/.codex/worktrees/pm9-runtime/autoflow`，分支 `codex/project-management-pm9-runtime`，基点 `31bfbb51`；原检出只清除了内容校验一致的本任务改动。

- R3 实现：正式 project_end/project_manual 节点与配置面板接通；End 先关闭再保存/关联，保留不完整结果；人工命令先持久接收，再由原 worker 继续或确认关闭后终结。真实继续/终结/超时 3 项通过（32.89 秒），等待期间停止/服务重启 2 项通过（18.40 秒）。共享调度定向 87 项通过。
- R3 Ruling: 人工检查点保存版本、节点访问和不可变内容身份，采用同一存活 worker 的挂起延续；进程消失后拒绝恢复并标记 interrupted，绝不自动重放。当前不支持跨进程重建浏览器页面/图栈，也不接受未声明的人工输入或任意跳转。代价是中断后须通过失败后续重新创建任务，而不能直接继续旧浏览器。
- R3 Ruling: 同一存活 owner 使用 waiting_manual → running，保持 executionGeneration；原 resume_queued → running 仍表示新派发并增加代次。自动预算暂停，人工期限取节点配置与冻结批次上限的较小值。若未来增加新进程检查点恢复，必须走新代次派发，不能复用此入口。
- R3 修复了旧 End 无保留分支的 accepted → completed 非法跳转，改为预检/确认关闭后完成；真实人工终结先失败后通过。
- R4 发现并修复 Studio 平铺文档与项目旧封装读取不通：读取时转换、保留原文档/布局/版本，权限清单使用同一转换；正式 Studio HTTP 保存 → 真实多表/登录保存复用先失败后通过（15.81 秒）。不改写已有工作流或运行历史。
- R4 源码和 PyInstaller 产物现已通过同一正式 HTTP/worker/真实浏览器链：UUID 参数、多表条件写入、人工继续、End 保存关联、第二自动化读回登录。尚待最终同提交三平台 CI、工程回归和整分支独立审查。
- 最终独立审查发现 4 个 P1、3 个 P2。修复人工终结停止循环、循环整体完成后才汇合、人工 RPC 同时监控 worker 退出并在撤权后取消人工项、字段预览使用 modifyField 权限、按人工项定位历史检查点、浏览器动作使用共享嵌套变量解析。新增定向回归 90 项通过；真实 worker 日志 1004 条、6 页、31.350 秒，约 1922 条/分钟（单次吞吐测量，不代表 UI 内存或持续压测）。
- R4 Ruling: 项目图暂拒绝包含循环或人工节点的并行根/同路由扇出，因为共享 Runtime 的 loop_stack/控制标志尚未按分支隔离。串行循环、嵌套循环、互斥条件及不含循环/人工的普通并行图仍支持；代价是这类并行循环须拆为独立自动化，不能宣称任意完整图并发均已支持。未来只在共享调度器完成分支隔离并验证副作用次数后解除准入限制。
- 三平台 CI 回归补充：Framework Python 的 `sys.executable` 指向启动器，原生进程路径却是 `Python.app`，导致崩溃后的 worker/子进程未被重新识别。两处既有进程适配器改为同时比较当前进程的原生可执行文件，仍先验证运行目录标记；双适配器回归先失败后通过，并用本机 Framework Python 3.13 真实孤儿进程核验退出 -15 后才移除目录。定向 80 项通过，UTC 环境的概览/冻结行为 40 项通过；冻结结果解析沿用已有末行 JSON 方式，概览测试显式指定所断言时区。
- Windows 候选已通过 PM9 源码、打包 sidecar、万条记录桌面负载及安装包生成，随后暴露 schema CLI 的 cp1252 中文输出失败；改为标准 JSON ASCII 转义，强制 ASCII 输出回归先失败后通过，生成客户端不变。回收测试显式模拟 POSIX 分支，并独立验证 Windows 缺少原生所有权时保留目录；12 项回归和 ruff 通过。CI 把 OpenAPI、lint/type、后端与前端全量测试放到耗时打包前，失败不再等整个产物链结束才暴露。
- Windows 类型检查实际报出 6 个平台适配器中的 29 个 POSIX API 错误。把既有 Windows 锁分支改为类型检查器可识别的 `sys.platform`，给 POSIX 私有文件操作、进程组与 macOS 窗口入口显式拒绝 Windows，未用空标志替代安全选项；Windows 孤儿目录缺少原生所有权仍拒绝清理。`mypy --platform win32 src` 与本机 `mypy src` 均通过 396 文件；相关文件/进程/Android 回归 57 项通过。
- Windows pytest 收集实际因 UTF-8 JSON 夹具按 cp1252 读取而中断。所有同类 JSON 夹具显式 UTF-8，冻结源码对照的 Python 子进程使用 `-X utf8` 且父进程显式 UTF-8 编解码；1021 项对照/契约回归通过。POSIX 原生文件输出的 25 个参数化场景只在支持平台执行，Windows 拒绝行为仍独立测试；纯进程组模型显式提供 POSIX 能力，相关 42 项回归通过。这些跳过表示平台能力未开放，不是 Windows 原生输出验收通过。

- 存活探测审计发现 Windows 的 `os.kill(pid, 0)` 实际会调用 TerminateProcess，不能沿用 POSIX 的只读语义（[Python 官方定义](https://docs.python.org/3.11/library/os.html#os.kill)）。共享适配器改用仅 SYNCHRONIZE 权限的 OpenProcess + [WaitForSingleObject](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject)，仅明确退出/无此 PID 才返回不存活，权限拒绝与未知状态保留；项目与 Android 探测复用此入口。回归先失败后通过，54 项进程/回收测试及双平台 mypy 通过；真实子进程验证探测不杀死进程，退出后能识别。崩溃夹具使用生产 Windows Job，引入 Windows 原生定向前置检查以缩短失败反馈。
- Intel 全量后端候选 `fd5c1058` 只有浏览器崩溃释放槽位测试超时（3195 passed / 23 skipped）。该测试等待 1 秒短于生产清理允许窗口，同步等待调整为 5 秒，未改变生产超时；本机对应 3 项通过。Apple Silicon 同候选整个 CI 已成功。

- 2026-09-21：Windows 原生前置检查在候选 311d2889 报出 4 个测试模型问题：POSIX 假进程未限定平台、命令夹具 stdin 非 UTF-8、Windows 退出码断言使用 POSIX 信号值、回收模型仍调用真实平台信号函数。修正夹具后本机同组 57 项通过；原生结果等待下一候选 CI。两个浏览器清理入口和内核 worker 同步处理 TerminateProcess 与退出观察器的竞争，只有有界等待确认退出后才释放；6 个回归先失败后通过，相关 86 项通过，双平台 mypy 396 文件通过。
- 桌面负载后等待环境路由稳定，并观察原生 zoom 达到 2 后才检查溢出/截图，复位也等待实际生效；本机打包桌面管理、200% 缩放及重启检查通过。旧打包运行链失败时，事件补读的 409 曾遮住原始 Task 失败，脚本现在保留原始失败和补读错误，仍使验收失败；最新运行链继续验证。

- 2026-09-21：Windows 候选 2c7f4441 原生进程前置检查已通过（55 passed / 2 skipped）。旧候选 303c7b90 全量在取消时返回 224 failed / 2070 passed / 51 skipped，不能作为验收；203 个失败集中于覆盖全部环境变量的冻结源码子进程。对照夹具沿用已有 `os.environ` 继承方式，仅覆盖 PYTHONPATH，保留 Windows SystemRoot（[Python subprocess 文档](https://docs.python.org/3.11/library/subprocess.html)）。959 项源码对照通过；内核测试的并发判定改为同时进入停止的屏障，31 项重跑通过。
- Windows 文件失败修复：XLSX 使用可写文件句柄执行 fsync；运行目录产物和 XLSX 共用不覆盖的文件提交入口，Windows 使用 [MoveFileExW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw) WRITE_THROUGH，POSIX 保留硬链接与目录 fsync。保持文件先刷盘、证据先持久、禁止覆盖和失败清理；没有放开任意路径工作流文件输出。114 项文件/生命周期/worker 回归通过，双平台 mypy 397 文件通过。
- 删除失败测试用明确的 PermissionError 替代 chmod，保留跨重启残留与查询断言；worker 清理失败注入点改到两平台共用的 owned-cleanup 边界。新增 3 个 POSIX 原生工作流输出场景在 Windows 明确跳过，对应 501 拒绝测试继续执行。CI 原生前置检查包含已暴露边界，全量遇到 20 个失败即退出失败，只有零失败跑完整套才算通过。

- 候选 6b20d5ac 的 Windows 前置检查已执行 88 passed / 27 skipped，文件提交与重启恢复的实际测试通过，但一个旧提交失败注入点未更新，随后 EOF 夹具阻塞；该轮取消，不能算通过。提交丢响应改为注入共用文件提交入口；EOF 夹具发出半条消息后真正退出，并给测试加 5 秒外层等待，仍断言事件不提交、动作不执行。本机对应 25 项通过。CI 前置检查显示逐项名称，10 分钟上限将未结束的等待报告为失败。

- Windows 候选 0f883cb1 已跑完整后端：3172 passed / 57 skipped / 6 failed，1202.73 秒；失败均为测试平台契约。Android 探测模型改为注入共用只读探测入口并断言不发送任何信号；内核路径比较使用原生 Path 字符串。两个工作流导出用例在 Windows 仍执行，明确验证拒绝、无已注册产物和无输出文件；表流程导出前五步及读取数值继续断言。41 项相关回归通过，纳入 Windows 前置检查。此候选 ARM 前后端全量及打包运行/容量检查已通过，最终结果以最后候选报告为准。

- 2026-09-21：补齐 PM9-B 固定速率输入，复用既有运行事件仓库，仅在 smoke 创建的临时工作区对成功任务生成合成日志；无新增生产 API。60 秒计划写入 1000 条，同时通过实际 HTTP 分页读回并操作万行记录页、采样 GC 后 JS 堆。本机打包应用完整链通过：1000 条全部读回，60032 ms，最大批次延迟 38 ms；此证据不代表 worker 吞吐或长时间无泄漏。脚本测试 95 项、lint/typecheck 和 Python lint 通过。
- Intel 候选 0f883cb1 后端全量 3212 passed / 23 skipped；前端 5454 passed / 1 failed，失败在记录初次加载的 role 查询等待，尚未进入代次替换操作。测试沿用相邻用例先等待记录文本再查询按钮，避免全 DOM role 查询占用异步加载窗口；未修改生产代码或放宽超时，记录页 50 项通过。

- 候选 95597237 ARM 整个 CI 成功（后端 3212 passed / 23 skipped，前端 5455 passed，arm64 DMG）；Windows 后端完整 3178 passed / 57 skipped，前端 5451 passed / 4 failed，三处为硬编码 POSIX 路径，改用原生 join/dirname；四页签交互测试超过默认 5 秒，单用例给 15 秒预算，不将此交互契约测试当作性能 SLO。Intel 后端 3211 passed / 23 skipped / 1 failed，内核夹具未在 5 秒内启动；启动准备等待改为 20 秒，原服务关闭 3/8 秒断言保持。相关桌面 16 项、关闭 5 项及 lint 通过，Windows 桌面平台检查前置。未修改生产代码。

- 候选 d2ab2bcb：ARM 全部成功；Windows 后端 3178 passed / 57 skipped、前端 5455 passed，源码及打包真实运行链通过，但桌面万行准备的五路单行写入收到 INTERNAL_ERROR，原故障日志随临时目录移除，不能确认根因。万行前置数据改用既有 100 行原子批量 HTTP 入口；不是并发问题已修复的声明。另将五路单行 1000 条真实 HTTP 回归加入源码/打包管理链并前置 CI，保留失败且等待所有在途写入结束。桌面失败保留截断日志并移除 ready 元数据、替换当前服务 token；新增脱敏检查。
- Intel d2ab2bcb 后端 3212 passed / 23 skipped，前端 5454 passed / 1 failed；唯一失败是同一用例 17 次选择操作超过 Vitest 默认 5 秒。此前 Windows 四页签用例为同类问题，统一功能测试默认预算为 15 秒，移除单用例重复配置；显式业务耗时断言和逐用例预算不变。两个相关文件 17 项通过。
- 本机批量准备及固定输入打包链通过：万行准备 4997 ms（测量方式已改变，不能作为生产性能提升对比），1000 条合成日志写入/读回 60028 ms，最大批次延迟 59 ms。独立五路 HTTP 写入 1000 条及重启/生命周期通过；Windows 原始 500 仍需新 CI 独立回归和错误证据定位，不以本机通过代替。

- 验证范围修正：批量准备仅作对照，不用于关闭 d2ab2bcb 的五路万条写入 500。正式桌面容量入口保留运行后五路万条原规模，复用源码/打包 HTTP 的并发回归实现，并在失败时等待全部在途请求完成后保存脱敏日志。1000 条前置检查已在 Windows 候选 94437044 通过，但不据此升级原规模结果。本机完整五路万条、真实运行和固定日志输入通过，最终原规模 Windows 结果仍以新候选 CI 为准。

- 原生 Windows 候选 7aacd53f 的前置 HTTP 回归复现并拿到完整堆栈：`project_data_records.py:64` 的 `BEGIN IMMEDIATE` 报 `sqlite3.OperationalError: database is locked`，被转换成不透明 500。真实持锁 HTTP 回归先得到 500 后修为 503 DATABASE_BUSY / Retry-After 1；释放锁后原幂等键创建及重放仅一条记录，其他数据库错误仍是安全的 500。共享 SQLite 分类由原 Runtime 移至 session 工具，原四处调用保持行为；HTTP 错误契约与生成类型同步。
- 并发 smoke 仅对明确 503 DATABASE_BUSY 退避，每行始终使用原命令键，最多 10 次；记录实际 busyRetries，其余错误不重试。原规模五路万条保留。相关后端 70 项、脚本 97 项、双平台 mypy 397 文件、ruff/lint/typecheck/OpenAPI 均通过；新冻结后端和打包桌面的真实运行、五路万条写入与固定日志负载已通过（1000 条 / 60031 ms，最大批次延迟 41 ms）。Windows 修复结果等待下一候选，不把修复前的成功平台报告套用到新代码。

2026-09-21 最终候选 d59607f3（confirmed；来源：Actions 35531206432 三个原生 job 全部 success）：Windows 后端 3180 passed / 57 skipped；Intel/ARM 各 3214 passed / 23 skipped；前端各 5455 passed / 405 文件。源码及打包真实执行链、原规模五路万条、固定 1000 条/分钟合成输入、安装包构建及上传全部通过。Windows 万条耗时 725733 ms，发生 1 次明确 503 忙重试且保留原键，最终正好 10000 条；真实 worker 1004 条耗时 112121 ms（537 条/分钟），不能把独立合成输入通过写成 worker 达到千条/分钟。Windows/Intel/ARM 合成 1000 条全部读回，分别 60105/60038/60055 ms，最大批次延迟 143/181/202 ms。实网 Sheets、物理安装/原生专项、签名公证和历史完整规格余项仍待验收，releaseAccepted=false。
