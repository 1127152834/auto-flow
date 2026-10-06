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
