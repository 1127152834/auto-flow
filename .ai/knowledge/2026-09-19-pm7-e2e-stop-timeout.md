# PM7 端到端「批次停止」超时根因（2026-09-19）

- **状态**：confirmed（证据来自本机真实运行与数据库只读查询）
- **范围**：PM7 F 阶段第一条端到端链（E2E-1 停止场景）
- **来源**：`docs/project-management/implementation/pm7/qa-runs/20260918184014/report.json`、`20260918184711/`，以及两次运行的隔离工作区 SQLite
- **影响**：PM7 首条 E2E 链在「普通停止 → 强制停止 → 等待批次终态」处超时；批次永久停留在 `stopping`

## 观察事实

1. 两次真实运行的隔离数据库中都留下同一形态的卡死批次：

```
batch       status      completed_at
5fe08384    stopping    (NULL)        # run 20260918184014
e49bd28f    stopping    (NULL)        # run 20260918184711

task        batch       run status
03a1de26    e49bd28f    running       # 无 completed_at
a55478ae    5fe08384    running
```

2. 同批次内**没有** `project_manual_items` 记录，因此不是「等待人工」导致的正常挂起。
3. `report.json` 失败点：`Error: batch <id> did not reach terminal state`（`waitBatchTerminal`）。

## 根因

两个已确认事实叠加：

1. **产品侧规则（设计如此）**：`apps/backend/src/autoflow/application/project_runs/scheduler.py:434`
   在批次非终态时 `if stopping: return` —— 处于 `stopping` 的批次只要还有非终态任务，就不会转终态，必须等运行中任务自行收敛。这条规则本身符合「普通停止不新建任务、等运行中任务结束」的既定语义。
2. **验收脚本时序**：`scripts/qa-project-management-pm7.mjs` 先给下一任务装上 `executor-pause` 屏障（任务在隔离执行器内被挡住），再执行普通停止 → 强制停止 → **等待批次终态**，最后才调用 `executor-resume` 释放屏障。

任务被屏障挡住 → 运行始终 `running` → 批次永久 `stopping`；而解开屏障的调用排在终态等待之后，脚本只能等到超时。**这是脚本自锁，不是批次停止语义的产品缺陷。**

## 待确认的产品问题（不能默认已通过）

强制停止后，运行任务的**执行代次撤权**只能在执行器下一次推进时被观察。因此存在一个尚未验证的边界：

> 若执行器被外部因素永久挂起（不返回、不超时），强制停止是否仍能让批次收敛？

- 若既定契约只要求「代次撤权 + 执行器恢复后被拒绝」，则修好脚本时序即可，批次收敛依赖 `executor-resume` 之后任务被拒绝并落为 `interrupted`/`cancelled`。
- 若契约要求「强停后批次必须收敛且不依赖执行器响应」，则 `scheduler.py:434` 需要补充被撤权任务的终态化路径，属功能缺口而非脚本问题。

PM7 验收必须二选一并留下证据，不能靠放宽等待时长或改断言绕过。

## 建议修法（最小改动优先）

1. 在 `确认强制停止` 之后立即 `executor-resume`，再调用 `waitBatchTerminal`，断言批次 `stopped` 且暂停任务落为终态。
2. 若第 1 步仍不收敛，则按上面「待确认的产品问题」升级为产品缺口，进入 `scheduler.py` 排查，不得下调断言。

## 附：同一时点的机器检查结果（当前 HEAD `82473be9`）

| 命令 | 结果 |
|---|---|
| `uv run --directory apps/backend pytest -q` | 3082 passed, 16 skipped, 0 failed |
| `uv run --directory apps/backend ruff check .` | All checks passed |
| `uv run --directory apps/backend mypy src` | Success: no issues found in 383 source files |
| `npm test` | 399 files / 5409 tests passed |
| `npm run typecheck` / `lint` / `build` | 通过 |
| `npm run openapi:check` | 通过 |
| `npm run test:scripts` | 78 passed |
| `npm run test:structure` | 4 passed |
| `git diff --check` | 无输出 |

一次更早的全量运行曾出现 `tests/contract/test_schema_export.py::test_schema_export_cli_outputs_only_json` 单点失败（进程内与子进程 schema 不等）；隔离重跑与第二次全量均通过，现场另有并行进程在写同一工作区，判定为并发干扰，非稳定缺陷。
