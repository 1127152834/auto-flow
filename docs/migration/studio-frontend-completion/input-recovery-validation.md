# F3 输入回执与事件恢复验收

2026-09-14。本批保持284节点及中文界面范围，不新增自动化执行器。

## 实现

输入提交与取消等待同一稳定commandId的确认回执。发送期间禁止重复操作；确定拒绝保留输入并允许修正；响应丢失后按原ID查询，仍无法确认时保留内容、锁定提交并提供“查询提交结果”，不另发一次提交。旧请求的回执不能关闭新请求。AI和人工入口遵守同一提交规则。

新增 GET /api/events/input-prompts/{requestId}，返回requestId、workflowId、nodeId与pending/answered/cancelled/expired状态，不返回用户值。未知404，错误方法405。类型来自StudioInputPromptState的OpenAPI生成结果；正式自动化后端仍需按合同实现此读取接口。

SSE输入事件显示前查询请求状态，只有当前仍pending的请求可显示。已完成历史事件不重新弹窗。请求状态查询临时失败会重试读取；404/410停止重试。序号保护迟到查询，断开连接清除重试责任，连接恢复重查候选请求。匹配工作流的停止/失败回收等待弹窗，不让其他工作流的结束事件关闭当前输入。

原始输入保存在组件内，命令结果状态不能由HTTP接受或按钮点击代替。输入请求状态只存在Mock服务生命周期中，未宣称跨服务崩溃持久化。

## 用例与证据

- input-prompt-delivery.test.tsx：等待确认、拒绝保留、原ID查询、旧回执隔离、取消确认，共5项。
- input-delivery-http.test.tsx：真实本地HTTP丢响应、查询暂不可用、四种历史请求状态恢复、失败重试与迟到查询隔离，共7项通过。
- input-command-protocol.test.ts：新增8个内存/HTTP查询用例，验证三种终态、不暴露输入值、错误方法和未知ID。
- Python输入契约新增5项；该文件30项通过，Ruff/mypy/OpenAPI通过。
- 浏览器UI证据见evidence/f3-input-recovery/browser-ui.md。

首轮HTTP恢复测试6项失败，原因包括测试resetModules后动态导入连接配置产生不同实例，以及新增测试未隔离localStorage。API复用已有静态配置导入；每个网络夹具独立存储后重新测试通过。没有删除断言或把失败记为通过。

全量前端131文件/1592项通过，renderer/main/preload构建通过，21项脚本检查通过。

## 尚未完成

完整独立runId、服务epoch、输入队列、跨工作区协议、其他交互命令以及正式Electron生命周期仍待验收。未知请求不恢复用户输入；网络永不返回时的请求超时/取消仍需统一服务层处理。F1/F3不因本批标记完成。
