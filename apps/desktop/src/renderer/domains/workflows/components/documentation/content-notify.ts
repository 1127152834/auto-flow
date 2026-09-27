// Source: WebRPA@5ccb900e, components/workflow/documentation/content-notify.ts; see SOURCE.md for license and adaptation boundaries.
export const notifyGuideContent = `# 通知渠道

> 桌面正式入口连接本机后端。运行前请配置节点所需资源，执行结果以当前运行日志和实际产物为准。

当前动作库提供 Telegram 通知和自定义 Webhook 两种通知入口。

## Telegram 通知（notify_telegram）

配置 Bot Token、Chat ID 和消息内容。Bot Token 可引用凭据库，Chat ID 指定实际接收会话。节点运行会向配置的会话发出真实消息；配置页面本身不会发送。服务拒绝、连接失败等结果会显示为节点失败。

## 自定义 Webhook（notify_webhook）

配置 Webhook URL 和消息内容。消息是有效 JSON 时按原 JSON 发送；普通文本会转换为含 message 字段的 JSON 对象。默认使用 POST 和 application/json，HTTP 2xx 才报告发送成功。需要自定义请求头、方法或保存响应时，使用 Webhook 请求节点。

## 配置与结果

通知应连接到需要发送的业务分支；消息可以引用流程变量。发送失败后先核对运行日志和接收端记录，避免重复发送。成功仅说明接口接受请求，实际接收结果应在目标会话或接收服务核对。

工作流中的桌面通知、语音播报和用户输入见[通知与交互](notifications-guide)。
`
