# PM0 契约与实施基线交付

- 日期：2026-09-13；状态：confirmed（授权与已核验事实），PM0最终交付状态以账本/报告为准，用户验收pending。
- 来源：用户明确要求执行PM0；基线349c4be，设计906deda。
- 工作区：autoflow-project-management-design / codex/project-management-design；主项目、UI和旧项目只读。

## 产物与审查

[执行卡](../../docs/superpowers/plans/2026-09-13-project-management-pm0.md)、[领域契约](../../docs/project-management/implementation/contracts.md)、[HTTP与IPC](../../docs/project-management/implementation/api-contracts.md)、[样例](../../docs/project-management/implementation/fixtures.json)、[执行账本](../../docs/project-management/implementation/execution-ledger.md)。

48功能、178场景、18执行契约、7能力门槛映射到30交付包；FX-01–07、13个分支场景、3条代表流程都是合成领域样例，不是可执行Studio IR。

规格审查修正可选输入/日期与身份/原关联证据/动态事务/人工TTL/End恢复等问题；随后工程质量审查核对批量块、影响预检、命令结果、分页、签名/错误映射和迁移依赖。审查闭合记录见账本，最终命令/退出码、源码与文档指纹见[核验报告](../../docs/project-management/implementation/plan-verification.json)。

## 真实基线与边界

主项目初读f3fe376，交付前另一任务提交b2e95b3；Studio M1文档CRUD、renderer窗口及0005_workflow_documents已提交，但节点runnable=false，Run仍无实现。旧about:blank/全为WIP当前事实已superseded。PM1先对齐当前0005迁移head；PM3依赖核心实际运行能力，项目不得自行扩展Profile测试worker来替代。

已完成的核验类别是文档编号/引用/依赖/样例结构、TS文档片段严格编译及Git范围/空白；具体最终结果以报告为准。未执行pytest/Vitest业务测试、应用、CloakBrowser工作流、实网Sheets或Windows/macOS源码/安装包验收。

保留本分支和工作区，不合入主项目、不推送、不自动开始PM1。下一步由用户验收PM0后，按PM1前后端垂直切片执行卡继续。
