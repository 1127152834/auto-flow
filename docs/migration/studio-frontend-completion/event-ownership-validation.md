# 活跃流程的终态、数据与节点事件归属

已有currentExecutionWorkflowId时，其他workflowId的node_start/node_complete/completed/stopped/data_row/data_row_batch不再修改当前执行状态、暂停位置、数据或节点标记。当前工作流事件照常处理。无已知执行身份时保留原历史初始化行为；本批不改变日志集合策略、started事件或同文档多轮身份协议。

新增内存与真实本地HTTP/SSE两条顺序事件用例，先确认活跃/暂停，再插入外来事件和有序marker，断言暂停、状态、数据及节点标记未污染，最后验证本流程仍能收数并成功结束。首次两项失败，修复后与调试HTTP及修复建议事件合计6项通过。扩展节点标记断言纳入全量回归。类型/lint、构建及21脚本通过；全量141文件1706项通过。证据evidence/f3-event-ownership。

全部为服务消费协议验收，不是实际自动化后端或Electron实机验收。独立runId、重复运行、SSE epoch、运行历史持久化仍属于未完成合同。

首次全量发现3失败：新节点状态测试缺localStorage夹具（2项），以及输入弹窗关闭回归（1项）。保留全部断言，初始化测试存储，并将按pendingInputPrompt.workflowId清理放在主运行归属检查之前；针对11项回归后全量通过。
