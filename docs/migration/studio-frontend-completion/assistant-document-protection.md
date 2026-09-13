# F5 AI 文档替换保护

日期：2026-09-14；状态：本切片已实现并验证。

AI 的实际 executeClientAction 与此前 UI 事件是两条路径。new_workflow、load_workflow 和 load_workflow_from_data 必须调用已挂载编辑器的同一保存保护，拒绝/取消不能报告完成。未挂载编辑器时拒绝替换。文件加载期间编辑使响应失效；文件导入复用正常文档校验并保留变量。

测试：实际 AI 命令等待 UI 选择；取消/保存失败保留；无编辑器拒绝；文件读取迟到不能覆盖；合法文件完整变量恢复。动画搭建的中断、原子撤销及活动会话清理仍另行完成。


## 验收

- actual executeClientAction 的 new_workflow / load_workflow_from_data 等待三选项决定，取消返回失败且草稿不变；没有挂载编辑器时拒绝替换。
- AI 读取工作流期间编辑使结果失效；允许载入时通过正式 importWorkflow 校验，保存文件的声明变量全部恢复。
- add_nodes 改为一次历史操作，不再调用会清空变量/历史的 loadWorkflow；撤销/重做均保留既有变量。
- AI 新生成文档带声明变量并标为未保存。
- 在取消 i18n 范围后完成 99 文件 / 1,167 项全量回归，类型/lint/构建通过。定向组件与规则测试含实际 AI 命令分发，不调用真实 AI 服务。
- 证据复用 `evidence/chinese-only-validation.txt`，测试路径 toolbar-draft-protection.test.tsx、excluded-assistant-nodes.test.ts。

此前一次高并发全量回归出现大量无关超时，已中止；随后直接使用 workspace 测试命令与 maxWorkers=1 完整通过，没有调整断言或时限。i18n 专属测试后来按用户独立的产品范围决定移除，不能用其删除解释其他回归通过。

仍待完成：AI 动画搭建的中途取消/编辑隔离、AI 时间线快照中的变量和结果状态、整包导入，以及全部活动会话/宿主离开协调。
