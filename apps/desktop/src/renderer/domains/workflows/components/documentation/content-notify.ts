// Source: WebRPA@5ccb900e, components/workflow/documentation/content-notify.ts; see SOURCE.md for license and adaptation boundaries.
export const notifyGuideContent = `# 通知配置

> 当前 Studio 教学范围为保留节点及前端配置交互。Mock 用于交互演示，不执行真实网页、模型或系统操作；文中的执行行为需正式后端支持。

本章介绍 AutoFlow 支持的 Telegram 和自定义 Webhook 两种通知渠道，让工作流在完成、出错或达到特定条件时，自动向你发送通知。

---

## 概述

当前保留 Telegram 和自定义 Webhook 通知，使用对应节点配置连接和消息参数。

| 模块 | 适用场景 |
|------|----------|
| Telegram | Telegram 用户、群组或频道 |
| 自定义 Webhook | 任意 HTTP 接口 |

---

## Telegram 通知（notify_telegram）

通过 Telegram Bot 发送消息。

**获取 Bot Token**：
1. 在 Telegram 搜索 \`@BotFather\`
2. 发送 \`/newbot\` 创建机器人
3. 获得 Token（格式：\`123456789:ABC-DEF...\`）

**获取 Chat ID**：
- 向机器人发消息后，访问 \`https://api.telegram.org/bot{TOKEN}/getUpdates\`
- 找到 \`chat.id\` 字段

**配置项**：

| 参数 | 说明 |
|------|------|
| Bot Token | Telegram 机器人 Token |
| Chat ID | 目标会话 ID（可以是用户/群组/频道） |
| 消息内容 | 要发送的文字 |
| 格式 | Markdown/HTML/纯文本 |

---

## 自定义 Webhook（notify_webhook）

向任意 HTTP 接口发送 POST 请求，最灵活的通知方式。

**配置项**：

| 参数 | 说明 |
|------|------|
| Webhook URL | 目标 HTTP 接口地址 |
| 请求方法 | GET/POST/PUT |
| 请求头 | JSON 格式的请求头 |
| 请求体 | JSON/表单数据 |

---

## 实战示例：工作流完成后发送通知

\`\`\`mermaid
flowchart TD
    A[执行主要任务...] --> B{任务成功?}
    B --是--> C[设置变量\nmsg=任务完成]
    B --否--> D[设置变量\nmsg=任务失败]
    C --> E[发送 Telegram 通知\n内容: {msg}]
    D --> E
    E --> F[结束]
\`\`\`

**配合错误处理使用**：

在条件分支的错误输出路径上添加通知模块，当工作流出错时自动发送告警。

---

## 使用技巧

- **变量引用**：消息内容中可用 \`{变量名}\` 引用工作流变量，实现动态消息
- **多个渠道**：可依次使用 Telegram 与 Webhook 节点通知不同渠道
- **防通知刷屏**：配合条件判断，只在特定条件满足时发送通知
`
