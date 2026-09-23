# PM9 XE-A17 归档收尾执行切片

日期：2026-09-23。状态：confirmed（既有 PM9 / XE-A17 授权范围内的缺陷修复）。来源：execution-and-environment.md §14 XE-A17、现有生产 HTTP/SQLite/worker 和本轮失败断言。原实施分支继续；不扩展连接恢复 L1–L3、云端行操作 M1–M3 或跨进程人工恢复。

1. 在一个真实项目中构造两个真实 worker：A 等待人工，C 已进入 End 保存；B 的远端写入成功但响应丢失。归档必须关闭新入口、等待已受理保存和未知同步核验、取消 A；C 的未发送值不能自动推送。
2. 在共享归档 blocker 中纳入 sending/verifying/unknown 值意图和未结算 saveEnvironment 操作；closing 仅允许原目标 reconcileSync。保留 pending/paused 本地事实。
3. 任务 updateRecord 与管理编辑复用事务内 enqueue_intent；不接通新增/删除云端行。原命令重放不重复入队。
4. End/manualComplete 通过标准线程池运行现有保存函数，已受理线程在取消时必须先结算；worker 在 capability 结束前保留目录和容量。新的保存/End 在接受事务中校验项目、实例和运行代次；原摘要重放和固定父 End 派生保存可以收尾。retained_unsaved 的显式更新冲突/另存保留现有行为。
5. 终态 Run 的实例经过现有所有权清理后才释放记录占用、终结批次。保留 retained_unsaved 和未知实例；不以修改状态替代 native 清理。
6. 定向验证归档、同步、环境、worker 取消与代次竞争；复跑真实旧候选冲突、仅关联修复、人工到期竞争。稳定后完整后端回归、构建和单次三平台候选矩阵，记录各自 hash，不据历史通过升级当前验收。

本轮先复现的根因：未知值写未参与归档 blocker；closing 拒绝原结果核验；任务更新遗漏出站意图；同步 End 阻塞事件循环；force cleanup 不等已受理 callback；取消 Run 后实例遗留 waiting_manual。实现与验证进度见 `docs/project-management/implementation/pm9/archive-settlement-follow-through.json`。releaseAccepted=false。
