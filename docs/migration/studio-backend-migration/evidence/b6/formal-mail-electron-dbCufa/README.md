# B6 邮件节点正式窗口验收

`result.json` 记录 macOS arm64 开发构建：正式 Studio 通过真实 UI 配置、保存、切换、重开并运行 `send_email` 和 `email_trigger`。生产执行器使用原有 `smtplib` / `imaplib` 客户端，连接本地受控 TLS SMTP/IMAP 端点；仅把硬编码的 QQ SMTP 地址在本次临时测试进程中映射到回环端口。SMTP 已实际收取一封中文 MIME 邮件并关闭连接；IMAP 按发件人和主题筛选并标记两封邮件已读。临时授权码未出现在运行日志或报告中。

本证据不宣称外部 QQ 邮箱交付，也不宣称 macOS Intel、Windows 或冻结包通过。临时工作区和证书已清理，未修改用户数据库或生产网络设置。
