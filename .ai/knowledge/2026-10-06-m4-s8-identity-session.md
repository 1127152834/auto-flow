# M4 S8 perIdentity：切片验证与基准记录

- 日期：2026-10-06；来源：本机 Windows，同机同数据量，运行 `python -m tests.benchmarks.<名称>`；状态：confirmed（逐切片追加）
- 决定见 `.ai/decisions/2026-10-06-m4-s8-per-identity-v1-keep-instance.md`

## S8-1 身份独占与领取门禁（2026-10-06）

- 改动：`project_environment_instances.identity_id` + 部分唯一索引（未释放 = 状态不在 `cleaned`/`retained_unsaved`）；
  预约时拒绝同身份第二个实例（`ENVIRONMENT_BUSY`，details.holderKind=identity）；领取门禁让被占身份的行等待（`temporarilyBusy`）；
  准备→提交之间被占用由重新校验兜住；有未释放实例的身份不能重新生成种子或删除（`IDENTITY_IN_USE`）。
- 纠正架构师稿：索引不豁免 `closed`——`quiesce_instance` 把实例置为 `closed` 时工作副本和占用都还在，直到 `cleaned` 才释放。
- 基准（非身份路径，CPU 空闲约 5%，改前 = 暂存 `src/` 的改动后重跑）：

| 指标 | 改前 | 改后 |
|---|---|---|
| claims-10000 created_order | 4.636 ms | 4.863 ms |
| claims-10000 field_filter | 16.244 ms | 17.096 ms |
| claims-10000 field_order_full_scan | 27.482 ms | 28.574 ms |
| claims-10000 key_order | 4.860 ms | 5.823 ms |
| claim-loop-lag threaded claim | 11.124 ms | 12.183 ms |

  差异在单次样本噪声内（约 5–15%，key_order 的绝对差 1 ms）；身份路径每次领取多一条按（项目，状态）索引的查询，未单独测量。
- 测试：`tests/integration/test_identity_exclusivity.py`（24 个含迁移 head），相关回归 289 passed。

## S8-2 持有与重新附着（2026-10-06）

- 状态 `identity_held` = 工作副本保留、浏览器已关闭、没有任务在跑、身份仍被独占。只能从 `closed`（已确认浏览器退出）进入，
  所以保留副本在构造上是静止的，不存在"撕裂的登录状态"。持有时清空 `active_run_id`（使终态清理的 JOIN 看不到它）、
  记录 `held_batch_id`；不进 `LIVE_INSTANCE_STATES`（没有浏览器），进 `BUSY_INSTANCE_STATES`（项目归档/删除不得 rmtree 它）。
- 重新附着在领取事务内一条路径完成：同批次、同环境代次、`runtime_lock_present` 为假（重启后残留浏览器锁则拒绝）、有活动名额；
  通过后直接置 `active`（绝不写 `reserved`，否则 `attach_task_instance` 会 rmtree 后重新恢复，销毁登录状态），
  `instance_use_generation` +1（今天首次让旧 End/保存授权被代次围栏拒绝），占用持有者改为新任务。
- 领取门禁：持有该身份的批次可继续，其他批次、`active`/`closed` 的实例仍让行等待。
- 任务视图：持有中显示"保留中"，已被后续任务接走的旧任务显示 notRequired（不再误报"临时环境已释放"）。
- 增补列 `held_batch_id`（迁移 rm4_instance_identity 内，尚未推送）：持有时记批次，免去门禁与重新附着对任务表的 join。
- 测试：`tests/integration/test_identity_hold.py`（14 个），相关回归 298 passed（唯一失败为本机符号链接权限）。尚无调用方：End 在 S8-4 才会持有。

## S8-3 释放：保存一次再清理（2026-10-06）

- `EnvironmentService.release_identity_instance`：`begin_identity_release`（BEGIN IMMEDIATE 内 `identity_held`→`closing`，与重新附着互斥）→
  `runtime_lock_present` 非等待核实（有锁则停在 `closing`、身份保持占用、记日志，由扫描重试）→ `closed` →
  `retain_on_release` 且目录存在才保存（缺目录记日志、不发布空版本）→ 清理。
- 保存复用 `save_environment`，幂等键 `identity-release:{实例}:{使用代次}`：崩溃后重放同一操作，不会出现第二个环境；
  有环境走 update（版本只 +1，不是每任务 +1），没有走 save_as，名称 = 身份名（≤29 字）+ "·" + 身份 id 前 6 位，
  并通过 `linkIdentityId` 把首个登录挂到身份上（否则下一个任务会从模板重新开始）。
- 保存失败：`STORAGE_FAILED`/`SAVE_GENERATION_CONFLICT` 及其他保存阶段错误 → `retained_unsaved`（副本保留、身份解锁、原因写日志）；
  项目暂时不可写 → 稍后重试；`OSError` → 稍后重试（同一键重放）。
- `release_due_identity_instances`：空闲超时、持有批次已结束、或释放到一半（`closing`/`closed`/有未完成保存操作的 `saving`）；
  只处理 `active_run_id` 为空的身份实例，不碰任何运行中或普通任务副本。尚未接入调度器（S8-5）。
- 测试：`tests/integration/test_identity_release.py`（11 个）。
- 基准（`bench_identity_session`，同一 45 MB 夹具、3 次中位、CPU 空闲，仅文件工作，不含浏览器启动与数据库更新）：

| 任务数 k | perTask（每任务恢复+保存） | perIdentity（恢复 1 次 + 保存 1 次） |
|---|---|---|
| 1 | 3880 ms | 3158 ms |
| 3 | 5394 ms | 3151 ms |
| 10 | 16332 ms | 2845 ms |

  k=10 时环境文件工作减少约 5.7 倍；k=1 的差异是磁盘缓存噪声。perIdentity 的 k 个任务之间只剩一次数据库更新。

## S8-4 End 改为"持有"，失败运行把副本还给身份（2026-10-06）

- perIdentity 的 End（运行 `sessionMode` 为 perIdentity 且实例带身份）不再保存/关闭：worker 仍在发 End 前关闭浏览器
  （协议不变），`quiesce` 确认静止后 `hold_identity_instance`。End 想要保存与否记入 `retain_on_release`（跨任务取 OR，
  之后一次 End 不保存不会撤回）。`recordTargets` 被忽略（台账 `targets=[]`），身份靠 `IdentityRow.environment_id` 带登录；
  仍保留预览运行拒绝保存。只有持有型 End 的载荷多 `holdForIdentity`/`batchId` 两个键，其他 End 形状不变。
- 失败/取消的 perIdentity 运行（worker 已确认清理）：终态清理改走 `dispose_terminal_instance`，`quiesce` 通过后交还给身份
  （`retain=False`，不新增保存意图）；`timed_out`/`interrupted`（清理确认靠推断或授权被撤）仍丢弃且不保存。
  `quiesce` 不过则副本留在原状态、身份保持占用，下一轮重试，不会降级为丢弃。
- 两处终态清理（`cleanup_terminal_tasks`、调度器 `_cleanup_terminal_instances`）统一调用 `dispose_terminal_instance`。
- 测试：`tests/integration/test_identity_end.py`（11 个；去掉 End 改动后 3 个红）；相关回归 278 passed（唯一失败为本机符号链接权限）。
- 已知上限：End 已受理但进程在 hold 之前崩溃时，实例仍 `active`，被未决 retain 操作保护、身份保持占用，需人工处理
  （与现有"中断的保留型 End"同语义）。

## S8-5 释放扫描接入调度器（2026-10-06）

- `ProjectBatchScheduler.tick` 在终态清理之后启动后台协程 `_release_idle_identities`：同一时刻只有一个在飞；
  在 `QuiesceGate.mutation()` 内用 `asyncio.to_thread` 调 `release_due_identity_instances`（目录拷贝与 rmtree 不上事件循环，规则 3）；
  释放数 > 0 时 `wake()`，让在等该身份的批次立刻重试而不是等 30 秒。`shutdown()` 等待在飞的扫描，不遗留线程。
- 关键：扫描不放进终态清理的 `if active is None` 分支——那个分支只在没有任何运行时才执行，放进去的话只要一直有别的批次在跑，
  已结束批次的保留实例就永远不释放、身份永久被占。
- 触发条件（在 `due_identity_instances`）：空闲超过 120 秒（`identity_idle_seconds`）；持有批次已终态；`closing`/`closed`/
  有未完成保存操作的 `saving` 的重试。重启后保留副本在持久化意义上始终静止，首轮按同样规则处理；
  有运行锁（残留浏览器）则既不保存也不被复用，停在 `closing`，锁消失后释放。
- 测试：`tests/integration/test_identity_sweep.py`（7 个）。

## S8-6 配置面（后端）：sessionMode=perIdentity 的保存、启动与冻结（2026-10-06）

- 保存：HTTP 契约 `RunPolicy.sessionMode` 加 `perIdentity`（`generated.ts` 由 `npm run openapi:generate` 重新生成，一行变化；
  本机 `uv run` 会因 dlib 无法同步，用 `UV_NO_SYNC=1` 运行生成脚本）。`session_source_error` 统一规则：pool 只配"按浏览器配置新建"，
  perIdentity 只配"按记录的身份运行"，错误文案用业务语言。
- 校验：`session_pool_blockers(document, mode)`——perIdentity 下"结束时保存环境"不再是阻断项（那正是这个模式的用途），
  节点自带浏览器环境、人工处理节点（v1 不支持）阻断；pool 的规则与文案不变。`validation` 对两种模式都检查，状态为 blocked。
- 启动：`validate_batch_start` 现在读 `sessionMode`：启动覆盖不能把 perIdentity 改回别的环境来源，也补上了 pool + 覆盖的既有缺口。
  协调器对所有非默认会话模式都把冻结工作流传给资源解析（原来只在节点模式才传，非节点模式下启动时从不重检阻断项）。
- 冻结：`freeze_input_environment` 的两条返回路径原先都丢 `sessionMode`——inputIdentity 必然走这条路径，perIdentity 会静默退化为
  perTask；现在带上并有断言测试。运行期不需要再改：`_session_key` 只认 pool，perIdentity 走每任务一个 worker（v1 预期）。
- 测试：规则、校验、批次启动、冻结共 7 个新增失败用例转绿；相关回归 235 passed。
- 批次级整链路（真实 End、hold/重新附着/释放）用 G1 的 perIdentity 变体验收（S8-7），不另建假 worker 装配。

## S8-7 前端与真实浏览器验收（2026-10-06）

- 真实浏览器黄金场景 G2（`tests/golden/test_g2_shared_identity.py`；站点用持久 Cookie 模拟登录）：K 个账号各 R 行，
  `sessionMode=perIdentity`、`claimMode=cycle`、并发 K。本机 Windows + CloakBrowser 146：
  3 账号×3 行 109 秒通过；5 账号×4 行 150 秒通过。断言：批次 1 每账号第 1 行无 Cookie、其余行都带 Cookie（共用同一浏览器目录）；
  `prepare_instance` 次数 = 账号数、`restore_generation` = 0；每账号 1 个实例，使用代次 = 行数，批次结束后释放扫描保存一次
  （每账号 1 个环境、版本 1）、副本 `cleaned`；批次 2 每次访问（含各账号首行）都带 Cookie，`restore_generation` = 账号数，版本 2。
- 前端：运行设置"浏览器会话"改为三选一（独立浏览器 / 任务之间复用浏览器（不登录采集）/ 同一账号共用浏览器并保留登录状态），
  不适用的选项置灰；环境来源改变使当前会话模式不合法时自动退回"独立浏览器"；表单校验与后端同口径；
  批次启动框对按记录的身份运行的自动化不提供"临时环境"覆盖；环境页状态表增加"账号保留中"。文案无内部术语（规则 6）。
- 未覆盖/已知上限：服务关闭时不额外保存（保留副本下一次启动由释放扫描保存）；`project_manual` 节点不支持；
  跨批次同身份等待最长到持有批次结束或空闲 120 秒；S8b（浏览器保活）未做。

## M4 退出前复测（2026-10-06）

- native-batch-v1（pool，200 行，并发 2，5 样本）同机同时段 A/B：S8 之前（3ea4d314，worktree 运行）吞吐 146/164/180/195/205，中位 180；
  S8 之后（396af4c5）187/193/190/168/154，中位 190；另一轮 176/173/170/162/118。循环延迟 p99 两侧都在 25.8–29.3 ms。
  S8 之后一轮出现的 `attempts == 2`（1 行）与同一样本里 1.5 s 事件循环停顿同时出现，该样本开始前我刚递归删除了一个 worktree
  （大量磁盘写入），静置后重跑 5 个样本全部满足每行恰好 1 次尝试；该轮不作为数据。结论：S8 无可测回退，机器基线本身在 180–212 波动。
- G1 200 行（`AUTOFLOW_G1_ROWS=200`）：任务数上限最大 100，所以每个循环用一个"不限次数"批次（`maxTasks: null`）；55 分 47 秒通过。
- G3：首次绑定不看身份地区的缺口（见验收文档"已知限制 1"），以及批次任务名额按"被领取的行单元"计数——前置失败的行不消耗行预算，
  但占用本批次的名额，留给下一批次重新处理。
