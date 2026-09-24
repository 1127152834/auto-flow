# 节点浏览器环境讨论

- 日期：2026-09-24。
- 状态：confirmed 产品方向；proposed 详细执行/兼容契约，未实施。
- 来源：用户要求移除环境页右侧卡片、模板与实例独立、将浏览器选择放入打开网页节点；随后确认三个属性是模板、代理、内核。
- 核对：ProjectDefaultsPanel / ProjectFormDialog、Toolbar、OpenPageConfig / OpenPageExecutor、WorkflowBrowserResources、dispatcher / worker 及原 I1–I3 身份规格。当前 git 分支 codex/automation-studio-entry；读取时新增同行提交 317f07f8，未覆盖其修改。
- 结果：规格见 `docs/superpowers/specs/2026-09-24-node-browser-environments-design.md`。顶部选择器不能单删：Studio 请求、提前启动、录制调试和自动化覆盖均需要按同一契约调整。已有持久身份漂移仍是实现缺口。
- 范围：复用一个 Runtime 与环境服务；每 Task 单活动实例；不新增所有指纹属性编辑、任意多浏览器切换或隐式保存。详细兼容规则仍需用户审阅，不能把仅确认三个属性写成全部架构批准。
- 验证：本轮仅代码阅读与文档自查，无生产修改、无业务测试、无运行验收；releaseAccepted 不变。主目录和用户运行数据未修改。
