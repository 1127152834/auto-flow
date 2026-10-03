# M2A Task 5：熔断、坏行隔离与暂停/继续 步骤级计划

- 日期：2026-10-03；状态：执行中。上位：[M2 规格](../specs/2026-09-30-remediation-m2-business-model-reliability.md) R2-15/R2-16/R2-17。

## 设计

1. `runPolicy.failurePolicy = "thresholds"`（可选）。缺省沿用旧规则：continueAfterFailure=false 首个失败即停止领取（legacyAnyFailure），true 则继续（legacyContinue）；不把旧自动化静默迁到新阈值。界面新建数据自动化默认开启阈值。
2. 阈值（`domain/project_runs/circuit_breaker.py`，只看最近一次"继续"之后结束的任务）：连续 5 个 infrastructure；连续 10 个相同技术错误码（page/infrastructure）；最近 20 个中 page 超过一半（至少 10 个才判断比例）。business、unknown、cancelled 不计入也不打断连续计数；成功打断连续计数。
3. 触发后批次进入新状态 `paused`：关闭领取开关，`selection_outcome.pauseReason` 记录类型、文案、错误码、样本任务；已在运行的任务自然结束，不再领取。
4. 继续：`POST /batches/{id}/resume`（expectedStatusRevision + 幂等键，操作种类 resumeBatch），只接受 paused；不重置预算、处理记录与未知门禁；熔断窗口从这次继续之后开始。停止沿用原停止命令。
5. 坏行（R2-17）：主处理输入所选行自身取值不合法、身份可确定时隔离该行（不计尝试），重新选择下一行；参考输入坏行仍按原配置错误处理，Sheets 来源身份门禁不变。
6. 界面：批次状态"已暂停"（目录筛选、标签）、详情显示原因与"继续批次"；运行策略"失败过多时自动暂停批次"。
7. 范围：熔断只作用于数据批次；参数批次保持旧规则。不新增数据库列（暂停原因在 selection_outcome，继续时间取自操作记录）。
