# M2A Task 3：终态投影、业务结果与人工核实 步骤级计划

- 日期：2026-10-03；状态：执行中（2b 统一出错策略顺延到 Task 4 之后，原因：规格只要求"分类先于投影"，领取安全链 AC2-02 依赖 Task 3/4）。
- 上位：[M2 规格](../specs/2026-09-30-remediation-m2-business-model-reliability.md) R2-02/R2-04/R2-06/R2-14；[任务级计划](2026-09-30-remediation-m2-business-model-reliability.md) Task 3。

## 设计决定

1. **投影落点**：调度器"终态释放数据租约"的事务（`ProjectBatchScheduler._release_terminal_leases`）。主处理输入的租约 held→released 只发生一次，投影随之恰好一次；释放前该行不能被再次领取，因此与"终态同事务"在领取安全上等价，且不把项目逻辑塞进通用运行核心。只投影主处理输入，参考输入不建账。
2. **结果判定**（`application/project_runs/outcomes.py`）：运行成功且 End 业务结果为 failed → business；运行成功 → succeeded；其余按 Task 2a 的分类（infrastructure/page/unknown/cancelled），终态缺分类时按 unknown。
3. **状态转换**（`domain/project_runs/ledger.py::next_ledger_entry`）：succeeded 计一次并设 60 秒再用间隔；business → skipped；page 按本轮预算退避（默认 3 次、[60,300,1800] 秒），用尽 → quarantined；infrastructure/cancelled 不计预算、保留资格；unknown → needs_review 并记录原任务；needs_review 不被后到的投影改写；只有确认成功的单位开始新一轮时 processing_cycle+1。预算与退避读冻结请求中的 runPolicy（字段 Task 4 加入，暂用默认值）。
4. **批次处理单位**：投影时登记 (batch, unit)，供历史批次统计。
5. **人工命令 HTTP**：`/automations/{id}/processing-units` 列表（按状态、键集分页）与 reset/skip/resolve 命令；需修订号、原因与幂等键（复用 project_operations，kind=changeProcessingUnit），活动任务持有该行时拒绝，needs_review 只能 resolve。
6. **最小界面**：自动化详情页"处理记录"面板：按状态筛选、显示最近原因、重置/跳过/核实（核实需选择结论并填原因），失败重试沿用同一请求身份。

## 验证

- 单元：next_ledger_entry 各分支、预算跨轮、needs_review 不被覆盖。
- 集成（真实 SQLite + 调度器 + 分发器 + 模拟 worker 上报已确认的 started 事实）：成功/只读失败/副作用后失败/未开始失败四种终态各投影一次，二次释放不重复，参考输入不建账。
- HTTP：列表筛选分页、跳过→重置的修订号与幂等重放、needs_review 只能核实、错误请求 404/422。
- 前端组件：状态文案、筛选、原因必填、核实结论、失败后同一请求身份重试。
