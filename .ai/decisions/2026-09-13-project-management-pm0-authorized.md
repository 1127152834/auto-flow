# PM0 实施授权与逐里程碑验收

- 日期：2026-09-13；状态：confirmed。
- 来源：用户明确“PLEASE IMPLEMENT THIS PLAN”并提供完整PM0计划；此前要求逐个里程碑验收。
- 设计基线：906deda；整体里程碑计划基线：349c4be。

用户已批准PM0执行及完整里程碑方向。此前“仅规划/尚无实施授权”的会话时点描述已 superseded；历史设计文件保持原样。当前授权交付PM0文档、契约、合成样例、覆盖核验与独立提交，不启动PM1页面/API实现。

使用独立设计worktree，主项目、UI与旧项目只读。主项目的Studio并行工作可以被读取并记录WIP差异，不覆盖其文件、不替其声称验收通过。每阶段交付后等待用户验收，不自动跨越到下一阶段。

执行依据：[PM0执行卡](../../docs/superpowers/plans/2026-09-13-project-management-pm0.md)。PM0完成状态以[执行账本](../../docs/project-management/implementation/execution-ledger.md)和实际核验报告为准；授权不等于业务测试通过。
