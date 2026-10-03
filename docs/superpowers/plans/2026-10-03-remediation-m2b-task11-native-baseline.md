# M2B Task 11：native-batch-v1 吞吐基线（AC2-19，部分 AC2-01）

- 日期：2026-10-03；状态：confirmed（本机 Windows 采样）；对照用途：M3 优化前基线
- 场景：`apps/backend/tests/golden/test_native_batch.py`（需真实 CloakBrowser，`-m golden -o faulthandler_timeout=0`）

## 固定条件

| 项 | 值 |
|---|---|
| 场景版本 | native-batch-v1（execution profile `ledger-batches-writeback-v1`） |
| 数据 | 200 行（`AUTOFLOW_NATIVE_BATCH_ROWS`），1% 永久 404（fault seed `gone-1pct-v1`） |
| 流程 | 打开条目页 → 读标题 → 版本可省写回本行 |
| 领取 | claimMode=unprocessed，failurePolicy=thresholds，retryBudget=3，退避 [1,1] 秒；每批 100 单位，共 2 批 |
| 并发 | 2；每任务新建临时浏览器环境；realWrites |
| 环境 | Windows 11，CloakBrowser chromium-146.0.7680.177.5，代码 3a869cf7 + 本场景文件 |

## 结果（5 次，每次全新应用与数据库）

| 样本 | 成功行/分钟 | 尝试/分钟 | 循环延迟 p99 (ms) | 成功 | 隔离 | 总尝试 |
|---|---|---|---|---|---|---|
| 1 | 14.458 | 14.896 | 70.4 | 198 | 2 | 204 |
| 2 | 13.367 | 13.772 | 93.0 | 198 | 2 | 204 |
| 3 | 13.367 | 13.772 | 82.9 | 198 | 2 | 204 |
| 4 | 13.533 | 13.943 | 102.0 | 198 | 2 | 204 |
| 5 | 13.394 | 13.800 | 107.6 | 198 | 2 | 204 |

中位数：成功 13.39 行/分钟，循环延迟 p99 93.0 ms。每次都满足：正常行各尝试 1 次并写回；404 行恰好 3 次后隔离；无漏行、无重复。
原始报告在 `tests/benchmarks/results/`（不入库，见整改规则 7）。

## 未覆盖 / 风险

- AC2-01 要求一万行 G2；本机按当前速度约 12 小时/次，未执行。数量可用环境变量放大，留给 CI/长时间机器。
- 吞吐主要受"每任务新建浏览器环境"限制；M3 以此为对照，不与 M0 不同口径的数字相除。
- 循环延迟 p99 在 70–108 ms，高于空载；M3 需关注（整改规则 3 的监测项）。
