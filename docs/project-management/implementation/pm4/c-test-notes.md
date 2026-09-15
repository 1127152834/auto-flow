# PM4-C 调度测试先行记录

- 日期：2026-09-16（Asia/Shanghai）。
- 状态：confirmed，仅测试准备；不是 PM4-C 实现或验收通过。
- 来源：唯一计划 `docs/superpowers/plans/2026-09-15-project-management-pm4.md` §3.2、§3.6、C 与自动验收矩阵；实际 coordinator/scheduler/CoreRun/SQLite 代码。
- 运行基线：HEAD `48e5919b1524539269e44f8ac1c698761c140e16` 加共享工作树已有未提交生产变更；不能把结果解释成纯 HEAD 测试。
- 本次独占修改：`apps/backend/tests/integration/test_project_data_scheduler.py` 与本文档。没有生产修改、B 测试修改、QA runner 修改、执行卡修改或提交。

> 历史说明：下文“12 failed, 3 passed”保留测试先行时的真实红灯证据，不能代表当前实现状态。2026-09-16 完成实现后的权威结果见本文末尾“实现完成后的复验”，真实管理端证据见 `c-verification.md`。

## 验证结果

```sh
uv run --directory apps/backend pytest tests/integration/test_project_data_scheduler.py -q --tb=short
# 12 failed, 3 passed in 3.56s
uv run --directory apps/backend pytest tests/integration/test_project_run_dispatch.py -q --tb=short
# 12 passed in 2.39s
uv run --directory apps/backend ruff check tests/integration/test_project_data_scheduler.py
# All checks passed!
git diff --check
# exit 0
```

新文件复用现有 `_setup`、`Worker`、`SyntheticResources`。数据库、批次接受、CoreRun 调度、停止与恢复都是生产实现；worker 为现有合成执行器，不涉及真实浏览器。每个测试 docstring 写明所捕获的生产缺陷。没有 xfail，没有伪造缺失接口。

| 测试 | 当前层级与证据 | 最小生产接点 |
|---|---|---|
| acceptance `[1]` | 业务断言红：start 已建 1 个 Task，要求 0 | coordinator 数据分支只提交 Batch/PreparedContent/Operation；任务创建移到实际领取 |
| acceptance `[3]`、reusable `[3]`、failure `[False/True]` | 准入红：`数据输入首批次当前只支持一个任务` | coordinator 单任务限制与 scheduler 数据分支 |
| acceptance/reusable `[None]` | 领域校验红：`maxTasks` 必须 1–100 | BatchStart/rules 明确区分 null 与省略，参数型规则继续保持 |
| busy | 准入红：第二批次 `INPUT_TEMPORARILY_BUSY` | start 不领取；scheduler 持久 blocked，lease 释放后重新选择 |
| noMatch | 准入红：`INPUT_NO_MATCH` | start 接受冻结请求；scheduler 在无活动任务时确认耗尽 |
| stop acceptance | 事务断言红：`status=stopping`，`claim_gate_state=open` | `_accept_stop` 的现有 BEGIN IMMEDIATE 中同时关领取门闩 |
| authoritative terminal | 业务断言红：CoreRun/Batch 已 completed，但两条 lease 未 released | 权威 CoreRun 终态到 lease 状态投影；不能从 Task 业务成功推导记录业务状态 |
| restart `[True]` | 恢复断言红：新 dispatcher 已确认 interrupted，lease 仍未释放 | 恢复完成的权威 CoreRun 事实到 lease 释放 |
| restart `[False]` | 绿：恢复异常保留 reconciling、两条未释放 lease，选择仍 temporarilyBusy | 保留已有未知归属保护 |
| old generation | 绿：旧代次终态写被 `EXECUTION_GENERATION_REVOKED` 拒绝，lease 未释放 | 保留 CoreRun CAS fencing；新增 lease 投影不能绕过 |
| identical workspaces | 绿：复制得到相同逻辑 ID 的两个数据库，A 停止不改变 B 的 accepted/open/lease | 所有新增领取/通知继续绑定工作区 factory |

置信度：高（以上来自实际运行）；测试后共享生产文件可能继续变化，后续结果必须重跑。

## 已明确的测试边界与阻断

1. 有限、不限、同批复用、失败策略的后半段断言已写入真实服务测试，但当前因准入失败尚未执行。不能声称已验证其运行行为。
2. 不限反例仅验证 4 次连续复用和显式停止，不证明任意次数无隐藏上限。正式实现后需要按实际可疑上限增加针对性反例，不凭空制造通用压力框架。
3. 现有执行端口容量只有 1，coordinator 没有按槽领取入口。无法用真实接口制造“失败时另一任务已经原子创建且 queued/running”的数据批次，也无法制造多槽 claim/stop 两种线性化顺序。当前 stop 测试只证明停止提交后的门闩事实错误，不能冒称完整竞争测试。最小后续接点是调度器的真实领取事务，在其前后设置测试屏障；无需新增通用队列。
4. 未用生产未知接口模拟 `prepareInputGroup`/`commitInputGroup`。候选续查（超过 10,000 条）、有效并发的四项最小值、30 秒低频核验、lease/CoreRun/stop 事件唤醒仍待对应实际入口落地后加测。
5. 重启测试创建新 dispatcher/scheduler 来执行真实 startup，并让旧合成 worker 保持未完成直到检查结束；它证明恢复和 fencing 的数据库规则，不是进程崩溃 E2E。
6. 双工作区测试只覆盖同 ID 的数据库隔离，不覆盖 Electron 工作区切换时的迟到通知。
7. 没有运行全量后端、前端、类型检查或构建：此独占范围是定向红灯测试准备，生产由主协调者实施。

## 当前原始红灯输出

以下为该次定向执行输出，保留准入失败与真正业务断言失败的区别。

```text
FFFFFFFFFFF.F..                                                          [100%]
=================================== FAILURES ===================================
____________ test_acceptance_defers_all_task_and_lease_creation[1] _____________
tests/integration/test_project_data_scheduler.py:61: in test_acceptance_defers_all_task_and_lease_creation
    assert coordinator.list_tasks(project, batch.batch_id) == []
E   AssertionError: assert [Task(task_id...e, ordinal=0)] == []
E
E     Left contains one more item: Task(task_id='89d3efc2-57cd-41bc-a79c-40c0b0e291ba', project_id='ec58813b-2e93-4493-be19-86dfc3290c8c', batch_id='0fb1...eated_at=datetime.datetime(2026, 9, 15, 16, 19, 39, 75876, tzinfo=datetime.timezone.utc), completed_at=None, ordinal=0)
E     Use -v to get more diff
____________ test_acceptance_defers_all_task_and_lease_creation[3] _____________
tests/integration/test_project_data_scheduler.py:60: in test_acceptance_defers_all_task_and_lease_creation
    batch = start(data_services, max_tasks)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/test_project_data_scheduler.py:43: in start
    return coordinator.start(
src/autoflow/application/project_runs/coordinator.py:205: in start
    raise ProjectRunError(
E   autoflow.domain.project_runs.models.ProjectRunError: 数据输入首批次当前只支持一个任务
___________ test_acceptance_defers_all_task_and_lease_creation[None] ___________
tests/integration/test_project_data_scheduler.py:60: in test_acceptance_defers_all_task_and_lease_creation
    batch = start(data_services, max_tasks)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/test_project_data_scheduler.py:43: in start
    return coordinator.start(
src/autoflow/application/project_runs/coordinator.py:199: in start
    start = validate_batch_start(
src/autoflow/domain/project_runs/rules.py:53: in validate_batch_start
    raise _error("maxTasks", "必须是 1–100 的整数")
E   autoflow.domain.project_runs.models.ProjectRunError: 批次启动参数无效
_________ test_reusable_rows_are_claimed_again_without_batch_dedup[3] __________
tests/integration/test_project_data_scheduler.py:79: in test_reusable_rows_are_claimed_again_without_batch_dedup
    batch = start(data_services, max_tasks)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/test_project_data_scheduler.py:43: in start
    return coordinator.start(
src/autoflow/application/project_runs/coordinator.py:205: in start
    raise ProjectRunError(
E   autoflow.domain.project_runs.models.ProjectRunError: 数据输入首批次当前只支持一个任务
________ test_reusable_rows_are_claimed_again_without_batch_dedup[None] ________
tests/integration/test_project_data_scheduler.py:79: in test_reusable_rows_are_claimed_again_without_batch_dedup
    batch = start(data_services, max_tasks)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/test_project_data_scheduler.py:43: in start
    return coordinator.start(
src/autoflow/application/project_runs/coordinator.py:199: in start
    start = validate_batch_start(
src/autoflow/domain/project_runs/rules.py:53: in validate_batch_start
    raise _error("maxTasks", "必须是 1–100 的整数")
E   autoflow.domain.project_runs.models.ProjectRunError: 批次启动参数无效
____ test_failure_closes_only_new_claims_unless_explicitly_continued[False] ____
tests/integration/test_project_data_scheduler.py:124: in test_failure_closes_only_new_claims_unless_explicitly_continued
    batch = start(data_services, 3)
            ^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/test_project_data_scheduler.py:43: in start
    return coordinator.start(
src/autoflow/application/project_runs/coordinator.py:205: in start
    raise ProjectRunError(
E   autoflow.domain.project_runs.models.ProjectRunError: 数据输入首批次当前只支持一个任务
____ test_failure_closes_only_new_claims_unless_explicitly_continued[True] _____
tests/integration/test_project_data_scheduler.py:124: in test_failure_closes_only_new_claims_unless_explicitly_continued
    batch = start(data_services, 3)
            ^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/test_project_data_scheduler.py:43: in start
    return coordinator.start(
src/autoflow/application/project_runs/coordinator.py:205: in start
    raise ProjectRunError(
E   autoflow.domain.project_runs.models.ProjectRunError: 数据输入首批次当前只支持一个任务
______ test_busy_batch_is_not_exhausted_and_recovers_after_owner_finishes ______
tests/integration/test_project_data_scheduler.py:148: in test_busy_batch_is_not_exhausted_and_recovers_after_owner_finishes
    second = start(data_services)
             ^^^^^^^^^^^^^^^^^^^^
tests/integration/test_project_data_scheduler.py:43: in start
    return coordinator.start(
src/autoflow/application/project_runs/coordinator.py:243: in start
    raise ProjectRunError(code, message, status)
E   autoflow.domain.project_runs.models.ProjectRunError: 符合条件的数据暂时被其他任务占用
________________ test_true_no_match_finishes_without_task_facts ________________
tests/integration/test_project_data_scheduler.py:184: in test_true_no_match_finishes_without_task_facts
    batch = start(data_services)
            ^^^^^^^^^^^^^^^^^^^^
tests/integration/test_project_data_scheduler.py:43: in start
    return coordinator.start(
src/autoflow/application/project_runs/coordinator.py:243: in start
    raise ProjectRunError(code, message, status)
E   autoflow.domain.project_runs.models.ProjectRunError: 没有符合条件的数据
__________ test_stop_acceptance_closes_claim_gate_in_same_transaction __________
tests/integration/test_project_data_scheduler.py:208: in test_stop_acceptance_closes_claim_gate_in_same_transaction
    assert stored.claim_gate_state == "closed"
E   AssertionError: assert 'open' == 'closed'
E
E     - closed
E     + open
_______________ test_authoritative_terminal_releases_data_leases _______________
tests/integration/test_project_data_scheduler.py:227: in test_authoritative_terminal_releases_data_leases
    assert all(lease.state == "released" for lease in leases)
E   assert False
E    +  where False = all(<generator object test_authoritative_terminal_releases_data_leases.<locals>.<genexpr> at 0x10d90cba0>)
____ test_restart_retains_unknown_leases_until_core_confirms_cleanup[True] _____
tests/integration/test_project_data_scheduler.py:270: in test_restart_retains_unknown_leases_until_core_confirms_cleanup
    assert all(
E   assert False
E    +  where False = all(<generator object test_restart_retains_unknown_leases_until_core_confirms_cleanup.<locals>.<genexpr> at 0x10da9adc0>)
=========================== short test summary info ============================
FAILED tests/integration/test_project_data_scheduler.py::test_acceptance_defers_all_task_and_lease_creation[1]
FAILED tests/integration/test_project_data_scheduler.py::test_acceptance_defers_all_task_and_lease_creation[3]
FAILED tests/integration/test_project_data_scheduler.py::test_acceptance_defers_all_task_and_lease_creation[None]
FAILED tests/integration/test_project_data_scheduler.py::test_reusable_rows_are_claimed_again_without_batch_dedup[3]
FAILED tests/integration/test_project_data_scheduler.py::test_reusable_rows_are_claimed_again_without_batch_dedup[None]
FAILED tests/integration/test_project_data_scheduler.py::test_failure_closes_only_new_claims_unless_explicitly_continued[False]
FAILED tests/integration/test_project_data_scheduler.py::test_failure_closes_only_new_claims_unless_explicitly_continued[True]
FAILED tests/integration/test_project_data_scheduler.py::test_busy_batch_is_not_exhausted_and_recovers_after_owner_finishes
FAILED tests/integration/test_project_data_scheduler.py::test_true_no_match_finishes_without_task_facts
FAILED tests/integration/test_project_data_scheduler.py::test_stop_acceptance_closes_claim_gate_in_same_transaction
FAILED tests/integration/test_project_data_scheduler.py::test_authoritative_terminal_releases_data_leases
FAILED tests/integration/test_project_data_scheduler.py::test_restart_retains_unknown_leases_until_core_confirms_cleanup[True]
12 failed, 3 passed in 3.56s
```

## 实现完成后的复验

2026-09-16 在当前 C 候选源码上重新运行与调度、输入领取和前端管理事实直接相关的检查，历史红灯已经闭合：

```sh
uv run --directory apps/backend pytest \
  tests/integration/test_project_data_scheduler.py \
  tests/integration/test_project_run_data_start.py \
  tests/integration/test_project_input_groups.py \
  tests/unit/test_project_automation_rules.py -q
# 63 passed

uv run --directory apps/backend ruff check .
# All checks passed!

uv run --directory apps/backend mypy src
# Success: no issues found

npm run typecheck
# passed

npm run openapi:check
# passed

git diff --check
# exit 0
```

独立规格复核与工程复核均为 PASS。复核重点包括：跨页 `fieldEquals` 歧义、候选排序与现有数据查询语义一致、未知英文内部原因不直接暴露、停止门闩、领取提交内容量重查、状态/结构改变后的旧候选撤销，以及带类型记录身份。

真实管理端运行使用 Electron、FastAPI、隔离 SQLite 和 fake executor，权威目录为 `qa-runs/c-m3SplP`。有限 3 次、不限次数主动停止、人员重复使用、邮箱显式改变状态和账号不重复新增全部通过；视觉逐页复审结果见 `c-verification.md`。真实生产执行核心、CloakBrowser、Studio、Windows、打包与用户手测仍未执行。
