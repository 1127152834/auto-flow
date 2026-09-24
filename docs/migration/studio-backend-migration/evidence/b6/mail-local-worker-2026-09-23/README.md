# 本地邮件 TLS / Worker 专项

节点范围仅 `email_trigger`、`send_email`。冻结源码版本 `5ccb900e8dcf1530aae66f676d87593c416c7ebb`。

## 证据

- `result.json`：8 项新增真实 TLS/worker 用例逐项断言及边界。
- `pytest.log`：新增用例与已有邮件单元／源码差分／停止测试共 16 项，31.21 秒通过。
- Ruff、mypy 和 diff 检查通过；生产文件没有修改。

本地端点仅支持本用例所需 SMTP/IMAP 协议。真实标准库客户端经过 TLS 握手、认证、MIME 传输和关闭；未用替代客户端或 monkeypatch 成功响应。SMTP 原版固定 QQ 地址，因此 worker 测试启动器只将该地址重定向至临时回环端口，并阻止其他非回环连接。IMAP 通过节点已有 host/port 字段接入回环端口。

## 原版语义核对

- `advanced.py#SendEmailExecutor`：QQ SMTP_SSL、授权码登录、中文纯文本 MIME、收件人和主题结果、认证错误保持。
- `trigger.py#EmailTriggerExecutor` / `trigger_manager.py#_email_monitor_loop`：UNSEEN、发件人/主题子串过滤、读取纯文本、匹配邮件标记已读、失败后重试、最后收到的匹配邮件写变量。
- MIME 容器由原版 multipart/plain 改为现有迁入实现的 EmailMessage/plain；本专项核对解码后的头部和正文语义，不宣称原始邮件字节完全一致。
- SMTP 其他异常使用迁入网关已有中文安全错误，不宣称与原版错误原文完全一致。

## 重现

在 `apps/backend`：

```sh
.venv/bin/python -m pytest tests/integration/test_b6_mail_transport_worker.py tests/integration/test_b6_email_trigger_worker.py tests/unit/workflows/test_email_trigger.py tests/differential/workflows/test_b6_email_trigger_parity.py tests/unit/workflows/test_message_executors.py::test_email_uses_qq_smtp_contract_without_exposing_auth_code tests/unit/workflows/test_external_integration_gateway.py::test_qq_smtp_gateway_sends_utf8_message_without_returning_auth_code -q
.venv/bin/ruff check tests/integration/test_b6_mail_transport_worker.py
MYPYPATH=src .venv/bin/mypy tests/integration/test_b6_mail_transport_worker.py --follow-imports=silent
```

## 未验收

外部 QQ 邮件投递、完整邮件服务器兼容性、证书信任/主机名策略、正式 Electron UI、Windows 与 macOS Intel 未验证。本证据不是外部服务或正式 UI 完成声明。

首轮 7 通过/1 失败：测试遗漏标准 IMAP STORE 的括号；修正为真实协议文字 `+FLAGS (\Seen)` 后通过，未改业务实现或放宽数据断言。
