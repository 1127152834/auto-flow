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
