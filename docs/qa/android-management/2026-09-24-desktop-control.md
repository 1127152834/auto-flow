# 真实桌面控制与进程清理回归

- 日期：2026-09-24；状态：真实桌面控制链 confirmed；本轮完整软件门槛通过，T05/AC05/AC06通过，AM1/总目标仍 partial。
- 基线：`codex/android-management-complete@5eedb18e` 加本次修复。
- 环境：Apple Silicon macOS、生产 Electron、真实 Lima/ReDroid；隔离数据目录 `/private/tmp/autoflow-android-desktop-qa-20260924`。
- 自建设备：`bf8fe420-30c6-4996-8255-98c59a44742e`，720×1280、1 CPU、1536 MiB、持久卷；基础镜像固定 `sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b`。没有 GApps/账号验收声明。

## 真实失败与 RED → GREEN

1. `0c67bffc` 引入的进程组清理在命令正常返回后也执行。由 `adb connect` 启动的 daemon 同属该进程组，随后被杀；桌面反复出现 `daemon not running` 与 `no such device`。新增真实子进程持续写入测试，`run`/`run_file` 两项先因子进程被杀而超时失败。共享函数改为仅异常、取消、超时路径清理进程组；正常成功保留命令启动的后台服务。运行时集合 `65 passed in 6.29s`，包含原四项取消/超时停止后代写入回归。
2. 原生窗口取得焦点时触发页面 blur，旧 generation 的 release 输入仍会发送，页面误报“控制权已变化”。新前端测试先观察到一次不应发送的 release 而失败；共享输入入口在切端期间停止接受新输入。已有输入队列仍先排空，后端切端继续释放按键/触点。
3. 切回页面时，旧 heartbeat 与切端重叠，租约响应把新会话误标为未知。新测试先出现“控制会话状态未知”而失败；页面切端前取消旧心跳查询、切端期间暂停轮询、查询 key 加 generation。正常心跳失败仍保留 unknown 与输入锁定保护。两文件定向 `41 passed in 14.95s`。

## 已观察的真实链

- 页面完成基础镜像登记、标准模板创建、单实例创建并启动；初始启动操作完成后，阻塞提示消失、设备 ready。
- 进程清理修复后，嵌入控制显示“手动控制中”“由你独占操作”，真实画面可见；最近任务/主页按键返回“按键已发送”。
- 切到原生 scrcpy，首次 PID46276；离开详情、切到总览后仍存活；返回模块识别同一控制会话。用户式显式“结束控制会话”后该 PID消失，设备恢复空闲。
- blur 修复后重建并重跑：原生 PID67900，切端未出现旧 generation 输入错误；离开模块后窗口仍保留，返回可读取会话。随后切回时发现上述 heartbeat 竞态，故这一轮不算完整往返验收通过。
- 一次 QA 使用了重新编号前的 AX index，误点击 launcher 的启动按钮；页面返回“应用不存在或没有启动入口”，未声称该应用启动成功。后续操作重新获取完整 AX 树。
- [嵌入状态](2026-09-24-desktop-control/embedded.txt)、[离开模块](2026-09-24-desktop-control/left-module.txt)、[保留原生状态](2026-09-24-desktop-control/native-retained.txt)、[原生截图](2026-09-24-desktop-control/native.png)。这些是实际 CUA 观察，未通过 mock 生成。

## 归档保护复验

`apps/backend/.venv/bin/python docs/qa/android-management/scripts/restore-failure-smoke.py --allow-device-mutation` 实际 exit0，见[JSON](2026-09-24-desktop-control/restore-regression.json)。真实 16 MiB tmpfs 填满、恢复任务取消、损坏备份三场景均保持隔离；取消后部分目标数据稳定为5251584 bytes；重启及 recover 不能释放未完成恢复。新请求恢复成功，源卷/目标数据哈希一致、原备份不变；自建容器/卷/备份及私有挂载清理完成。

## 最终桌面与断线重跑

最终构建完成嵌入→原生 PID90530→离开安卓页到总览→返回读取既有会话→切回嵌入；原生进程关闭、generation从10推进至11，嵌入按键返回“按键已发送”，未再出现切端/心跳误报。见[离页](2026-09-24-desktop-control/final-left-module.txt)、[保留原生](2026-09-24-desktop-control/final-native-retained.txt)、[切回嵌入](2026-09-24-desktop-control/final-embedded-return.txt)、[进程与版本](2026-09-24-desktop-control/final-switch.json)。

第一次只终止该实例身份匹配的 SSH PID90388，页面显示“画面连接已断开，请重新打开设备”并禁用按键；但结束控制时，离线 ADB 无法删除 scrcpy 暂存文件，导致会话继续占用。这是真实产品缺陷，未计通过。新增断线清理测试先2失败/1通过；修复为：转发删除失败后读取 host forward 清单，仅在格式有效且目标端口确实不在时继续；删除随机 jar 失败后经生产 inspect 归属校验，用 Docker 删除同一容器内本次文件。转发仍在、结果不可解析、外部容器均保持失败隔离。增加清单格式用例后，运行时/控制/清理集合91项通过。

加载修复后重新建立会话，核对数据库 PID/birth，仅终止本实例 SSH PID10362；页面锁定输入。点击结束控制后，实际 Docker `test ! -e` 确认本次 jar 消失，数据库 `ownerRunId=null/control=idle/processes={}`；重新打开设备进入手动控制，主页按键可用；再从嵌入控制直接导航总览，正常释放占用。见[断线与清理核实](2026-09-24-desktop-control/final-disconnect.json)、[重连状态](2026-09-24-desktop-control/reconnected.txt)、[嵌入离页](2026-09-24-desktop-control/embedded-left-module.txt)。此为真实单实例 SSH/ADB 链路中断，不代表关闭整台 Mac 网络或 APK 写入中断已验。

最后关闭自建 Electron/sidecar，经完整认证 HTTP 生命周期删除该测试实例与数据卷，再用生产 runtime.verify_deleted 核实为missing；见[清理结果](2026-09-24-desktop-control/cleanup.json)。未删除基础镜像或任何其他设备。

## 软件门槛与未完成项

| 命令 | 实际输出 |
| --- | --- |
| `apps/backend/.venv/bin/pytest apps/backend/tests/unit/test_android_stream_cleanup.py apps/backend/tests/unit/test_android_runtime.py apps/backend/tests/unit/test_android_console_lifecycle.py -q` | 91 passed in6.22s。 |
| Node22：`npm run test --workspace @autoflow/desktop` | 424 files、5631 passed，333.39s，包含审查新增回归。 |
| Node22：`npm run typecheck --workspace @autoflow/desktop && npm run lint --workspace @autoflow/desktop && npm run openapi:check && npm run build --workspace @autoflow/desktop` | exit0；11751 modules；built in50.26s。既有Rollup注释/拆包提示。 |
| `apps/backend/.venv/bin/ruff check apps/backend/src apps/backend/tests`；`python -m compileall -q apps/backend/src` | exit0，All checks passed；编译无输出。 |
| `apps/backend/.venv/bin/pytest apps/backend/tests/integration/test_migration_heads.py -q`；Alembic heads | 2 passed in0.61s；唯一am01_management_operations。 |
| 完整后端 `.venv/bin/pytest -q` | 1 failed、4040 passed、26 skipped、2 warnings，952.76s；首次OpenAPI请求5秒超时，详见下文。 |

旧一轮完整后端在流清理修复前运行，有 `test_b6_external_http_worker.py::test_stopping_worker_interrupts_in_flight_http_request` 计时失败（1.206s超出<1s）；为加载新代码而显式中止，最终1failed/2438passed/22skipped/1warning、994.64s。该项单独复跑1passed in2.29s，未更改业务或断言；后续独立临时目录完整重跑4041项通过，未调整上述断言。旧前端全量亦因新增心跳修复被显式中止，由上述最终完整通过结果替代。

精确200%/指定窗口尺寸、应用写入期间ADB断线/进程SIGKILL、前台五实例指标及GApps条件不由本报告关闭。既有三份Studio文档SHA-256与原值相同；本次无契约或表结构变更，不新增空迁移。独立新修复审查见下节；后端完整重跑终态见下节。


## 独立增量审查

依据 Superpowers requesting-code-review，由独立审查代理只读检查本次生产与测试 diff，未操作设备或修改文件；发现2项Important/P2、无Critical：

- 只读切端不增加generation，旧成功heartbeat缓存可能在切端结束后覆盖新endpoint。最初测试夹具设备ID不符未计为RED；修正后快速心跳也能掩盖问题，因此明确延迟新心跳，双向切端均在最终端点断言失败。修复将endpoint加入查询key，保留generation。
- 旧backend的切端请求挂起时，页面全局暂停标志会抑制新backend新会话的心跳；旧finally又可能解除新切端暂停。新测试先因新会话没有heartbeat而失败；修复将transition绑定client、instanceId及会话快照，切backend清理旧记录，旧回调不能影响新身份。

两项修复后的页面/控制组件定向44passed in6.62s；覆盖旧响应、同generation端点切换、新backend心跳恢复及旧finally不能解除新切端暂停。审查代理对进程清理和断线清理无其他高优先级发现，并独立复验运行时/stream清理69passed in6.06s。最终前端全量已重新执行，424文件/5631项通过；类型、lint、OpenAPI和构建exit0。未沿用先前5628项作为最终版本证据。


## 审查修复后的最终构建实测

另建实例`473df9d4-3277-4c89-92ab-30a08b3510c2`（QA Final Control Review），最终构建真实手动控制→原生PID56471/generation3→总览保留→返回切回页面/generation4→主页按键已发送→总览释放。数据库为ownerRunId=null/control=idle/processes={}，原生PID已消失。关闭本轮Electron后，通过完整认证HTTP删除自建设备和卷，生产verify_deleted返回missing。见[资源与清理](2026-09-24-desktop-control/reviewed-build-smoke.json)、[原生保留](2026-09-24-desktop-control/reviewed-native-retained.txt)、[页面输入](2026-09-24-desktop-control/reviewed-embedded-return.txt)、[离页](2026-09-24-desktop-control/reviewed-left-module.txt)。

最终后端第一轮完整执行出现一次`test_sidecar_shutdown.py::test_open_sse_does_not_block_shutdown_or_worker_cleanup[True-host]`失败，发生在准备阶段GET /openapi.json等待响应头超过5秒；尚未开始SSE/worker/关闭动作。独立重跑整个文件5passed in34.49s。检查当前代码，OpenAPI首次同步构造全部schema并缓存；Android控制进程清理不在此调用路径。未修改该测试或生产超时，未据单独成功抹去全量失败。同期存在本轮Node测试/构建及另一工作区pytest进程，资源竞争是待验证解释，非已确认根因；单独测量317个paths的首次schema构造1.472s、缓存读取0.000001s，未复现5秒超时；原pytest临时stderr已被回收。随后以唯一basetemp重跑完整后端，exit0、4041passed/26skipped/2warnings in823.04s；全量通过不追认早前两次计时失败已确定根因。


## 最终门槛与剩余风险

- 后端最终命令：`cd apps/backend && .venv/bin/pytest -q --basetemp=/private/tmp/autoflow-android-final-isolated-pytest-20260924`，exit0；4041 passed、26 skipped、2 warnings，823.04s。警告为Starlette anyio弃用和故意重复APK manifest负向测试。原始日志`/private/tmp/autoflow-android-final-isolated-pytest.log`。
- 桌面最终命令：`npm exec --offline --yes --package=node@22.23.2 -c 'npm run test --workspace @autoflow/desktop'`，exit0；424files、5631passed，333.39s。类型/lint/OpenAPI/build亦在相同Node22环境执行，上表四项串行命令exit0，build50.26s。
- 文档核验：102步骤仍83passed/16not_run/3blocked；297个修改文档本地链接存在；全部QA JSON可解析；暂存区diff检查通过。三份Studio原SHA256保持，未暂存。
- T05与AC05/AC06可按本轮证据关闭；本轮两台桌面设备及恢复回归自建资源均清理。完整目标仍active/partial：T06精确200%与窗口尺寸/旧temporary兼容，T07/T15应用写入时ADB/HTTP进程中断和桌面确认流，T09桌面镜像内容删除/拉取断线核实，T12回退演练与历史RED缺证，T14/T16前台/隐藏页探测指标，T20最终完整矩阵尚有not_run。十台最低8192MiB超过Lima7921MiB、专用GApps镜像/账号/商店链为blocked。
- 已修复增量审查的2项Important，无尚未处理的Critical/Important发现；这不宣称未执行场景已通过。早前全量两次计时失败保留为风险记录，独立及最终完整重跑均通过，没有放宽超时或跳过测试。
