# 排除能力清理台账

2026-09-13；F0 进行中。

| 对象 | 消费者依据 | 本次处理 | 尚未完成 |
|---|---|---|---|
| QQ/飞书全局配置表单 | 专属标签及 updateQQConfig/updateFeishuConfig 调用 | 删除标签、表单及组件内失效引用 | 旧配置 Store 数据保留，避免破坏用户数据；剩余帮助/AI 工具描述待审 |
| Excel 资源底栏 | LogPanel→ExcelAssetsPanel；节点端消费者 ReadExcelConfig 已排除 | 删除面板入口、上传按钮和渲染；旧 assets tab 显示日志 | 源组件与旧 API 保留待全调用闭包确认；不是全部删除完成 |
| AI 新建排除节点 | add_nodes/load_workflow_from_data 使用 partitionValidAiNodes | 根据相同 excludedModuleTypes 拒绝；保留合法节点并移除悬空边 | AI tool 描述与其他动作入口继续审计 |
| AI Excel 资源工具 | upload/list/delete/rename/preview/sheets 及 switch_bottom_panel | 明确拒绝，不能通过 AI 重新打开已删除面板 | 注册/说明中的暴露仍待移除 |
| 数据表格与图像资源 | 保留网页采集、截图及 AI 工具 | 保留 | 逐项引用审计未关闭 |
| 旧文档与自定义模块 | importWorkflow/loadWorkflow | 未清除任何已有数据，保留源解析 | 不支持节点的显式标记和运行拒绝仍待实现 |
