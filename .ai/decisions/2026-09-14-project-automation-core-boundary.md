# 项目自动化与执行核心边界

- 日期：2026-09-14。
- 状态：confirmed。
- 来源：已批准 PM3 规格、当前实现及 2026-09-15 管理范围复核。
- 验证：docs/project-management/implementation/pm3/verification.json。

## 决策

项目模块拥有 Automation、Batch、Task、输入快照、项目 Operation、运行目录与展示聚合。工作流文档、PreparedContent、CoreRun、RunEvent、网页 worker 和浏览器资源释放由核心执行层拥有。项目模块通过进程内应用服务和同一数据库工作单元组合原子事务，不通过 HTTP 回调同一服务，也不建立第二套执行器。

Batch 创建时，Task、不可变输入快照与 queued CoreRun 在调用者的短事务内共同提交；提交后才调度。Task 只投影 CoreRun 状态。项目停止命令关闭后续领取，再把带期望修订和执行代次的停止请求扇出给核心；强停准入由核心根据持久状态和 30 秒宽限计算。强停先撤销旧执行代次，再结束 worker 和资源，迟到事件不能取得提交权限。

项目管理界面读取持久事件、日志、输出与证据；SSE 只作失效通知，断线后按序号从持久接口补读。命令接受、最终完成和结果不明分别表达；结果不明保留原 Idempotency-Key，先查询原操作事实。

Studio demo 的画布、transport 与 bridge 不属于本次 PM3 管理交付。工作流测试资料由真实 WorkflowService 创建，该做法只验证管理端关联与执行，不表示 Studio 用户路径已验收。

## 后续边界

项目数据领取和工作流显式写表属于 PM4；持久环境与 End 保留属于 PM5；同步、统计、人工处理和项目生命周期继续由后续里程碑交付。PM3 不提前实现这些能力。
