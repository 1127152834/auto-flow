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
