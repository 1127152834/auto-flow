# 退役项目临时浏览器执行器

日期：2026-09-24。状态：confirmed。来源：用户澄清四节点实现是项目管理开发期间的临时引擎，并在审阅清理范围后明确要求“开始吧 帮我处理掉”。

范围：保留 open_page/input_text/click_element/get_element_info 节点功能，统一调用正式生产注册表；删除 _LegacyBrowserNode、WorkflowExecutor 动作与线性循环，迁移有价值的 worker 测试。此前 2026-09-20 PM9 R1 Ruling 中长期保留四节点旧语义的取舍在此范围 superseded。

设计：项目仅保留事件持久确认、取消/整体超时及 project_data/project_end/project_manual 能力适配。图调度、变量解析和浏览器动作由现有正式实现负责，失败截图从同一浏览器会话读取。既有 chain/v1 仅转换为共享 Runtime 文档，不恢复旧引擎，不删除用户文档/运行数据或改数据库。

契约：无新 HTTP/前端节点类型。动作行为采用正式引擎，包括输入方式、变量解析、当前页面不存在时的错误；不维护临时引擎的独立行为。保持事件先提交后副作用、错误脱敏、截图、停止及权限边界。

实施与验证：先以同文档在 Studio/项目两入口的真实节点执行对照建立失败回归；移除旧实现并迁移超时/停止/截图断言；运行对应单元、真实浏览器/worker、后端全量、Ruff/mypy和构建。另核对旧执行器无源码引用。仅在隔离分支 codex/remove-project-legacy-executor 修改，不操作主任务的工作区、在途验证或发行状态。

实施已完成；全量 3487 passed、79 skipped，另行真实浏览器 46 passed，打包生产链通过。详细边界与首次健康检查超时记录见 [验证记录](../knowledge/2026-09-24-project-legacy-executor-retirement.md)。
