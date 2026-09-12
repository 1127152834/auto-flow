# ProxyPanel v1 脱敏契约样本

- 日期：2026-09-12
- 状态：fixture-verified（真实字段结构；值已替换）
- 来源：用户授权“补齐实现真实代理能力”，使用应用已保存的 API Key，只读调用官方 `https://proxypanel.io/api/v1`；认证值只在内存中使用。

| 文件 | 来源 | 结果 | 范围 |
| --- | --- | --- | --- |
| list-redacted.json | GET /proxies | HTTP 200 | 真实响应为只有 proxies 字段的完整列表，无分页元数据；账户网页与接口均为 6 条。夹具仅保留 1 条有效代理的结构。 |
| credentials-redacted.json | GET /proxies/{id}/credentials | HTTP 200 | 用户授权使用代理后按需读取；独立 HTTP/SOCKS5 端点及认证字段。 |

账号名称、代理 ID、标签、主机、出口 IP、用户名、密码、认证 URL、位置和时间均替换成测试值；不包含原始 Key 或原始认证 URL。测试主机使用 `.example.test`，密码为字面值 `test-password`。数值不能用于推断真实账户情况。

实际账户还观察到 expired 状态。单元测试修改状态、删除字段、空列表、非法端口/日期/ID、重复记录和分页扩展均为 synthetic 异常测试；不声称这些异常是服务端实际返回。未知包装或分页元数据会拒绝同步并保留本地数据；未观察到多页账户，不推断未验证的分页规则。

映射：id → provider_id；label → name；state → remote_status；location → 城市/州/运营商；last_ip → exit_ip；connection.http_port/socks5_port → 各协议端点；expires_at → subscription_expires_at。时间必须带时区。公开投影不保留 connection.username 或 credentials_url。

凭据读取只使用固定官方来源及校验后的 ID，不访问响应里的 credentials_url/http_url/socks5_url。数据面用户名和密码按操作读取、仅在进程内使用；不写入 SQLite、fixtures 或系统凭据库。系统凭据库持久保存的仍只有用户录入的 API Key。
