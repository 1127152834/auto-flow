// Source: WebRPA@5ccb900e, components/workflow/documentation/content-notify.ts; see SOURCE.md for license and adaptation boundaries.
export const notifyGuideContent = `# 通知配置

> 当前 Studio 教学范围只保留 Telegram 和自定义 Webhook 的前端配置。Mock 用于交互演示，真实发送需要正式后端支持。

## Telegram 通知（notify_telegram）

配置 Bot Token、Chat ID、消息内容和格式。Bot Token 可通过 Telegram 的 BotFather 创建，Chat ID 由目标会话提供。编辑器只保存配置，不表示消息已经送达。

## 自定义 Webhook（notify_webhook）

配置目标 URL、请求方法、请求头和请求体。请在正式服务接通后验证目标接口及响应；编辑器预览不执行外部请求。
`
