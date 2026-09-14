# 语音通知请求合同

状态：前端合同已实现，真实后端待接入。2026-09-14；范围仅既有保留节点 text_to_speech 的前端服务消费。

来源：冻结 WebRPA basic.py TextToSpeechExecutor、main.py request_tts_sync 和 Studio 的语音播报表单。保留 text/lang/rate/pitch/volume；新增 workflowId/nodeId 绑定目标。语速/音调接受当前表单范围0.5至2，音量0至1，缺省由节点配置提供1；请求中的错误值不静默覆盖。界面保持中文，语音语言是业务参数。

与脚本复用命令确认机制：GET /api/events/tts-requests/{requestId} 读取 pending/claimed/completed/failed/expired；tts_claim 携带 requestId/claimId；tts_result 携带相同身份、布尔success及失败error。命令使用稳定commandId，响应丢失查询原命令，不重播。请求在运行内稳定，同请求只能被一名客户端领取；已领取却无法确认结果时不得重新朗读。

领取确认后使用 SpeechSynthesis；成功以onend确认，错误/缺失能力明确返回失败。60秒操作上限，停止/终态/显式断开取消本次朗读并清除监听，迟到onend不提交新结果。普通SSE重连保留当前请求，重复事件不重播。Mock节点等待确认后才继续；失败停止后续、停止后请求过期。

测试覆盖正常、错误、无能力、超时、取消、零音量、重复领取/结果、响应丢失、外来所有者和重连。Mock不提供系统语音回退，也不声称音频监听或真实浏览器操作；未来后端负责持久化命令与请求身份，不能把未确认的前端动作当作未发生而自动重播。
