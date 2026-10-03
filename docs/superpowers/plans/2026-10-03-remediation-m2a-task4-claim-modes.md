# M2A Task 4：领取模式、批次处理单位上限与退避等待 步骤级计划

- 日期：2026-10-03；状态：执行中。上位：[M2 规格](../specs/2026-09-30-remediation-m2-business-model-reliability.md) R2-03/R2-04/R2-05/R2-07；[任务级计划](2026-09-30-remediation-m2-business-model-reliability.md) Task 4。

## 代码事实（2026-10-03）

- 领取分两段：`_prepare_data_claim`（锁内冻结尝试身份）→ 锁外 `select_required` 选候选 → `_commit_data_claim`（BEGIN IMMEDIATE 内重验、建 Task 与租约）。
- 每次推进先 `_release_terminal_leases`（Task 3 投影在此）再领取，所以领取时处理记录已反映刚结束的任务。
- 调度循环最长 30 秒自醒一次；`noMatch` 且无活动任务时关闭领取开关，批次随后完成。
- 批次上限 `maxTasks` 现按任务数计。

## 设计

1. `runPolicy` 新增可选 `claimMode`（unprocessed/cycle/retryFailed）、`retryBudget`（整数 ≥1，默认 3）、`retryBackoffSeconds`（非空正整数数组，默认 [60,300,1800]）。**缺省 claimMode 按 cycle 解释**（R2-07 存量迁移，不改写数据）；界面新建自动化默认 unprocessed。
2. 领取资格（领域纯函数 `claim_eligibility(entry, mode, now)`）：
   - 所有模式先排除 needs_review、quarantined、skipped；
   - next_eligible_at 晚于现在 → 等待（不可领）；
   - unprocessed：无记录、pending、failed_retryable；cycle：另加 succeeded；retryFailed：只 failed_retryable。
3. 候选过滤只作用于主处理输入；参考输入不做处理记录过滤（R2-03）。在 `_candidates` 解析租约身份后按完整作用域（含 Sheets 命名空间）过滤，处理记录按表与代次一次预读。
4. 提交时在写锁内再查一次主单位资格（防止人工跳过/核实与领取竞争），不合格返回 staleSelection 重选；合格则确保处理记录存在并登记批次处理单位。
5. 数据批次的 `maxTasks` 按本批纳入的**不同主处理单位**计（R2-05 maxRows），同一单位重试不额外占数；参数批次与无主处理输入的批次仍按任务数。
6. 等待：`noMatch` 时若本批成员中存在 failed_retryable 且未到期的单位，不关闭领取开关，记录 `{status: waiting, waitUntil}`；调度循环自醒后继续领取；停止批次照常关闭开关。重启后从处理记录与开关状态恢复。
7. 前端运行策略：领取方式选择、单行最多尝试次数。

## 步骤

1. 领域：资格函数 + runPolicy 校验（单元测试）。
2. 候选过滤 + 提交重验 + 处理单位登记（真实 SQLite 集成测试：三种模式、阻断状态、参考输入不受影响、Sheets 命名空间作用域）。
3. 上限按单位、等待不提前完成、到期继续、停止不再领取（调度器集成测试，用可控时钟或直接改 next_eligible_at）。
4. 前端运行策略编辑器 + 契约生成。
5. 回归、`.ai` 记录。

## 实施修订（2026-10-03，回归后）

- 存量自动化（缺 claimMode）单独为 `legacyCycle`：保留规格要求的全部安全门禁（needs_review/quarantined/skipped 不领取；页面失败按预算隔离；结果不明转人工），但**不加**再次可用等待、批次上限仍按任务数计。原因：项目回归中 PM9 已验收的"同批连续复用同一行""不限批次反复领取最后一行"等行为依赖这两点；R2-07 只要求不保留"绕过安全门禁"的行为。显式选择 `cycle` 时才有 60 秒再用间隔与按行计数。
- 批次上限已用完时，仍允许领取本批已纳入、等待重试的单位（以候选限制实现），到期前进入等待。
- 坏的主处理行（自身取值不合法、身份可确定）隔离后继续选下一行（R2-17，Task 5 一并实现）。
