# PM9 多 Task 实际并发补充方案

日期：2026-09-21；状态：approved；2026-09-21 用户在收到 S1–S5 后要求“继续实现”。来源：DATA-E2E-06、FLOW-A02 原始验收条件、52936b6a ARM 打包 HTTP/真实 worker 补测及现有资源所有权代码。本方案独立于已提出的 S1–S4，不能将此前四片确认自动解释为本片批准。

## 已复现的边界

`application/workflows/dispatcher.py` 的 capacity 固定为 1，task/lease/runId/预算定时器均只有一个；`infrastructure/process/project_workflow_worker.py` 也仅拥有一个 `_worker`。参数型第二批次已有 Task，但处于 queued、批次 blocked；数据型批次则在领取前受 core_capacity 限制。人工等待仍占用活跃现场和执行槽。首轮并发场景中 T2 到期后 T1 才完成，不能称为旧契约并发成功。

即使改这两处，`bootstrap/workflows.py` 中工作区、内核、许可证锁及 profile usage guard 仍会阻止同时使用。删除锁或仅改变 capacity 不是修复。此问题是多个独立 Run 的所有权边界，S3 是单个 Run 内的分支隔离，两者分别验收。

## 契约与最小实现边界

1. 保留一套 WorkflowRunDispatcher、ProjectWorkflowWorkerManager 和 WorkflowRuntime 执行逻辑。将现有单 owner 状态移入按 `(runId, executionGeneration)` 定位的 owner 记录；每个 owner 有独立 task、worker 进程、租约、自动预算、清理状态和控制锁。不得共享某个 Run 的定时器或把全局 busy 当作某 Run 的取消条件。
2. dispatcher 暴露真实可用的有界容量。首片提供两个槽，用于证明两个同时活跃 Task；保留参数批次按 maxTasks 连续创建多个 Task 的既有语义，单参数批次同时最多一个活动实例；两个参数批次可分别占用一个槽，多输入数据型批次继续受已声明 concurrency/maxLiveInstances 约束。首次并发准入必须在同一个控制锁内预留槽与转换 Run 状态；失败归还预留，等待人工仍占槽，清理结果不明不释放槽。后续提高硬上限必须有资源/吞吐证据，不新增设置页面。
3. 资源租约在既有 `WorkflowBrowserResources` 内引用计数：项目运行集合只持有一次既有工作区排他锁，Studio 会话继续被同一锁拒绝；同内核/许可证的外部排他锁由该集合持有至最后一个租约确认清理，安装/删除/换许可证仍被阻止。每个 Run 使用独立环境工作副本；同来源 Profile 的保护锁可在项目集合内部共享持有，禁止修改或删除来源。不能把实际 Profile 用户目录当模板直接并发打开。
4. 持久环境占用仍以环境 ID 和 instance ID 排他，不受来源 Profile 共享规则影响。同一持久身份的两个 Run 只能一个成功获得占用。准备/获取资源中途失败只释放本 owner 的计数；清理未知保留对应租约及外部锁，不影响另一 Run 的身份。
5. 所有 worker RPC、事件 ACK、人工继续/到期/终结和取消按精确 runId/代次路由；取消 A 不停止 B，不重置 B 的预算、不释放 B 的占用。全局 quiesce/shutdown 关闭新准入后逐个收尾，全部确认才释放集合锁。重启沿用既有中断/核验规则，不恢复人工执行。启动时先关闭全局准入，全部历史非终态 Run 的占用/进程/目录核验与中断收尾完成后才开放槽；任一清理未知继续阻塞准入，不能因内存 owner 集合为空就认为空闲。
6. 不复制 scheduler、不加入跨进程人工恢复、不扩大项目节点目录。这里的共享租约仅在当前拥有锁的 sidecar 进程内部；另一进程仍被 OS 锁拒绝。外部锁参与者（Studio、内核安装与 Profile 管理）协议保持兼容。

## 文件级实施与验证切片

所有路径位于现有 PM9 独立工作区。每片先补能失败的实际断言，再改实现；本轮继续实现指令已授权执行这些切片。

- **S5.1 owner 隔离。** 修改 `application/workflows/dispatcher.py` 与 `infrastructure/process/project_workflow_worker.py`，审查所有 pause/resume/cancel/force_stop/shutdown/reconcile 的 owner 定位。先在现有 dispatcher/worker 单元与集成测试里证明两 owner 独立预算、取消、迟到事件、清理失败、同 ID 旧代次拒绝；生产容量仍保持 1。
- **S5.2 资源集合租约。** 修改 `application/workflows/browser_resources.py` 和 `bootstrap/workflows.py` 的项目装配；复用既有 OS 锁及 Profile guard，不改主目录 Studio 工作。测试同内核/同来源独立副本并发、不同内核、第二资源获取失败、非最后租约释放、未知清理保留；用另一个进程验证 Studio/内核修改/Profile 删除仍不能越过锁。若现有保护协议无法支持内部共享，先更新该设计，不绕过检查。
- **S5.3 真实运行与调度。** 只有 S5.1/2 安全边界都通过才将容量启用为 2。复用 `application/project_runs/scheduler.py` 的配额/领取事务，补两个批次及单数据批次并发，确保不超配、不重复领取、同环境占用排他、两 worker 各自写回。更新 `scripts/smoke-project-business-combinations.mjs`：T2 始终 waiting_manual 时 T1 加列/新建/修改/设状态并完成，然后 T2 按旧字段继续成功；移除当前已知边界期望须以这条正向真实链替代。
- **S5.4 回归与证据。** 覆盖取消一方另一方持续执行、TTL 各自竞争、清理未知、同名变量、浏览器 cookie/工作目录隔离、退出后无拥有的 worker 遗留。运行相关 pytest、ruff/mypy、脚本检查，稳定候选跑完整回归及既有三平台源码/打包链，记录实际并发重叠时间与任务/进程身份。覆盖台账只按各自断言升级，单槽下串行成功不能填补 FLOW-A02。

## 审批与退出

本新增多 Run 架构已于 2026-09-21 随用户“继续实现”批准。当前生产在 S5 完成安全租约验证前仍保留单槽与安全锁；完整 PM9 退出前 releaseAccepted=false。
