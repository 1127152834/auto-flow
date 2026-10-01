# M0 实施记录

日期：2026-09-30；状态：in_progress。来源：持续实施授权、r2规格与计划；从文档提交547a0785建立受管worktree，分支codex/remediation-m0。

Task 1 已实现：真实SQLite领取基准、统一数值报告与必填manifest、默认排除benchmark/golden。复用现有项目/表测试工厂；合成行使用确定UUID排序，计时仅覆盖真实select_required。报告记录代码提交、工作树是否有未提交变更、硬件/运行时/场景维度；未知或脏源码报告只供观察，不比较提升。

验证：RED先因新增模块缺失失败；sourceDirty反例先失败再通过。定向12项通过；现有输入选择10项通过，默认命令同时排除11个当时已有基准用例。Ruff检查/格式通过。2000行一次本机观察：记录键141.677ms，字段164.630ms；不是收益结论，正式对照需提交后干净源码重跑及同口径多样本。原计划默认仅跑全被排除目录会退出5，使用既有输入选择测试一起运行以验证排除行为，未把无测试当通过。

范围：本片无生产实现修改、无前端契约变化；未执行全应用回归、浏览器或跨平台验收。M0仍待Task2–10；Task11历史清理不在本轮授权内。进度细节在本计划忽略目录的progress.md；提交和本记录是持久来源。

Task 2 已实现：G4无浏览器执行基准，按实际成功nodeAttempt核对每个循环体节点次数，不用计划次数冒充实际执行。空流程反例、零次输入、真实50×5节点测试通过；全部基准15项通过，Ruff通过。默认1000×5实际5000节点，本机单次0.227ms/节点、5.001事件/节点。该次源码尚有未提交改动，manifest明确不可用于提升比较。

Task 3 已实现：每条日志通过真实SqlAlchemyWorkflowRuntimeRepository.append_event独立事务提交，计时后新Session核对实际持久条数。RED2缺模块→GREEN2，累计17项通过；Ruff通过。默认1000条本机观察p50=1.238ms、p99=1.854ms；非跨平台结论，也未改SQLite配置。

Task 4 已实现：50ms心跳、100ms告警、真实5分钟样本窗口/有界缓存与只读快照；接入sidecar启动/最终关闭，不新增HTTP契约。RED缺模块、RED缺app.state后实现；单元+生命周期+既有settings_dashboard共16 passed/1依赖弃用警告（anyio BlockingPortal），Ruff全src通过，mypy547源文件通过（1条既有annotation-unchecked提示）。首次异常关闭注入在前置shutdown直接抛错，跳过其他服务清理而挂起，7项后人工终止；改为既有gather内服务完成真实清理后抛错，验证监测器仍关闭，未声称修复原先全应用异常关闭链。

Task 5 已实现：仅loopback随机端口的黄金站点、五字段、首次延迟/永久404/提交丢响应、线程安全命中与提交计数。普通CI运行3项HTTP测试通过（RED缺模块→GREEN3），Ruff通过。按规格保留表单查询参数并支持lose=1，同时兼容lose-名字；关闭站点用Event提前结束故障等待，预期客户端断线不输出服务端堆栈。真实浏览器完整链仍待Task6，不把站点测试记成G2/G3通过。

Task 6 进行中（尚未完成）：指标与完整身份覆盖反例5项通过，涵盖同一行30次失败不可算30成功行、空错误不可算原因、成功需输出核验且去重、typed key/代次身份区别、缺行/重复/未终态与零耗时拒绝。golden/conftest.py显式注册现有real_cloak_page。harness目前仅指标部分，真实HTTP/SQLite/worker编排与G2/G3尚未接入，故不标该Task或AC0-05通过。

Task 7 已实现（Task6长运行期间独立推进）：四项文本守门、按键身份防替换绕过、独立回退反例，8项通过。双引号反例RED后扩展扫描，两种引号一致；真实基线127/2008/81/3247，原80漏算DataTableDetailPage.tsx的双引号phosphor导入。指定七个错误/重试债务键保留。全量脚本首次因新工作树缺依赖/冻结reference失败；复用本机node_modules及已核对5ccb900e的reference后119项通过。没有安装新依赖或改动原目录。

Task 8 本地配置完成，远端验证未执行：checks增加守门、离线基准与报告上传；独立golden workflow支持手动/每晚触发、固定真实内核、数值/manifest/逐行证据上传。YAML实际解析及原触发规则+守门9项通过。依据30行黄金203秒实测，将夜间默认改为各101行（推算万行受控批次存在超时风险，未宣称测过万行）；不改M2B原生吞吐目标。未推送或触发远端CI，AC0-07仍待验证。

Task9文档已加入整改硬性规则、目录职责及实际观察表；表明确sourceDirty/并行测量不可作收益基线、CI未执行，未填写计划预期。结构4项通过。Task6定向汇总41 passed/3 deselected/1既有anyio警告；Ruff全后端通过、mypy547通过（既有annotation-unchecked提示）。101行G2已完成99成功/2预期失败，G3和全后端回归仍运行。

Task6真实harness已接通并完成30行验证（202.69s，2 passed/1 strict xfailed/8 deselected）：公开自动化创建后保存其自有工作流，open_page显式profile；真实TCP/SQLite/worker/内核、分页选行、单任务批次并发2、等待任务终态与清理、逐行输出/站点回执核验、manifest及rows证据。初始fixture沿用旧workflowId创建契约触发422，修正为当前API；2秒open超时发生于浏览器初始化，修正15秒仍小于20秒故障延迟。3行冒烟2通过/1预期失败；未配内核3跳过只证明选择正常。101行完整验收仍待G3完成，Task6不标全部完成。

Task6完成真实覆盖验证：101行G2为99成功/2预期失败，G3为100成功/1丢响应失败且每行恰好提交一次；2 passed/9 deselected，538.99s。独立整阶段review_m0_implementation发现1个P2：保存时Git状态不能代表起点源码。一次修复将三个CLI与golden均前置manifest采集，保留sourceBefore/sourceAfter、开始commit，两端变化或脏禁止比较；4个状态反例RED→GREEN、golden保存反例RED→GREEN，合计30 passed/3 deselected。修复后真实3行2 passed/1 strict xfailed/9 deselected（67.79s），三个实际CLI及五份报告元数据/文件对应检查通过。独立定点复核确认P2闭合，无其他重要问题；AC0-07仍pending。旧本地manifest标注缺起点快照、不可比较，实际正确性证据保留。

全后端验证首轮发现共享venv子进程可能导入原checkout，SIGINT中止PID89991并保留backend-full.log（中断清理出现stash KeyError，非通过）；已以绝对worktree/src PYTHONPATH重跑，日志backend-full-worktree.log。评审者一次uv启动意外建立忽略的worktree .venv后中止，未改生产源码，后续继续使用原目录既有解释器。阶段全量结果尚未返回，不标M0完成。

远端验收前置核对（confirmed，2026-09-30）：gh auth status报告CLI token失效；GitHub连接器get_repo仍可读取1127152834/auto-flow，默认分支codex/architecture-baseline。SSH git push --dry-run验证可创建codex/remediation-m0，但没有实际推送/创建远端分支。默认分支读取.github/workflows/golden.yml返回404；官方文档确认workflow_dispatch要求文件先存在默认分支。修正Task8步骤为先分支CI、授权合并后再手动30行验收；不把本地YAML解析或功能分支push算成手动验收。全量回归session94741仍在运行（最新61%，无失败终态），继续等待，不重启。

M0全量本地验证完成：绝对PYTHONPATH指向工作树的session94741正常退出0，5278 passed/137 skipped/20 deselected/2 warnings，1466.31s；2警告为既有anyio弃用及重复AndroidManifest测试输入。该全量开始收集后新增的报告反例由46项定向检查单独覆盖，未冒充全量收集过新反例。随后干净f60b3cac串行15份离线报告（各5份）及起止源码/各组比较维度全部核对通过；中位数万行领取key726.047ms/field998.982ms、G4 0.228ms/节点和5.001事件/节点、持久事件提交p50 1.177ms/p99 1.587ms。详见knowledge基线表。全部本地进程已结束；M0仅远端AC0-07尚未验收，持续目标仍为完整M0–M6，不标阶段或目标完成。

首轮远端CI（confirmed失败，2026-09-30）：c2f87017已普通推送至codex/remediation-m0，运行36776563696。Intel在安装阶段因mediapipe0.10.35没有x86_64 macOS wheel失败；Windows/ARM安装成功，随后各有2项真实节点浏览器测试在环境保存断言失败，尚待定位。未合并默认分支，AC0-07仍pending。

Intel依赖兼容修复（本地confirmed、远端pending）：PyPI包元数据确认0.10.21是Python3.11最后的Intel MediaPipe wheel，要求numpy<2，与OpenCV5要求numpy>=2冲突。仅Intel选择MediaPipe0.10.21/OpenCV4.11；增加uv.required-environments覆盖三平台，规则先复现原无解错误，再成功生成平台分支锁。解析同时为Intel选择兼容的torch2.2.2/torchvision0.17.2、onnxruntime1.23.2及传递依赖，ARM/Windows现有版本保持；没有禁用能力或跳过平台。来源：https://pypi.org/project/mediapipe/0.10.21/ 、https://docs.astral.sh/uv/concepts/projects/config/ 。uv lock --check及三平台sync --locked --group build --dry-run通过；ARM需显式MACOSX_DEPLOYMENT_TARGET=15.0匹配CI（默认13.0预检被现有onnxruntime14.0最低版本拒绝，未伪报通过）。本机真实模型空帧推理、手势unit/contract/worker/parity共10 passed/1既有警告，Ruff通过。安装dry-run不代表Intel/Windows实际运行通过，后续以CI结果为准。

首轮CI真实浏览器断言修复（本地confirmed、远端pending）：Windows/ARM均在test_real_worker_delayed_browser_keeps_cookie_in_one_task的saved is not None失败。本机真实内核单例复现相同RED。测试直接调用manager.run，跳过宿主dispatcher在worker确认清理后执行的_finish_end；生产bootstrap已注入project_end，故不修改生产发布逻辑。测试补齐同一宿主收尾，明确验证finishing→succeeded，再检查环境名称和冻结身份包；两个profile模式、Studio模式及browserless End相关共21 passed（17.85s），Ruff/diff检查通过。原5278项全量因未设置真实内核跳过了这些场景，不能当作本次问题的既有通过证据。

等待36777777338期间的M1预检（confirmed证据、proposed实施，2026-09-30）：未开始M1生产修改。发现Task1示例未读取wal_checkpoint返回值，真实临时SQLite两连接实验返回(1,1,0)，源表1行而主文件复制表0行；释放读事务后返回(0,0,0)。官方语义：https://www.sqlite.org/pragma.html#pragma_wal_checkpoint 。据此修订M1计划：busy拒绝复制、复制期间保持写入静止、在线备份用backup API、停机告警后仍dispose、双连接并存测试及复制后新行核验；避免仅按调用所在行过滤而漏查间接数据库路径。性能验收沿用50%目标，但参照当前干净五样本中位数1.177ms，删除旧原型数字冒充基线的空间。未声称M1实现或性能已通过。

第二轮CI Windows脚本编码修复（本地confirmed、远端pending，2026-09-30）：36777777338@64adcb40的Windows真实浏览器与类型检查通过，test:scripts为115 passed/4 failed，均出在studio-required-fields.test.mjs嵌入Python默认CP1252读取UTF-8源码；没有元数据差异证据。统一python helper增加-X utf8，同时固定源码读取和JSON输出编码，保留所有对照断言。PYTHONUTF8=0运行相关6项通过，全脚本119项通过，diff检查通过。ARM真实浏览器、类型/脚本/守门/lint/OpenAPI/Ruff/mypy及HTTP预检已通过、完整后端回归仍运行；Intel仍安装依赖。先本地提交，等待当前运行收齐结果再推送，避免cancel-in-progress丢弃仍在执行的证据；不把本地macOS结果当作Windows修复已远端通过。

第二轮CI ARM回归诊断（2026-09-30，confirmed本地复现/修复，远端pending）：36777777338@64adcb40的ARM后端为5273 passed/7 failed/137 skipped/24 deselected/2 warnings（1835.96s）；7项集中在暂停测试、4项SMTP、文件共享、凭据停止。普通本地定向11项全部通过，不能据此忽略远端失败。受控注入getfqdn延迟13秒，原SMTP/文件共享分别复现12秒/5秒超时；stdlib SMTP构造会解析本机EHLO名，HTTPServer.bind会解析本机server_name。测试固定各自本机名称，真实TLS/SMTP/IMAP/HTTP传输、业务断言及原超时保持。受控后台mutation占用0.2秒时原静止测试稳定返回201；复用现有pause_when_idle模式检查门禁返回值，成功暂停后再断言409，并finally恢复。上述故障注入同时保留时10项通过（15.92s）。DNS是已验证的测试环境依赖和一致复现路径，未拿到远端线程采样，不声称已经证明远端DNS具体耗时。

凭据停止的远端堆栈位于首轮capture_processes线程扫描；人为给该扫描增加2.2秒复现相同2秒超时。测试改为凭据读取一直阻塞至显式release，用read_done证明停止/真实进程清理完成时读取仍未返回；清理等待上限改为10秒，释放后等待真实read_done替代固定sleep，继续断言无迟到命令。受控扫描延迟下1项通过（3.87s）；反向把stop改为等待该read_done，新测试仍按10秒超时失败（10.95s），并非放过阻塞。首次反向探针因循环重新索引已移除的map而KeyError，不计为有效证据；捕获原Event后重新验证。所有探针仅放忽略目录，不修改生产调用链。相关4文件回归32 passed/1既有anyio警告（42.84s），Ruff/diff检查通过。Intel完整后端仍运行，收齐后再普通推送待验修复；M0/AC0-07继续pending，不进入M1实施。

M1容量唤醒预检（2026-09-30，confirmed代码事实/proposed实施）：ProjectBatchScheduler.startup订阅dispatcher.subscribe_idle，_run无通知时等30秒；ProjectManualRuntime只调用pause_manual，不负责唤醒调度。原M1 Task7示例为pause_manual减计数、set_capacity赋值，但未调用既有唤醒入口；原测试手动dispatch第二个run，无法证明积压批次及时前进。补齐两处_wake_idle_listeners及AC1-07，新增真实scheduler.startup、worker启动事件验收约束，禁止测试手动tick/wake/dispatch掩盖遗漏；Task8 PUT提高容量同样覆盖。不改变人工恢复允许暂时超执行名额的既有决定，不新增调度抽象，未实施M1生产代码。

CI并行验证调整（2026-09-30，confirmed配置检查，运行结果pending）：截至22:42 UTC，原Intel任务110099935900仍在全量后端回归（21:39开始），任务日志下载仍BlobNotFound；不据耗时判定停止，也不取消或重启它。已有Windows编码、ARM测试前提修复已本地验证并提交。为使这些修复进入远端验证且保留原任务，使用独立功能分支codex/remediation-m0-ci-validation；ci.yml的concurrency.group按分支区分，push触发相同完整矩阵。沿用已授权的普通功能分支CI推送，不改默认分支、工作流并发策略或验收范围，不部署、不创建PR。原任务和新候选均按实际提交记录证据；M0/AC0-07继续pending。

原Intel回归完成及剩余失败修订（2026-09-30，confirmed本地，远端pending）：110099935900正常返回failure，后端8 failed/5272 passed/137 skipped/24 deselected/2 warnings（3990.12s），完整日志已读取；未取消原任务。5项SMTP/共享失败由cfb6f995覆盖，其余3项分别是代理第二轮确认仍unknown、错误worker协议在ready前超时、双worker中成功者退出超时。普通本地5项通过后，增加0.1秒第二轮探测、2.2秒子进程启动、0.2秒解释器退出延迟，3项在相同断言/调用栈RED（3.92s）。代理工作流测试公共确认预算由50ms改为1s，第一轮显式阻塞仍必须unknown、第二轮仍复用同一operation且只发一次POST；协议测试启动预算10秒、退出使用生产默认3秒，保留所有身份/ACK/取消/归属/清理断言及独立的原生启动超时测试。无生产超时或业务逻辑修改。两文件回归67 passed/3平台跳过/1既有anyio警告（48.92s），Ruff/diff通过。该新增修复将更新同一CI验证分支，按现有并发规则替代旧候选cc380401的运行36787203849；替代原因是已有失败的具体修复，不是观察等待超时。M0仍未验收，未开始M1生产实施。

M1性能证据预检（2026-09-30，confirmed文档修订/proposed实施）：规格仍把旧原型2.0–2.6秒、4.1→1.4ms及1,935→129ms写成已验证结果，并断言GIL成因和M3彻底解决；已删除，事件提交引用当前M0干净五样本中位数1.177ms，保留AC1-09原阈值及AC1-10下降50%目标。Task10示例原先在run之后构建manifest，且万行CLI只输出不检查阈值；调整为测量前构建manifest、输出有效采样数并检查p50/max/非零样本，去除预热及多余空闲采样。明确微基准与真实调度器路径测试共同验收，五样本同步对照和线程模式分别记录，2,000行不能替代万行。结构检查4项、示例AST与manifest先于测量/CLI门禁静态检查、diff检查通过；未运行M1性能验收，未修改生产代码。本次文档提交暂不推送，保留e27b1814的运行36787864210继续验证。

CI修复独立复审（2026-09-30，confirmed）：独立评审范围64adcb40..d7ae717d，核对测试与生产协议、幂等性、阻塞读及清理调用链，未发现削弱回归能力的重要问题；评审者实际运行6个相关后端文件99 passed/3原生Windows跳过/1既有警告（92.20s），UTF-8元数据脚本6 passed。唯一P3为M1停机checkpoint示例的固定告警丢异常原因，已加exc_info=True；保留dispose行为，未实施M1。当前run36787864210@e27b1814的Windows/ARM真实浏览器与脚本步骤均success，Windows随后在mypy因3文件15个平台属性/句柄协议错误失败；本地win32目标已复现，兼容修复另行验证。ARM/Intel尚运行，不把该候选计为全绿。

Windows类型门禁修复（2026-09-30，confirmed本地/远端pending）：36787864210的Windows job110133876605在mypy报告15错误/3文件，主要是os.name分支未使Windows类型分析排除POSIX属性，以及_WindowsHandle缺Detach声明；本地mypy --platform win32复现相同15项。共享路径使用sys.platform分支和描述符保护，补句柄协议；Android停止保留POSIX进程组与Windows单进程分支，备份只在实际statvfs/O_NOFOLLOW操作前明确报告平台不支持，未添加缺省0的安全降级。首次4个边界反例RED；独立评审发现方法入口拒绝会将Windows空工作区CleanupService查询从[]改为错误（P2，真实SQLite前后复现），已收窄保护并新增空工作区/空目录反例，RED后GREEN，评审确认闭合。最终相关4文件150 passed/1既有AnyIO警告（27.48s）；最后平台守卫位置调整后5项定向再次通过；win32与darwin目标mypy各547文件通过，Ruff/diff通过，strict debt893/基线893/新增0。两次初始测试命令因工作目录/路径不匹配未执行，不计作验证。保留现有macOS CI36787864210继续运行，在已终态的原codex/remediation-m0分支提交本候选进行新一轮CI，避免取消仍有证据价值的旧任务。没有默认分支合并或发布，M0仍未退出。

M1测量方案实跑预检（2026-09-30，confirmed）：等待CI期间，从计划示例提取微基准，在干净1219e824串行执行万行同步/线程及750ms空闲对照各5次，15份manifest起止一致且comparable。线程max46.704–56.258ms、p5016.072–17.096ms，后者未满足10ms目标；空闲p502.059–2.119ms。已将实际样本及未达标边界写入基准记录和Task10；不放宽目标、不预判单一原因、未实施M1。首次汇总把manifest当指标JSON导致KeyError，筛选后全部验证通过。CI仍是原运行，没有为文档变更重新推送或取消。

M1领取热点定位（2026-09-30，confirmed诊断）：在55274af2对现有真实万行领取剖析，发现10,000次Candidate构造、330,032次递归冻结及46,836次Python比较回调；记录键显式排序也走通用回调路径。已记录原始来源与计时不可比较边界，为M1未达标项提供定位方向；未据此修改调度或提前实施M3。当前候选1219e824的Windows已进入mypy，ARM完整回归运行中；继续保留原远端任务。

M0首份CI构件核验（2026-09-30，confirmed）：e27b1814 ARM job110133876955已通过后端回归/离线基准/守门/上传；下载构件11132310685，SHA256与GitHub一致，核验3指标+3manifest及源码身份。全部dirty=true且comparable=false，不能算性能基线。工作流HTTP预检写入的artifacts/pm9目录原未忽略；隔离Git仓库RED复现报告使源码变脏，新增该精确生成目录忽略后GREEN，真正source.py仍可见。不改comparable判定，不追认旧数据；当前1219e824全矩阵仍在运行，本次忽略规则及证据只本地提交。

Windows完整回归编码修复（2026-09-30，confirmed本地、原生复验pending）：1219e824的job110139691053在完整回归20 failed/1750 passed/1 skipped/24 deselected（817.51s）终止；其中18项B5差分失败为父进程中文JSON的CP1252编码或子进程中文输出。27个B5/B6调用统一复用B1–B4既有-X utf8与encoding=utf-8，required-fields fixture补显式UTF-8。验证码真实子进程在父CP1252/子C locale下先复现输入与输出两个RED，修复后中文空选择器失败和非空成功两场景GREEN；正常环境104 passed/1既有警告（25.34s），仅父CP1252故障注入84 passed（18.57s），Ruff/diff通过。首次全局C locale故障注入103 passed/1 failed：嵌套Python脚本source只传PYTHONPATH、target继承环境造成非对称输出，保留失败，不算通过。独立复审确认27文件逐字逆向还原等于HEAD、未改冻结源码/harness/断言或生产代码，无重要问题。Android平台相关1项失败另行处理；M0仍未验收。

Android备份测试平台边界（2026-09-30，confirmed本机/模拟边界；原生Windows pending）：Windows合同测试使用声明支持的fake runtime却调用真实POSIX备份存储，返回ANDROID_PLATFORM_UNSUPPORTED。合同现分别验证原生存储和win32拒绝的HTTP409、零归档调用/零目录；新增真实SQLite拒绝持久化及原requestId不可重放。逐项核对调用链后，42个依赖实际statvfs/O_NOFOLLOW/目录fsync/权限语义或真实发布fixture的函数标记Windows不适用，共69参数场景；不删除断言或放宽生产安全机制。纯归档/数据库/提前拒绝保留，三个已有磁盘预算模型显式模拟POSIX块大小并继续跨平台运行。7文件本机120 passed/1既有警告（11.45s）；最后P3缩小跳过后7定向passed，模拟win32存储边界51 passed/69 skipped（1.24s），后者不是Windows实机证据。Ruff/diff通过，独立审查无重要问题；建议保留预检持久失败的跨平台测试已采纳。M0仍未验收。

新远端事实：e27b1814 ARM job110133876955后端5284 passed/137 skipped/24 deselected（2102.39s）、前端454文件和构建通过，随后原生项目场景44 failed/31 deselected（147.36s），均在创建automation请求的旧workflowId字段被422拒绝。整体job失败，不沿用前序步骤当全绿；夹具修复另行推进。

原生场景所属工作流夹具修复（2026-09-30，confirmed有界修复、整组仍失败）：五文件12个创建点改为正式POST automation产生所属空文档，再GET/PUT真实场景内容；复用golden/harness流程，在已有workflows fixture中提供sync/async两个简短辅助方法。删除无用独立文档创建，不改生产契约或业务断言。真实内核启动失败两模式+单任务参数3 passed（24.36s）；Studio成功+Sheets异常来源仍正确执行2 passed（21.80s）。Ruff/diff通过；独立审查确认全部12点覆盖、legacy browserEnvironmentVersion缺省保持、中途工作流ID/revision一致，未删除业务断言。模块import位置P3已修。扩大CI相同选择并加success共46项，maxfail3结果3 failed/8 passed/29 deselected（100.74s）：data-schema/data-delete-field/data-subflow在End的CAPABILITY_SCOPE_DENIED，非创建422；读取pytest-62真实SQLite确认三例均是End失败。整组尚未通过。

End历史兼容缺口（2026-09-30，confirmed代码与运行证据；修复未实施）：旧原生夹具发送nested retainEnvironment.recordTargets包装项；当前正式End wire只含arguments.recordTargets的bare RecordRef，动态目标为完整变量引用，link revision由Task cursor派生。独立审查历史f670145f第二父分支的旧worker/UI证实旧形状曾被支持；现有normalize_project_end仅搬运该列表，不能等价执行。这是历史兼容缺口，不能通过把当前新建场景改用正式契约就宣称已修；后续M6兼容/迁移门禁须保留该反例，不放宽后端fencing。M0继续修订新建原生场景夹具，尚未验收。

End 动态名称兼容修复（2026-09-30，confirmed 定向/原生复测中）：owned-workflow 夹具更新后，真实 data-schema/data-delete-field/data-subflow 在 End 被 CAPABILITY_SCOPE_DENIED 拒绝；SQLite 确认旧包装 recordTargets 不再符合正式裸 RecordRef 契约。测试改用既有 PythonScript 汇合变量列表及 flat End，Sheets inputIds 明确选择对应输入。曾尝试 JS 汇合，headless harness 缺 renderer 交互通道导致约30秒超时（3 failed/1 passed/51 deselected），已弃用，不作为生产 JS 缺陷。Python 汇合后真实 data-schema 的两个 Task 中仅一个成功；pytest-65 SQLite 指向第二次 saveEnvironment 的 IDENTITY_CONFLICT：宿主保存了固定/未解析名称。

本轮先补名称解析和真实 SQLite 准入测试，RED 为11 failed/6 passed/73 deselected（5.38s）。修复只传可选动态 name，host 精确限制参数形状、校验静态冻结名称不可覆盖、真字符串及既有1–36字符规则，在 durable payload 中持久化；完整 workerRequest 对比保护重放。变量访问正则从原 resolver 原样抽取，未改变其解析行为。旧无 name 请求仍用冻结名称，mode/replace/input/version/ref 权限未变。End/恢复/栅栏定向102 passed/1既有anyio警告（13.23s），变量 differential/End 控制流86 passed（9.14s），Ruff及mypy547通过。独立只读复审无重要问题；真实浏览器场景仍在验证，尚不据此关闭M0。

远端1219e824 ARM结果（2026-09-30，confirmed）：job110139690940完整日志确认后端5289 passed/137 skipped/24 deselected/2 warnings（1746.06s），前端与构建success；原生选集44 failed/31 deselected（164.49s）均为旧 workflowId extra 字段422，尚未运行ca5b3704的修复。Windows旧候选失败与Intel进行中状态仍单列，不将该候选计为全绿。

End 原生增量（2026-09-30，confirmed 部分通过）：真实 data-schema、data-delete-field（含conflict）、data-subflow（含cancel）、data-parallel（含failure）、data-link-forged-end 共8项通过；data-schema读取已保存环境并断言名称等于各记录UUID。合并Sheets归档选集结果1 failed/8 passed/62 deselected（130.27s），失败为旧stage_candidate拦截器未透传identity_package，补齐后单独重跑仍1 failed/11 deselected（104.26s）：保存和取消已完成，但归档停在closing。pytest-70真实SQLite只读_blockers定位到取消Task的实例仍waiting_manual，另一个End操作已completed；此为后续独立修复，不能把本组全部标通过。End名称自身修复通过定向和8项原生并经独立审查，无名称唯一性、Task数量或安全断言放宽。

取消人工现场清理（2026-09-30，confirmed本地/远端pending）：原生归档超时根因在共享disposable_task_instances：状态不含waiting_manual，且任意manual历史均阻止候选。新增11项先得到5 failed/6 passed（5.26s）；查询复用MANUAL_TERMINAL，只有终态Run、同instance/project/task/run的终态人工证据且没有该实例任何未终态manual才释放waiting_manual候选。仍排除unknown/saving/retained_unsaved，未决/失败save继续保护，实际删除沿既有native closer与生命周期锁。清理/Task投影/End恢复47 passed（14.92s）；原生归档同用例从104.26s失败转1 passed（14.67s），覆盖保存/取消/核验/归档/重启/删除完整链。补充3项错误归属反例时第一次外项目夹具用了不存在项目，触发FK错误（1 failed/91 passed）；修正为实际创建邻居项目后环境/生命周期合约92 passed（31.78s），Ruff/mypy547通过。独立只读复审无重要问题。

人工结束内部授权（2026-09-30，confirmed本地/远端pending）：扩大原生回归3 failed/20 passed/32 deselected（297.31s）。data-link-race拦截器遗漏新authority关键字导致TypeError，补齐原样透传后真实关联冲突/修复断言通过。余下人工parallel-finish/expire再加expire-race定向3 failed/1 passed（43.50s），pytest-77 SQLite明确finishManual失败为END_ACCESS_REVOKED：合法ManualRuntime.complete回调被公共EnvironmentService.end活动Run限制拒绝。新增仅keyword trusted_manual=False，只有已通过冻结节点/访问、checkpoint、关闭确认、host intent/expiry的内部回调传True；未放入payload，未冒用workerEnd。保留实例锁、事务中的归属/代次/状态检查及现有人工End账本和子保存恢复。

新增4项边界测试先4 failed（1.95s）；第一次GREEN检查误用会创建目录的instance_path判断删除（1 failed/116 passed），改为保存既有Path后验证。最终能力/End/环境合约117 passed（36.59s），Ruff/mypy547通过；真实manual-parallel-finish/manual-finish/manual-expire/manual-expire-race共4 passed（46.37s）。独立评审已核对设计通道，不削弱公共End或保存竞争栅栏；当前完整原生选集正在复跑。

POSIX 信号拒绝退出竞态（2026-09-30，confirmed本地/远端pending）：1219e824 Intel job110139691123完整回归1 failed/5288 passed/137 skipped/24 deselected/2 warnings（3603.30s），唯一失败为强停人工交互时os.killpg(SIGKILL)抛EPERM。具体内核原因未知；共享force_process_tree仅将PermissionError送入既有有界退出核验，保留异常cause；父进程未回收、同birth子进程仍活或身份未知但存在时仍失败并保留manager容量与目录，不信号未验证PID。新增graceful/强停×退出/父活/子活/未知子/PID重用共10反例先RED10失败，最终进程与交互三文件107 passed/3 skipped（44.14s），Ruff、mypy547与diff通过。独立只读复审无重要问题；未将故障注入当Intel原生复验。

完整原生选集复验（2026-09-30，confirmed本机）：与CI相同五文件选择式44 passed/31 deselected/1既有AnyIO警告（562.29s），包含End数据/人工/Sheets/Excel/无限任务/写入冲突。进程于e251fbe8启动，之后新增EPERM修复由107项定向单列覆盖，不能称完整选集运行于最终HEAD。三平台旧远端任务均已终态；推送已提交候选供新矩阵复验。桌面完整冒烟另在修订旧断言/夹具，尚未通过、不纳入此提交。

桌面冒烟修订进行中（2026-09-30，confirmed部分场景/整体pending）：本地构建35.20s通过；原工作树desktop依赖和Python虚拟环境以本地symlink复用，不改锁文件。实际Electron独立Studio浏览器、保存/关闭/重开、6个项目页、旧独立文档解绑保留与编辑后所属文档删除均已执行通过。脚本旧预期69模块改为实际218及project_data正式字段/缺项目准入提示；创建后工作流使用正式所属文档。无保留Task页面实际走DurableEndResult，旧TaskEndPanel提示仍存在于legacy组件但不适用本场景；改为End完成+清理确认，保留磁盘副本不存在/不报保存成功/无再次保存按钮的断言。

完整桌面运行仍失败，不能计全绿：00:46Z轮在Profile冻结编辑时expectedRevision=1/currentRevision=2冲突，根因复制独立文档后继续使用旧文档修订号；两处冻结编辑改先GET实际所属文档。00:50Z轮进一步运行至subflow准入，firstSaved变量表达式长于End静态36字符上限被拒绝；仅夹具改为同resolver已支持的无引号下标，最终值仍UUID，未放宽生产长度限制。正式End禁止替换会在发布前拒绝，旧“先保存再关联失败”预期无效；新增独立人工保存场景覆盖saved_unlinked与修复，同时保留正式End拒绝、零新增环境、零部分关联反例。旧固定expectedContentGeneration不再控制flat End，新Task自动读取当前来源；改为真实人工保存失败保留旧副本、正常Task发布新代次、再对旧副本HTTP保存冲突。当前两脚本仍未提交，真实整链验证与独立审查进行中。

远端候选14df725c已推送，run36797958370：https://github.com/1127152834/auto-flow/actions/runs/36797958370 。三平台检查均已启动；ARM进入完整后端回归，Intel仍安装依赖，Windows前端类型检查；未提前记录通过。GitHub fetch_commit_workflow_runs连接器只返回PR触发的运行，因此空列表不代表push未触发；此次通过公开Actions API按head_sha查到运行，再用连接器核对job。

Windows POSIX模拟夹具补全（2026-09-30，confirmed本地/原生pending）：14df725c Windows job110165627813在原生平台边界步10 failed/27 passed/1 skipped/1 warning（3.04s）；全部新EPERM模拟用例缺少Windows没有的SIGKILL/getpgrp。独立子进程删除两个属性复现10 failed/43 deselected（6.20s）；测试仅替换cleanup.signal与identities.os的模块局部引用，显式模拟15/9信号、当前组999与已有denied函数，不污染全局os/signal，不改生产代码或跳过测试。缺API故障注入10 passed/43 deselected（8.24s），正常完整进程单元53 passed（9.24s），Ruff/diff通过，独立只读审查无重要问题。保留运行中的两个macOS job，不重启远端矩阵。

桌面真实整链通过（2026-09-30，confirmed源码darwin/arm64；原生Windows/Intel/安装包未替代）：00:54Z轮在mixed首次End被CAPABILITY_SCOPE_DENIED拒绝，输入关联缺少正式写授权。夹具复用updateRecord按冻结revision写回原task-second并声明现有grant；auto更新原环境inputIds=[]避免无须进行的重绑，仍比较完整记录不变。独立审查两项P2已补：修复后同时断言新建目标关联；把现有第三次浏览器恢复移到旧副本409之后，验证实际cookie仍9，无额外恢复任务。

00:57:45Z开始的完整Electron生产sidecar冒烟最终status=passed；artifacts/pm9/source/project-desktop.json SHA256 ab36280b61db3160d386152c7f25318b58e939018550654bfb987a1e37f3b8c3。实际覆盖Studio独立执行/准入/保存/双窗、所属文档删除、6页、人工继续、未保存工作副本清理、Profile/root冻结、并行/子流程、正式End预检零保存、人工saved_unlinked两目标修复/刷新/历史失败保留、旧副本持久失败且新代次登录cookie恢复、归档恢复。1万行由5个真实HTTP写入者生成，busyRetries=0，表格每页50行；1004条真实worker日志分6页，另60秒合成输入1000条；200%缩放与Electron/sidecar重启保留数据。性能数字仅此次烟测观察，不作为干净可比较基准或持续负载无泄漏证明。最后一次只读查询临时SQLite报无法打开，是脚本成功后已按自身finally移除自建工作区；不计该查询为验证。CI使用的纯HTTP入口另行验证中。

纯HTTP真实入口通过（2026-09-30，confirmed源码darwin/arm64）：01:02:44Z开始，smoke-project-management.mjs --runtime-kernel 实际退出0、status=passed；artifacts/pm9/http-source/project-api.json SHA256 89157bbe200057eefe4a32be65d473eef45668a53aad29015f489a0c4ab4d02b。无桌面hook的两目标修复、旧副本409之后gen2/cookie9恢复、真实浏览器运行链、1000并发单行命令（5写入者/0busyRetries）及sidecar重启均通过。与完整桌面两条入口分别执行；脚本守卫18项通过，node --check/diff通过；独立最终复核无未闭合重要问题。保持两台macOS旧候选任务以取得完整回归证据，当前已验证脚本与Windows夹具候选经既有ci-validation分支正常快进推送另行复验，不修改默认分支或取消旧任务。M0 AC0-07仍pending。

业务组合夹具与实际打包验证（2026-09-30，confirmed本机darwin/arm64；三平台pending）：源码诊断复现人员初始化End的CAPABILITY_SCOPE_DENIED，冻结输入没有写授权；旧嵌套retainEnvironment/包装目标不符合当前正式契约。仅修订smoke-project-business-combinations.mjs：初始化通过现有updateRecord按冻结版本写回P001，再用固定inputId关联；注册仅选择邮箱inputId和本任务新建账号裸ref，复用现有Python节点组装数组，不增加人员写授权。人员不变基准仍在初始化后取得，后续全部内容/状态/关联及版本不变断言保留。独立只读复审无重要问题，node --check、18项相关脚本检查和diff通过。

现有虚拟环境以PYTHONPATH=src执行python -m PyInstaller --noconfirm autoflow-backend.spec成功（138.793s），随后npm run package:dir成功，得到未签名mac-arm64/AutoFlow.app；未执行安装器安装或发布。冻结后端SHA256为31ee18e0e549b5f9ec655394555938a3592b56b3638071e8086670f80dc566d1。01:11:10Z开始的真实打包业务组合退出0/status=passed，报告artifacts/pm9/packaged-business/business-combinations.json SHA256 3861f26cae0aba31ac994fa658350905b9fd255c526b9fad730d86654c06df68：共享人员已有环境与全部版本不变，邮箱消费不重复创建，邮箱和唯一账号共享新登录环境，后续Task恢复cookie；双任务领取/隔离/完成和结构确保冲突仍全部通过。无live Sheets或物理安装验收声明。

同一App内sidecar启动烟测退出0；01:12:36Z开始的打包HTTP整链退出0/status=passed，artifacts/pm9/packaged/project-api.json SHA256 bf630068bebc6d9dff546ee782c96fc2749057f80380d23cf33cbdab2dec3f7d。实际覆盖1000单行写入/5个HTTP写入者/0busyRetries、两目标关联修复、旧副本冲突后gen2/cookie9恢复、Profile/root冻结、并行/子流程和重启。上述结果是功能验收子范围，不作为干净性能比较；完整打包桌面另行运行，AC0-07不提前计通过。

完整打包桌面收口（2026-09-30，confirmed本机darwin/arm64）：01:15:24Z开始、01:20Z结束，smoke-project-management-desktop.mjs使用上述AutoFlow.app与真实浏览器，退出0/status=passed；artifacts/pm9/packaged/project-desktop.json SHA256 89f74da9574156df412173aeea434401b53191d320b6857bbf6251ef0ae0c47c。26张截图中已目视检查未保存清理和关联修复刷新：无错误保存成功提示、保留历史失败。完整场景含万行5写入者/0busyRetries、每页50行、1004条真实worker日志/6页、60秒1000条合成日志、200%缩放、双窗口与重启；单次seedMs=40547，不作性能提升比较或持续负载无泄漏声明。附加打包浏览器API、基础桌面及浏览器配置桌面均退出0；基础桌面验证host终止后sidecar退出。浏览器API开放SSE退出场景出现Uvicorn graceful timeout/CancelledError日志，但脚本断言8秒内进程exit0且端口关闭通过；日志不隐去，也不声明无错误日志。

候选c585a7aa已正常快进推送ci-validation，run36800414483（https://github.com/1127152834/auto-flow/actions/runs/36800414483）三平台已启动；03c33c4a旧同分支运行被新实际修订替代，不计取消为通过。另一分支14df725c的ARM/Intel完整回归仍在运行，Windows已知失败由ba9830f5修复。当前仅新增本条验证记录，不为文档追加重启矩阵；默认分支合并、手动黄金流程和AC0-07仍pending，M1生产实现未开始。

远端干净基准产物核对（2026-09-30，confirmed子范围）：14df725c ARM job110165627798的完整后端回归、离线基准、上传三步均success，前端回归继续运行；尚未取得终态完整日志，不推断具体测试数。artifact11135354382（benchmarks-macos-15，3325字节）实际下载ZIP并核对API所报SHA256 e57816f26f94e6bc7eab99392653142dc3d3f065d64b3a4783be8887091214dc。3组report/manifest逐对检查，sourceBefore/sourceAfter均为14df725cbd884c854277e2d648ad88938a7d07dc且dirty=false，sourceDirty=false/comparable=true；与旧e27产物的脏工作区不同，7108f61c产物目录忽略已在远端验证。领取10000行的键/字段排序610.066/817.076ms，G4实际5000节点0.330ms/节点和5.001事件/节点，1000事件提交p50/p99为1.701/4.660ms。实际环境macOS15.7.9 ARM、3逻辑CPU、7GiB内存、Python3.11.9、SQLite3.45.1；每场景仅1份/1次样本，不能与本机不同硬件基线计算提升比例，也不满足五样本比较要求。整体CI和AC0-07仍pending。

Windows夹具原生复验（2026-09-30，confirmed子范围）：2026-10-01 01:31Z查询run36800414483@c585a7aa，Windows job110173439898的“Check native Windows platform boundaries”和“Check native desktop path and settings contracts”均completed/success；包含ba9830f5的显式POSIX模拟夹具，关闭旧候选14df725c同一步SIGKILL/getpgrp缺失失败的原生复验缺口。当前正在HTTP写入预检，完整回归和打包尚未结束；只依据已完成步骤记录通过，不推断测试数或整体CI全绿。

旧候选ARM终态日志核对（2026-09-30，confirmed；2026-10-01 01:40Z结束）：run36797958370@14df725c的job110165627798最终failure。完整日志确认后端5336 passed/137 skipped/24 deselected/2 warnings（1724.02s），离线基准21 passed（2.81s），前端5972 passed/454文件（441.03s）、构建success，真实worker选集44 passed/31 deselected/1 warning（481.72s）。唯一失败步骤为随后的旧HTTP冒烟：第一个参数Task人工继续后在End报CAPABILITY_SCOPE_DENIED。已对照14df725c脚本第123行首个run及03c33c4a差异：旧嵌套retainEnvironment/包装recordTargets已替换为正式flat End及裸ref数组，与本地已通过的源码/打包HTTP场景一致。该旧失败不要求再次改生产授权或重启旧任务；当前c585a7aa包含03c33c4a，远端新版验收仍在运行。后续打包在旧job中未执行，不能由前序通过推断整体通过；旧Intel仍待终态。

当前候选ARM基准产物（2026-09-30，confirmed子范围；2026-10-01 01:59Z）：run36800414483@c585a7aa的job110173439919后端完整回归、离线基准、上传均success，进入前端测试；终态日志未出，不推断测试数。artifact11135889239（benchmarks-macos-15，3327字节）已下载并核对SHA256 f8ffb3a7c9595aac9ab04401f73ba91c6f048938d6d279ca6ff5629184ead698。三组report/manifest来源均c585a7aa4af8c3c5bae01f53b0533989e2423a07，前后源码一致且dirty=false/comparable=true，规模与报告配对断言通过。实际领取10000行键/字段743.512/1041.996ms，5000节点0.422ms/节点、5.001事件/节点，1000事件提交p50/p99为2.404/7.045ms；3CPU/7GiB/macOS15.7.9 ARM/Python3.11.9/SQLite3.45.1。每场景仍仅一次；不把与另一CI运行的数值差异当性能回归或提升证据，五样本比较与整体CI验收未由此完成。Windows、新旧Intel仍运行。

旧候选Intel完整回归与基准（2026-09-30，confirmed子范围；2026-10-01 02:03Z）：run36797958370@14df725c的job110165627571完整后端回归、离线基准与上传均success，前端测试正在运行；这提供包含e6477b69退出核验修复的Intel全量通过证据，但不是再次注入同一内核EPERM竞态的证明。终态日志未出，测试数暂不推断。artifact11135474903（benchmarks-macos-15-intel，3345字节）下载并验证SHA256 c4fcb95829f136a913c732e04d7e0114b21f9a35515da40f67eaa8f0c500f328，三组report/manifest源码前后均14df725cbd884c854277e2d648ad88938a7d07dc且dirty=false/comparable=true，规模和配对断言通过。10000行领取键/字段1980.427/2645.681ms，5000节点1.857ms/节点及5.001事件/节点，1000事件提交p50/p99为4.563/6.662ms；4CPU/14GiB/macOS15.7.9 x86_64/Python3.11.9/SQLite3.45.1。每场景一次，不作跨平台或五样本性能比较；当前候选c585a7aa的Intel/Windows仍在完整回归，ARM前端进行中，AC0-07仍pending。

当前候选ARM源码冒烟复验（2026-09-30，confirmed子范围；2026-10-01 02:25Z）：run36800414483@c585a7aa的job110173439919已通过前端测试、构建、真实worker恢复/共享Sheets领取/人工过期竞态选集、HTTP真实内核冒烟和源码桌面冒烟步骤，正在backend:build。03c33c4a覆盖的旧HTTP首个Task End授权失败已由新版同一步骤远端通过复验；终态完整日志未出，不推断各测试数量，也不把源码桌面步骤等同于后续打包桌面验收。Windows与Intel仍在完整后端回归，默认分支黄金流程和AC0-07仍pending；本条仅记录已完成步骤，不为文档更新重启矩阵。

旧Intel终态核对与新版退出竞态修复（2026-09-30，confirmed本地修复、远端复验pending；2026-10-01 02:29Z）：旧run36797958370@14df725c的Intel job110165627571完整后端5336 passed/137 skipped/24 deselected/2 warnings（3181.76s），离线基准21 passed（6.07s），前端5972 passed/454文件、真实worker选集44 passed/31 deselected/1 warning（715.67s）；最终仍在旧HTTP首个Task End报CAPABILITY_SCOPE_DENIED，与旧ARM相同且由03c33c4a覆盖，后续打包未执行。该旧矩阵现全部终态。

当前c585a7aa Intel job110173439678完整后端2 failed/5334 passed/137 skipped/24 deselected/2 warnings（3010.90s）：Python节点和命令节点停止时，旧test_browser_worker.force_process_tree调用browser_processes.signal_processes的SIGTERM遇到EPERM直接抛出。e6477b69只覆盖项目worker，旧公共清理与孤儿恢复同类路径仍缺少有界退出核验。两处沿用已有项目worker处理：记录TERM/KILL的PermissionError后继续原有父进程wait及birth/liveness检查，未确认退出继续失败并保留目录/状态，异常原因保留；不放宽原生身份验证，不改信号、等待上限或Windows逻辑。新增7例先全部RED（0.30s，相同权限异常），后全部GREEN（4.17s）；覆盖父进程仍活、子进程仍活、身份未知、PID重用、实际退出及恢复目录保留。六文件回归142 passed/9平台跳过（80.69s），包括两项原始失败场景；Ruff、mypy547与diff检查通过。独立只读复审无重要问题，另行7例通过（4.15s）。仍需Intel原生复验，不能把本机结果或旧候选全量通过当作已关闭新版竞态。当前ARM已进入打包整链，Windows仍运行；保留ci-validation现有运行，使用已终态的codex/remediation-m0分支正常快进推送新修复进行完整矩阵复验，AC0-07继续pending。

ARM远端打包子范围通过（2026-09-30，confirmed步骤级证据；2026-10-01 02:39Z）：run36800414483@c585a7aa的job110173439919依次完成backend:build、package:dir、Check and smoke packaged sidecar、Build installer artifact和smoke:desktop，全部success。打包检查工作流串行执行sidecar启动、真实内核HTTP、业务组合、打包桌面整链、浏览器API及桌面检查，每项非零即退出；此步骤成功提供远端打包业务契约修复通过证据。安装器步骤仅构建并确认dmg存在，未作安装、签名、发布声明；job仍运行、PM9构件尚未上传，未取得完整终态日志及报告摘要/哈希。Windows全量回归仍运行；包含新增旧worker退出修复的728cf027已触发run36806236192，其ARM进入完整回归，不能将旧c585打包结果替代新候选完整验收。M0/AC0-07仍pending。

原生浏览器功能测试预算修订（2026-09-30，confirmed本地/proposed远端复验；2026-10-01 02:55Z）：run36806236192@728cf027的Intel job110191075767在node-owned浏览器检查1 failed/4 passed（104.91s）；delayed_browser[False]的nodeAttempt报WORKFLOW_NODE_TIMEOUT、duration15148ms，原失败诊断只含payload，无法据此断言具体远端节点或初始化阶段耗时。未改版本的本机真实内核5项通过（14.62s）。沿调用链确认_TimedNode的15秒覆盖宿主初始化授权、真实浏览器启动和导航；忽略目录探针在initializeBrowser授权前注入16秒异步等待，原测试复现相同15025ms超时（1 failed/18.09s）。这证明原预算可触发同类失败，不等于取得远端耗时剖析。

仅修订test_node_browser_initialization.py：两个open_page节点改用现有执行器默认30秒，外层45→90秒以容纳两个节点、读取及启动/退出；失败诊断增加nodeId，cookie、单实例、冻结身份、End宿主发布、清理确认及空闲断言全部保留，生产超时逻辑不改。保留16秒注入时两种profile配置2 passed/3 deselected（39.98s）；正常真实浏览器5项加既有50ms凭据节点超时反例共6 passed（15.60s），Ruff/diff通过。独立静态复审无重要问题。两轮ARM/Windows仍运行，修订先本地提交，保留现有完整验收；取得可用分支的终态后再正常推送复验，不把本机通过当作Intel原生通过，AC0-07继续pending。

最新测试修订远端复验安排（2026-09-30，confirmed修订就绪/远端pending）：dc26be2a已完成定向真实内核验证和独立审查。此前暂缓推送以保留两轮回归；现将最新候选正常快进推送codex/remediation-m0，按既有分支并发策略替换含已知Intel失败的728cf027运行，以验证具体测试修订。另一个ci-validation分支的c585a7aa ARM最终回归与Windows完整回归继续保留。替换依据是已验证的新修订，不是观察超时；被取消的步骤不计通过，不修改CI门禁、默认分支或部署。

三平台原生浏览器初始化复验（2026-09-30，confirmed步骤级子范围；2026-10-01 03:14Z）：最新run36808514086@98e95dba的Intel110198234330、ARM110198234563、Windows110198234644在Verify node-owned browser initialization and cleanup步骤均completed/success。dc26be2a预算修订的Intel原生复验缺口关闭；不声称此前远端具体耗时成因已经查明。终态完整日志未出，不推断各平台测试计数。当前Intel类型检查、ARM全量后端、Windows HTTP预检进行中；较早c585a7aa ARM最终后端及Windows完整后端继续运行。全矩阵与默认分支黄金流程仍pending，本条文档证据不触发重新推送。

ARM首个完整远端任务通过（2026-09-30，confirmed该候选单平台；2026-10-01 03:17Z结束）：[run36800414483 / job110173439919](https://github.com/1127152834/auto-flow/actions/runs/36800414483/job/110173439919)在c585a7aa4af8c3c5bae01f53b0533989e2423a07最终completed/success。完整日志确认两轮后端各5336 passed/137 skipped/24 deselected/2 warnings（1925.69s、1688.78s），两轮前端各5972 passed/454文件，离线基准21 passed（3.62s），真实worker选集44 passed/31 deselected/1 warning（566.31s）；检查、构建、源码冒烟、打包整链、安装器构建、strict类型债务检查和最终构件上传均成功。

打包日志中的业务组合报告status=passed，确认人员状态/内容/关联和版本不变、邮箱消耗、唯一新账号与共用登录环境、下一Task恢复cookie及并发领取/字段冲突隔离。打包桌面报告status=passed，含未保存副本清理、人工关联修复且原End历史仍failed、旧副本拒绝后gen2/cookie9恢复、10000行五写入者/0 busyRetries及26张截图清单；本次未下载截图，不声称视觉复验。源码桌面步骤只运行管理链，完整运行时与规模场景由打包桌面步骤覆盖。日志仍有浏览器管理SSE关闭时Uvicorn graceful shutdown超时/CancelledError，烟测退出成功不等于日志无警告。AutoFlow-0.1.0-arm64.dmg已构建；代码签名因缺证书跳过，未执行安装或发布。

PM9构件11139561095（pm9-macos-15）上传883628173字节；日志与API元数据一致给出ZIP SHA256 bd4b8fd89576d36cc3b773009db20c4a8719069cb60b185a504b3e0f5e63ab45。下载连接器因超过536870912字节上限拒绝，因此未下载或本地复算此ZIP哈希，报告结论来自完整job日志；不能将元数据一致称作本地校验。此前已下载并校验的独立benchmark小构件证据不受影响。最新98e95dba三平台及较早c585a7aa Windows仍在完整后端回归；本次ARM成功不替代包含后续修复的最新候选验收，M0 AC0-07和默认分支黄金流程继续pending。

最新候选ARM完整后端及基准（2026-09-30，confirmed子范围；2026-10-01 03:38Z）：run36808514086@98e95dbad3db54bf7536507ee7556ebf2c39afac的ARM job110198234563后端完整回归、离线基准、构件上传均completed/success，当前前端测试进行中；完整终态日志未出，不推断测试计数。artifact11139786001（benchmarks-macos-15，3323字节）已实际下载，ZIP SHA256 c05b8b30c8af1c6ce2ef03e59e439d789003cfb27a6deef65e6b2045ade79348与API一致。三组report/manifest逐对断言：sourceBefore/sourceAfter及报告commit均为98e95dba，dirty=false/sourceDirty=false/comparable=true，10000行领取、1000事件及1000轮/5000节点规模一致。领取键/字段1126.381/1387.331ms，框架0.577ms/节点及5.001事件/节点，事件提交p50/p99为1.464/4.039ms；macOS15.7.9 ARM、3逻辑CPU、7GiB、Python3.11.9、SQLite3.45.1。每场景仅一次，不能由与旧运行数值差异推断性能退化或改善，不能替代五样本比较。首次Python urllib下载因本机证书链缺失失败，随后使用系统curl正常TLS校验成功，无关闭证书验证。Intel、当前Windows及保留c585a7aa Windows仍在后端回归；AC0-07继续pending，本证据记录不触发重新推送。

最新ARM源码链路复验（2026-09-30，confirmed步骤级子范围；2026-10-01 03:58Z）：run36808514086@98e95dba的job110198234563前端测试、前端构建、真实worker恢复/共享Sheets领取/人工过期竞态选集、真实内核HTTP冒烟及源码桌面管理链均completed/success，当前backend:build进行中。步骤结论已通过Jobs API逐项核对；完整终态日志未出，不推断测试数量或截图内容，源码桌面管理链不替代后续打包桌面的运行时与规模检查。Intel110198234330、Windows110198234644及保留c585a7aa Windows110173439898仍在完整后端回归。最新候选打包/安装器/最终回归与默认分支黄金流程尚未完成，AC0-07保持pending。

最新ARM打包与安装器步骤通过（2026-09-30，confirmed步骤级子范围；2026-10-01 04:12Z）：run36808514086@98e95dba的job110198234563后端可执行文件构建、桌面目录打包、打包sidecar整链冒烟、安装器构建及后续桌面/浏览器管理冒烟均completed/success；再次OpenAPI检查、Ruff、mypy和strict类型债务检查也success。Jobs API已逐项核对30–40步，当前最终前端回归41运行，最终后端42及PM9上传43待执行；未取得终态完整日志或最新PM9构件，不推断数量、哈希、签名或安装结果。Intel与两轮Windows仍在完整后端回归。此为最新候选的打包步骤证据，不依赖较早c585候选成功替代；整体CI和AC0-07仍pending。

最新Intel完整后端与基准通过（2026-09-30，confirmed子范围；2026-10-01 04:15Z）：run36808514086@98e95dbad3db54bf7536507ee7556ebf2c39afac的Intel job110198234330完整后端回归、离线基准与上传均completed/success，当前前端测试进行中。包含728cf027旧worker/孤儿清理修复的候选已取得Intel全量回归通过证据；不声称相同内核EPERM竞态再次发生或已复现，完整终态日志未出，不推断具体测试计数。artifact11140748604（benchmarks-macos-15-intel，3342字节）已实际下载并验证ZIP SHA256 d91c03a037b474c2f2862ae28a5c857474692eb5244b55a50ae27bd1575adb60与API一致。三组report/manifest来源前后均98e95dba、dirty=false/sourceDirty=false/comparable=true，报告配对、10000行/1000事件/1000轮5000节点规模断言通过。领取键/字段2177.935/2888.893ms，框架1.658ms/节点及5.001事件/节点，事件提交p50/p99为4.109/6.545ms；macOS15.7.9 x86_64、4逻辑CPU、14GiB、Python3.11.9、SQLite3.45.1。每场景一次，不作为五样本或跨运行性能比较。ARM最终前端、两轮Windows完整后端继续运行；最新全矩阵与默认分支黄金流程仍pending。


最新ARM终态失败与严格归属复查（2026-09-30，confirmed本地修复，远端复验pending；2026-10-01 04:49Z）：run36808514086@98e95dba的ARM job110198234563最终failure。首次完整后端5343 passed/137 skipped/24 deselected/2 warnings（1796.30s），原生worker选集44 passed/31 deselected/1 warning（487.10s），前端、源码/打包冒烟和安装器构建步骤均success；最终后端1 failed/5342 passed/137 skipped/24 deselected/2 warnings（1726.71s）。失败为test_workflow_proxy_workers::test_concurrent_project_workers_keep_proxy_requests_owned，清理阶段capture_processes(strict_ownership=True)抛Candidate browser process ownership is unavailable。原日志未包含候选PID，不能证明具体是另一worker、已死亡进程或权限问题；本机原用例1 passed（0.91s）。PM9构件11141159600上传890808552字节，上传日志SHA256为932fcd76ccf7ac0ab2955b6cb6bdb8fd0ec8195dd14cb801dc66e9cfbcb50af6；未下载、未本地复算或检查截图。

代码路径确认：全系统候选扫描先用命令文本过滤，再核对原生可执行文件/环境标记；单次原生读取失败且PID仍存在会立即中断，进入不了后续退出等待。最小修复放在共享project_browser_processes.capture_processes：仅严格扫描的未知候选复读原生信息，整次调用共用两秒观测上限、10ms间隔；持续未知继续抛错，附候选PID，不输出参数或环境。未改变信号发送、目录释放和manager容量门禁。四种瞬时反例先4 failed（0.20s）；独立审查另发现父PID重用后旧子树可能被误认的P1，双PID反例先1 failed（0.13s），补充进入owned集合前的birth一致性检查关闭，仍保留末尾复核。身份变化或未知时拒绝扩张旧ppid快照，不能用当前标记认领旧子进程。

最终归属/恢复/代理三文件回归82 passed/6 skipped（29.01s），永久不可读测试增加虚拟时钟两秒截止断言后六项定向6 passed（0.18s）；Ruff和mypy547通过。独立复审P1闭合、无剩余重要问题，独立六项6 passed（0.11s）、diff检查通过。远端精确竞态尚未复现，模拟测试不替代新候选原生验收。M0 AC0-07仍pending，M1尚未实施。

修复后额外worker回归：test_workflow_worker.py与test_workflow_worker_process.py共78 passed/3 skipped（26.99s）。六项平台跳过与三项平台跳过均未计通过。下一轮采用新的codex/remediation-m0-ownership-validation普通分支保存本修复的完整矩阵，避免取消98e95dba正在运行的Intel/Windows及c585a7aa Windows；不改工作流门禁或默认分支。

最新归属复查修复的三平台原生检查（2026-09-30，confirmed步骤级子范围；2026-10-01）：run36817654197@d8d3210e3eadf556d9f9603e985f1f622f1960f5的ARM110226128259、Intel110226128439、Windows110226128459，其Verify node-owned browser initialization and cleanup步骤均completed/success。Windows平台边界、桌面路径/设置契约和HTTP前置写入也success；ARM/Windows完整后端回归运行，Intel类型检查运行。该结果仅证明原生选集，不能据此声称先前并发代理清理竞态已在远端复现或完整回归通过。另保留run36808514086@98e95dba的Intel110198234330已完成backend:build、package:dir及打包sidecar整链冒烟（30–32全部success），安装器构建33运行；两轮旧Windows完整后端仍运行。没有重新推送证据提交或取消现有任务，M0 AC0-07继续pending。


98e95dba Intel终态与桌面启动诊断（2026-09-30，confirmed失败/诊断增强，远端根因unknown；2026-10-01 05:24Z）：run36808514086的Intel job110198234330最终failure。完整日志确认后端5343 passed/137 skipped/24 deselected/2 warnings（3268.24s），离线基准21 passed（7.43s），前端5972 passed/454文件，原生worker44 passed/31 deselected/1 warning（1007.22s）；源码HTTP、目录打包整链及AutoFlow-0.1.0.dmg构建通过。失败发生于安装器之后的源码npm run smoke:desktop：authenticated sidecar health等待60秒后为null；尚未执行该次desktop connected或父进程退出断言。之后最终前后端回归未执行，不计通过。PM9构件11142593833上传1080812513字节，日志ZIP SHA256为75b81cba04b7dceec50062c4ec88902f3c6aafd0723a062e8708c6f987dd3765，未下载或本地复算；DMG签名跳过，不作安装/发布声明。

定位确认源码SidecarSupervisor通过uv run启动、内部限时15秒，打包直接执行且内部90秒；外层60秒不能延长内部启动门限。原烟测将bridge不存在、非ready、健康HTTP失败或实例不匹配均折叠为null，并在finally删掉已有sidecar.log，故当前日志不足以判断此次远端是内部超时、依赖/导入失败或其他启动问题。本机原版正常源码桌面冒烟通过；用现有AUTOFLOW_QA_SIDECAR_MODULE注入不存在模块时，真实Electron原脚本同样只报null并退出1，证明诊断缺口，不代表复现远端原因。

仅修订scripts/smoke-desktop.mjs失败分支：删除临时目录前读取状态白名单及现有20,000字符脱敏日志，记录模式/平台和桌面退出信息，然后重新抛出原异常；不输出完整status/token、不改变启动预算、健康断言或清理流程。复用project-smoke-output.redactSidecarLog，未引入新日志框架。独立复审无阻断问题；按非阻断意见将launch未返回时mode标为unknown，避免误报development。修订后真实Electron负例断言state=failed、message含exited with code 1、日志含具体No module named、无READY元数据/顶层token、原健康超时仍保留，全部通过。node --check、diff检查、119项脚本测试通过（2454.91ms，保留Node模块类型警告）；不声称远端根因已经修复。最新d8d3210e矩阵与较早c585a7aa Windows继续保留；诊断候选将普通快进推送已含两个已知失败平台的remediation-m0分支以取得新日志，不把被并发策略取消的旧Windows计为通过。AC0-07仍pending。

诊断修订后的正常真实源码桌面冒烟也通过：desktop connected (development, darwin/arm64)，强停桌面后sidecar实际退出。使用已安装Python环境、UV_NO_SYNC=1及worktree绝对PYTHONPATH；未重构建无变化的前端/后端包。

归属复查候选ARM完整后端及基准（2026-09-30，confirmed子范围；2026-10-01 05:39Z）：run36817654197@d8d3210e3eadf556d9f9603e985f1f622f1960f5的ARM job110226128259完整后端、离线基准和上传步骤22–24均completed/success，当前前端回归进行中；未取终态日志，不推断测试数或声称原竞态再次发生。artifact11143900429（benchmarks-macos-15，3319字节）已实际下载并校验ZIP SHA256 bef0b7260af5b2f83bcf6976a12c605a4d873249ab3d223b637ceab48c09bac1，与API元数据一致。三组报告/manifest配对、sourceBefore/sourceAfter精确d8d3210e且dirty=false/sourceDirty=false/comparable=true、规模断言均通过。10000行领取键/字段597.106/835.400ms，1000轮5000节点框架0.302ms/节点和5.001事件/节点，1000事件提交p50/p99为1.399/2.431ms；macOS15.7.9 ARM、3逻辑CPU、7GiB、Python3.11.9、SQLite3.45.1。每场景一次，不作跨运行性能升降或五样本结论。最新诊断候选775a1cff的完整验收仍在运行；本次不推送纯证据提交，AC0-07保持pending。

归属复查候选ARM源码链路（2026-09-30，confirmed步骤级子范围；2026-10-01 05:59Z）：run36817654197@d8d3210e3eadf556d9f9603e985f1f622f1960f5的job110226128259，真实worker恢复/共享Sheets领取/人工过期竞态选集、真实内核HTTP冒烟及源码桌面管理链步骤27–29均completed/success，已通过Jobs API逐项核对；当前后端可执行文件构建30运行。尚未读取终态完整日志，不推断测试数量或截图内容；源码桌面管理链不替代待运行的打包运行时整链。最新775a1cff三平台均进入完整后端回归，保留d8d3210e Intel/Windows及c585a7aa Windows仍在完整后端回归。本次未发现新失败，不将运行中或旧候选单项成功计为最新矩阵通过；M0 AC0-07与默认分支黄金流程仍pending，M1生产实现未开始。本记录仅本地提交，不推送触发重复矩阵。

最新诊断候选ARM完整后端与基准（2026-09-30，confirmed子范围；2026-10-01 06:03Z）：run36820172667@775a1cffaa934b977d898f2a67341edccc65b8a9的job110233924148完整后端、离线基准及上传步骤22–24均completed/success，前端回归运行；未获取终态日志，不推断测试数。artifact11144220276（benchmarks-macos-15，3332字节）已下载，ZIP SHA256 4362a1e4c6afe2eab1c0eed736f824eb0d219f4bd6581afb6ff8c3336d4f36a4与API一致。三组report/manifest逐对断言提交来源前后精确775a1cff、dirty=false/sourceDirty=false/comparable=true、repetitions=1/concurrency=1及规模正确。10000行领取键/字段628.585/822.518ms，1000轮5000节点框架0.297ms/节点和5.001事件/节点，1000事件提交p50/p99为1.188/2.315ms；macOS15.7.9 ARM、3逻辑CPU、7GiB、Python3.11.9、SQLite3.45.1。每场景仅一次，不作为跨运行性能改善或五样本证据。保留d8d3210e ARM的backend:build/package:dir已success，打包整链运行；其余Intel/Windows完整后端仍运行，最新全矩阵与AC0-07继续pending。本条仅本地记录，不推送重复触发CI。

归属复查候选Intel完整后端与ARM打包链（2026-09-30，confirmed步骤级子范围；2026-10-01 06:16Z）：run36817654197@d8d3210e3eadf556d9f9603e985f1f622f1960f5的Intel job110226128439后端完整回归、离线基准及上传22–24均success，当前前端回归运行；终态日志尚未读取，不推断计数或声称同一EPERM/归属竞态再次发生。artifact11144222164（benchmarks-macos-15-intel，3334字节）已下载，ZIP SHA256 3c70bab17e33e81d90a32e156bfab912b8e1bfd1fee52f13ad6f95f44c2c0114与API一致；三组report/manifest逐对断言来源前后精确d8d3210e、dirty=false/sourceDirty=false/comparable=true、单次单并发及规模正确。10000行领取键/字段1718.580/2716.610ms，1000轮5000节点框架1.548ms/节点及5.001事件/节点，1000事件提交p50/p99为5.249/7.903ms；macOS15.7.9 x86_64、4逻辑CPU、14GiB、Python3.11.9、SQLite3.45.1。每场景仅一次，不作跨运行性能改善或五样本结论。

同候选ARM job110226128259后端构建、目录打包、打包sidecar整链、安装器构建、基础桌面和浏览器管理冒烟步骤30–36，以及OpenAPI/Ruff/mypy/strict类型债务37–40均经Jobs API核对success，当前最终前端41运行；最后后端42和构件上传43尚未完成。不推断安装、签名、截图内容或整体通过。最新775a1cff ARM已通过前端25和构建26，真实worker27运行；两候选Intel/Windows剩余任务与c585a7aa Windows仍待终态。M0 AC0-07和默认分支黄金流程继续pending，本条仅本地证据提交。

交接终态补证（2026-09-30，confirmed 单候选单平台）：d8d3210e的ARM job110226128259已completed/success，完整日志确认两轮后端各5348 passed/137 skipped/24 deselected/2 warnings（1863.17s、1573.09s），两轮前端各5972 passed/454文件，真实worker44 passed/31 deselected/1 warning（541.65s），基准21 passed（2.84s）。PM9 artifact11145965448为890808358字节，上传日志摘要2182acea8531beffe775bfe34c57fca6eafaa8f4cb87dd655979cb3716f88c5f；未下载或本地复算大ZIP。用户要求提交并交接给另一agent，随后明确授权推送baseline；本轮合并远端d45e8bc3/fb06fe60新增文档，保留整改r2索引及独立E计划，未新增业务改动。后续以[交接文档](2026-09-30-remediation-handoff.md)与实时Git/CI为入口；baseline推送不等于M0验收通过，AC0-07仍pending。
