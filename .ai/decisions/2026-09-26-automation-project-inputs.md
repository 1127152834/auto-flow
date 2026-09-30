# 自动化与输入对象
日期：2026-09-26。状态：confirmed。来源：用户批准并要求实施修订方案。
自动化与工作流一对一，创建时生成，不再让用户关联已有工作流。Studio 项目数据展示当前命名输入对象，列表只用于调试候选单选。选择不占用；执行时精确重验并领取，不换记录。默认第一个完整有效组、运行一次 maxTasks/concurrency=1。数据写入保持显式、原始快照不变。正式计划见 docs/superpowers/plans/2026-09-26-automation-project-inputs.md。

实施验证：见 docs/project-management/implementation/automation-project-inputs/README.md。新建公共 API 由服务器分配 workflowId；旧身份创建仅留内部兼容路径。项目单次调试使用原批次请求与恢复协议，固定输入版本，不创建第二执行器。Studio 共享弹窗从同一 Tailwind 编译入口导入现有主应用 tokens，避免缺失背景和层级。
