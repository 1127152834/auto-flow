# 参数批次并发实施计划

日期：2026-09-26；状态：approved。用户已批准实施并补充同一记录不得同时分配给两个任务。
规格：docs/superpowers/specs/2026-09-26-parameter-batch-concurrency.md。
全局约束：复用现有 scheduler/core/租约，不提高 core 的两个槽上限；不改主工作区；不合并；无数据输入不造数据；记录释放后由筛选条件决定是否再次领取。

### Task 1: 调度与领取

先写失败测试，再允许参数政策和启动并发 1–100。调度参数队列遵守请求/配置/同自动化实例/全局容量，保留失败及主动停止行为。核对数据任务原子领取，测试竞争同一记录、不同记录分配、释放后补位、参数排队不阻塞数据任务。
验证：相关规则、project_run_dispatch、project_run_data_start、project_input_group_claiming 和新增并发集成测试。
Expected: 全部通过，两个任务同时运行时输入身份不重复。

### Task 2: 编辑与启动

先更新失败断言；所有自动化可手填并发和实例上限；移除数据输入不重置数值；启动请求沿用已保存值，非法草稿不能提交，摘要真实显示上限。
验证：前端 project-automations/project-runs 测试，typecheck、lint、build。
Expected: 相关检查通过；实际容量仍有说明。

### Task 3: 集成与交付

真实 worker 并发和数据租约相关回归、最终差异审查；补记录并提交分支。复用上一轮全量前端两项 Studio 已复现的基线失败，不修改无关节点台账。
验证：真实 worker 并发测试、完整前端和后端相关回归、OpenAPI 检查。
Expected: 新增范围全绿；其他失败明确保留，不宣称 PM9 releaseAccepted。
