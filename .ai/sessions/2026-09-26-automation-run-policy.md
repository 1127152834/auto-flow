# 自动化运行设置边界调整

日期：2026-09-26；状态：confirmed（界面与默认值）；参数批次并发补充 proposed。
来源：本轮用户要求、RunPolicyEditor/form-schema、ProjectBatchScheduler 与既有环境回收测试。

## 已实施

- 移除自动化运行设置中的“任务结束时环境处理”禁用占位。环境是否持久保存由工作流显式决定；本次不新增用户尚待设计的保存节点，也不改变已存在的 End 保存/关联与失败恢复语义。
- 失败开关明确为“任务失败后继续下一个任务”，直接映射 continueAfterFailure。新建默认 true；读取、编辑旧配置仍保留显式 false。它只控制批次后续任务，不决定工作流节点失败后的跳转。
- 没有显式保存时沿用既有临时实例回收；清理失败、保存进行中、归属待核验等场景继续保留现场，不能冒充已删除。

## 并发待确认

旧 2026-09-21 多 Run 方案明确单参数批次最多一个活动实例，前端、API 校验及 scheduler 都限制为 1。不是数值控件问题。已交付 docs/superpowers/specs/2026-09-26-parameter-batch-concurrency.md，包含额度、排队、跨批次实例和失败/停止行为及验证切片，已发送异步确认，等待期间不开放输入框制造虚假能力。

## 工作区与验证

从本地 baseline b1ad5cb3 创建独立 codex/automation-run-policy 工作区，未修改主目录并行工作。远端 baseline 仍为 2cc06c63，比本地少 10 个提交；本次不擅自推送这些历史提交或合并。

- 新断言先复现 3 项失败，随后相关前端 37 文件 / 295 项通过。
- 既有后端调度、环境终结和清理投影 46 项通过，1 项第三方弃用警告；覆盖失败停止/继续、不重跑已完成任务、终态清理、保存/核验现场保护。
- typecheck、lint、build、git diff --check 通过。
- 全量前端 447 文件：444 通过 / 3 失败；5857 个断言通过 / 2 失败，208.73 秒。两项节点数量断言（module-scope 213 vs 216；moduleColors 216 vs 219）在未改动的 baseline b1ad5cb3 定向复验同样失败，保留为基线问题，不改并行 Studio 范围。第三个 suite 因新工作区缺少被忽略的 reference/WebRPA 无法加载，链接既有参考目录后 17 项全部通过。没有宣称全量绿色。
- 检查使用既有 baseline node_modules/.venv；临时依赖 symlink 在验证后移除，参考目录链接保留在 git 忽略范围。原始日志位于 /tmp/autoflow-run-policy-{tests,baseline-tests,reference-test,build}.log。
- 未运行三平台打包或实机验收；不升级 PM9 覆盖状态，releaseAccepted=false。
