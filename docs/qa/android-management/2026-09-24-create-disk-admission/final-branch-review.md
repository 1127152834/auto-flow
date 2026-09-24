# Android 管理完整分支最终只读审查

日期：2026-09-24。状态：reviewed，需修复。置信度：高（逐项证据见下）。

- Base：`a92f0688f206d4339ff4468c1871f3ccdd6816dc`
- Head：`ef0af03ffd34df2d7b86a2f70496cc3f05765c15`
- Worktree：`/Users/zhangtiancheng/.codex/worktrees/android-management-complete/autoflow`
- 模板：Superpowers `requesting-code-review/code-reviewer.md`。
- 基线：用户原始计划 `/Users/zhangtiancheng/Downloads/2026-09-19-android-emulator-management.md`、仓库 `docs/superpowers/specs/2026-09-19-android-emulator-management-design.md` 与同名实施计划；实际执行授权和迁移起点采用 `.ai/decisions/2026-09-22-android-management-execution.md`，不沿用历史 `5f07e2ad` / `pm07_environments`。

本次按产品源文件分段审查 AM1–AM4 的管理路由、生命周期/控制台、持久操作和资源仓储、镜像、批次和容量、观察器、备份归档/恢复/清理、诊断导出、页面装配和会话/维护组件；结合相关测试与 QA 索引。没有逐字复审 diff 中全部 QA 日志或生成类型的每一行，不把统计量当作业务验收。未派生子代理，未修改产品、索引、HEAD 或受保护的 Studio 三文件；仅生成此报告，临时复现使用 `/private/tmp` 和临时 SQLite。

## Strengths

- 继续复用 Mac/Lima/ReDroid 和现有生命周期执行者，未引入新的 Android 工作流执行链；新增操作表从实际 `0019_recording_commands` 增量演进，并有工作区/requestId 唯一约束。
- 备份归档文件先 staging、校验、fsync/原子发布，目录记录与操作成功在同一事务落盘；恢复核对清单、摘要、精确镜像、持久意图、目标代次/归属和空卷，不覆盖源实例。
- GNU tar 路径保存已验证的 UID/GID/mode/xattr/ACL；安全归档校验覆盖硬链接、符号链接链、路径和特殊文件；恢复中断保持 pending 隔离。
- 生命周期容量计入真实运行容器和持久预留，未知内存限额拒绝准入；本轮磁盘改动区分宿主工作区、Lima backing filesystem 与 Docker 数据盘，并把未知估计的确认冻结到请求。
- 批量管理有冻结目标、独立操作回执、容量探测后的批次重读和未知项禁止重放；默认诊断使用字段白名单，高级日志只保留受限元数据。

## Issues

### Critical (Must Fix)

未确认 Critical。以下五项均为 Important，合并前应闭合。

### Important (Should Fix)

#### I1 — 旧生命周期核实会覆盖新的设备代次及控制归属

- 主位置：`apps/backend/src/autoflow/application/android/verification.py:39`、`:55`、`:68`。
- 关联落点：`apps/backend/src/autoflow/infrastructure/database/android_operations.py:210`。
- 可达过程：历史 start 处于 needs_verification；发起其 `/operations/{id}/verify`，它读取设备后 await inspect。此时另一个请求执行合法 recover，随后创建新的人工会话。旧 inspect 返回后，核实代码把旧设备副本设为 idle；`transition_with_device` 仅对备份 restore 检查设备版本，普通生命周期直接 merge，覆盖当前设备。
- 实际复现：真实 SQLite 仓储 + 真实 AndroidManagement 的 recover + 仓储 claim，只有 runtime IO 受控。最终 **generation 从 4 回退到 2，control 从 manual 变成 idle，ownerRunId 从 new-session 变成 null**；旧操作同时写为 succeeded。
- 影响：新控制会话仍持有其运行时上下文，但数据库失去其归属/代次；后续管理、会话和重启恢复依据互相矛盾。违反 GC-08、AM-R04/R05，不应因“只是查询核实”绕过写栅栏。
- 最小修复方向：核实应用设备投影时复用既有锁，并在数据库事务中按设备代次、当前操作/归属做条件重验；旧操作若已被更新的操作取代，不得覆盖当前设备。不要仅在 UI 隐藏核实按钮。
- 必补检查：上述延迟 inspect→recover→新 claim→旧核实返回，当前代次/owner/control 不变；另保留普通当前操作核实成功测试。

#### I2 — 镜像元数据核实会复活取消登记项，并能覆盖删除回执

- 位置：`apps/backend/src/autoflow/application/android/images.py:349`、`:357`、`:387`–`:388`。
- 公开入口：`apps/backend/src/autoflow/adapters/http/android_management.py:578` 附近 `/images/{identifier}/verifications`；ImageManager 对全部目录项提供“验证”按钮。
- 可达过程：镜像取消登记后仍以 unregistered 墓碑出现在目录；点击普通元数据验证，`verify_server` 不检查生命周期状态，最终无条件将 state 改为 verified/registered。即使使用不支持的检查项、没有运行时探测，也会把状态写为 registered。该方法也不持有其他镜像写路径使用的 runtime lock；await probe 期间并发删除后，旧整行 save 可覆盖删除状态、revision 和 deleteRequestId。
- 实际复现：生产资源仓储中 `unregistered` revision 2 的镜像调用 `verify_server(..., {check: image_metadata})` 后变为 **verified**，没有登记命令。
- 影响：用户取消登记/删除的生命周期决定被只读性质的元数据核实撤销，镜像删除未知结果及其回执也可能丢失，违反 AM-R08 与 GC-08。
- 最小修复方向：复用镜像写锁，在锁内重新读取并限制可验证状态；验证结果与注册/删除生命周期分开更新，不覆盖墓碑或待核实删除记录。登记恢复仍只走显式 register。
- 必补检查：unregistered/deleted/delete_pending/delete_blocked 不被 verify 重新激活；probe 与 delete 交错时不丢删除回执。

#### I3 — 隐藏窗口会停止嵌入式心跳，30 秒后被误回收

- 位置：`apps/desktop/src/renderer/domains/android/pages/AndroidPage.tsx:151`–`:157`。
- 服务端影响：`apps/backend/src/autoflow/application/android/console.py:30`–`:50`，embedded seen 超过 30 秒进入回收。
- 原因：heartbeat 使用普通 TanStack `useQuery` 的 5 秒 refetchInterval，未指定 `refetchIntervalInBackground`；全局 ApiProvider 也没有覆盖该选项。当前安装的 `@tanstack/query-core/src/queryObserver.ts:425`–`:426` 在窗口失焦/隐藏时明确跳过定时 refetch。
- 实际复现：使用当前安装依赖和与生产相同的 QueryClient/QueryObserver 配置，缩短间隔到 10ms，隐藏前 4 次，隐藏后 60ms 仍 4 次，`hiddenHeartbeats=0`。这是依赖行为复现，不冒充真实 Electron 最小化验收。
- 影响：用户切换到其他应用或隐藏 AutoFlow，健康的嵌入式控制会话被当作失联释放；返回后输入失效。规格 AM-R12 明确“页面隐藏时暂停展示轮询，不能顺带停止必要会话心跳”。
- 最小修复方向：让控制心跳在后台继续，展示查询/预览保持暂停；不要增加第二个普通列表轮询器。
- 必补检查：隐藏页面超过租约窗口期间心跳持续、展示轮询停止，重新显示时同会话可继续输入。

#### I4 — 停机备份和源实例删除后的备份恢复没有可达的正式页面入口

- 位置：`apps/desktop/src/renderer/domains/android/pages/AndroidPage.tsx:235`–`:242`、`:477`；`apps/desktop/src/renderer/domains/android/components/BackupPanel.tsx:9`、`:14`。
- 已核对入口：`ManagementOverview` 的 onOpen 只允许 ready；`AndroidPage.open` 再次拒绝非 ready，且是进入 detail 的唯一业务路径。BackupPanel 仅挂在 detail，创建要求 stopped/retained、idle、无控制会话。首页没有独立详情/备份入口，DataMaintenance 只有清理和诊断。
- 可达失败：已停止实例从首页不能直接进入备份；为了访问维护功能先启动/申请控制与停机备份目标相违背。更明确的闭环缺口是：已备份后永久删除源实例，设备查询排除源墓碑，BackupPanel 又始终按当前 deviceId 过滤，因此该备份只出现在清理列表，**无法从正式 UI 恢复为新实例**，尽管后端 restore 支持它。
- 影响：AM-R14/R15 的已实现后端能力在正常维护/灾后恢复场景不可用。BackupPanel 独立组件测试不能证明 AndroidPage 中可达。
- 最小修复方向：增加不申请控制的设备维护入口，或者在现有数据维护区提供停机备份与全局备份目录/恢复动作；复用现有组件和 API，不重做页面架构。恢复选择不得要求源实例仍存在。
- 必补检查：从首页停机实例进入并创建备份；删除源实例后仍可选其备份恢复，且不隐式 start/claim。

#### I5 — 首页“核实状态”错误地只核实历史操作，失败设备无法走 recover

- 位置：`apps/desktop/src/renderer/domains/android/pages/AndroidPage.tsx:402`–`:407`；对应服务端 `apps/backend/src/autoflow/adapters/http/android_management.py:412`–`:413`。
- 可达过程：普通生命周期失败会留下 `control=recovery_required` 与 `operation.state=failed`；后端 policy 只允许 verify。首页点击“核实状态”固定调用操作日志 `/operations/{id}/verify`，该路由对 failed 原样返回，未运行设备 recover、未清理隔离。UI 关闭弹窗后仍只剩“核实状态”，反复点击无进展。没有历史 operationId 的未知设备直接报“缺少待核实操作编号”；create/recover 的 needs_verification 也不在 `verify_lifecycle_operation` 的可核实 action 集合中。
- 实际复现：真实操作仓储和公开 FastAPI 路由，failed start 的 verify 返回 **HTTP 200 / state=failed / control=recovery_required**。这与路由契约一致，问题在卡片的设备恢复动作错误接线。
- 影响：恢复环境或解决容量等失败根因后，用户仍不能从首页恢复、启动或删除设备；规格 AM-R03/R06 已明确 unknown/recovery_required 应有设备检查/recover 入口。
- 最小修复方向：区分“核实这条原操作回执”和“核实/恢复当前设备状态”。卡片当前设备恢复使用既有 recover；历史面板保留原 operationId/requestId 核实且不重放旧写操作。不得将 failed 历史直接改成 succeeded，也不得清空 pending restore/app 安全隔离。
- 必补检查：failed 生命周期、无旧 operationId 的 unknown、恢复中断目标这三类页面路径；前两类能按规范检查，第三类继续禁止启动/备份且允许安全处置。

### Minor (Nice to Have)

无新增阻塞外的风格建议。本次不以重构、源码行数或通用抽象作为问题。

## Recommendations

先一次性完成 I1–I5 的有界修复，新增上述可失败的回归；复用现有锁、事务、recover、查询和备份组件。修复后只重跑受影响测试及工程门槛，最后由根任务协调必要的完整回归；不为这些问题重开 AM1–AM4 架构。

## 验证证据与限制

本审查运行的复现命令：

```sh
cd /Users/zhangtiancheng/.codex/worktrees/android-management-complete/autoflow/apps/backend
uv run python /private/tmp/android-final-review-repro.py
```

真实输出（exit 0 表示三个缺陷断言被成功复现，不是产品通过）：

```text
LIFECYCLE_REPRO {'beforeGeneration': 4, 'afterGeneration': 2, 'beforeControl': 'manual', 'afterControl': 'idle', 'beforeOwner': 'new-session', 'afterOwner': None}
IMAGE_REPRO verified
FAILED_VERIFY_REPRO {'http': 200, 'operationState': 'failed', 'control': 'recovery_required'}
```

心跳依赖复现输出：`{"beforeHidden":4,"afterHidden":4,"hiddenHeartbeats":0}`；使用 node、当前安装 `@tanstack/query-core`、真实 QueryObserver/focusManager、生产查询选项，只有间隔由 5000ms 缩为 10ms。I4 是完整页面入口静态追踪，未声称完成本轮真实桌面复现。

根任务通知的最终 HEAD 软件门槛：后端 `4099 passed / 26 skipped / 2 warnings`，794.17s；前端 `424 files / 5683 passed`，351.96s；type/lint/OpenAPI/build/迁移 exit 0。本审查未重复全量运行；这些通过不覆盖本次复现的交错与页面入口。前端该次实际运行 Node 26.7.0，不能写成已按 Node 22 执行。

根任务提供的真实 Task4 证据为 `docs/qa/android-management/2026-09-24-create-disk-admission/real-create-final.json`；包括八条自建记录的最终清理与缺省确认批次重试保持 failed。这里只承认该链，不扩展为整体验收。Mac 锁屏阻塞新增桌面核验；GApps、十台规模以及既有文档列出的部分桌面/性能验收仍按实际 blocked/not_run 保留。

## Declined to judge

- Android 工作流执行、退役 Studio 恢复：明确在 AM1–AM4 范围外；只核对未因本分支恢复旧执行链。
- Windows/Intel Mac、远程设备、第三方备份导入、跨镜像恢复：规格明确排除，不将其缺失作为本分支缺陷。
- GApps 登录/商店/目标应用、十台真实规模、锁屏期间桌面行为、未完整记录的桌面性能：缺少相应真实条件或本次证据，不伪造通过；由验收矩阵保留缺口，不评价为代码缺陷。
- 大量历史 QA 日志、其他任务所有的 Studio dirty 文档、根任务正在更新的 QA/.ai：不作为被审产品改动；本报告不修改它们，也不从旧 4031 等历史计数推定最终通过。
- 既有 Fleet 取消交错等未建立本范围新增回归证据的疑点：未作为本报告确定缺陷；本次明确问题只限上列五项，不借此发起无界审计。

## Assessment

**Ready to merge? No.**

**Reasoning:** 当前 HEAD 的完整自动化门槛通过，但定向复现揭示设备代次/归属覆盖和镜像生命周期覆盖，页面还存在心跳及维护/恢复入口缺口。五项 Important 修复并复审前，不能批准为 AM1–AM4 完整可交付；即使修复通过，真实外部验收缺口仍须独立标注。
