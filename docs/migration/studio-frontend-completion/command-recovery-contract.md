# 停止目标与命令响应恢复（F1 局部合同）

日期：2026-09-13；状态：局部实现并验证，总 F1/F3 未完成。

## 合同

- POST /api/events/commands 必须含非空 commandId、event。相同ID/相同请求重取同一状态码和结果；不同请求409。接受和拒绝的结果均缓存。
- GET /api/events/commands/{commandId} 返回同一结果、commandId与原始httpStatus；不存在404。查询只读，不重新执行命令。
- execution_stop 的 data.workflowId 必须匹配当前目标。错误目标409且当前运行保留；已经完成的目标停止幂等成功，不重复终态事件。
- POST /api/workflows/{id}/stop 同样核对目标，不允许旧路径终止另一流程。
- StudioEventClient.emit返回本次commandId，可显式传入原ID。正常响应用command_result/command_error报告；传输或响应读取失败后查询原ID，不重发POST。查询失败报告status=unconfirmed，界面显示尚未确认。HTTP接受不代表所有后台动作已应用；运行状态仍取确认事件。

## 证据

- transport-parity.test.ts：内存/真实HTTP均验证错误目标保留当前运行、正确停止和重复停止只产生一次终态、原ID成功/拒绝查询、未知ID及缺标识。
- command-recovery.test.ts：已接受响应丢失时查询、查询失败保持未确认，两条测试通过。
- command-http-recovery.test.ts：真实loopback服务处理POST后销毁连接；前端查询恢复，服务端只收到一次POST。测试通过，无浏览器自动化动作。

## 必须保留的缺口

现有源接口以workflowId识别运行，同一文档先后运行缺少独立runId；迟到请求针对同workflowId的新一轮不能靠本补丁完全区分。F3冻结独立执行身份后需要贯穿事件/控制/结果。本阶段命令记录和完成目标仅在服务内存中，重启恢复、持久命令、完整权限、所有事件业务应用及容量上限尚未验收。不要将set_verbose_log夹具的接受结果写成真实后台执行。

本批完整检查：96个测试文件、1,133个用例通过；typecheck、lint、renderer/main/preload构建通过。日志见f1-command-tests/checks/build.log；socket主动断开实测见f1-command-http.log。
