# F1/F5：凭据元数据协议与确认

2026-09-14。置信度高：下面限定范围已测试；凭据配套能力整体尚未关闭。

## 本批交付

- GET 列表/名称、POST upsert/改名、DELETE 动态名称按方法分派，不让 names/rename 静态地址吞掉合法删除。不存在的删除为 404。
- 名称按数据处理，包括 __proto__、constructor、中文及保留路径词。空名称/空字段拒绝；错误类型拒绝。
- 部分 upsert 保留遗漏字段元数据，空描述保留原描述，与冻结服务一致。Mock 只存字段名和掩码，不存提交的字段值。
- 改名校验原名、目标冲突及同名无损行为；失败不改已有数据。
- 请求/响应加入 workflow_studio_schemas 与 OpenAPI 生成类型；api.ts 不再自定义 CredentialItem。保留 created_at、updated_at、old_name、new_name 线格式。
- 三种写操作统一检查 success 布尔确认；保存还须返回对应名称。矛盾错误包、缺少名称和错误名称不能关闭表单。旧连接的回执不作为当前连接成功。

## 测试证据

- 修复前协议 30 项中 26 失败；补充后协议共 40 项，内存/本地实际 HTTP 各 20 项。
- 新回执测试 21 项，修复前 18 失败，修复后全通过。
- 与既有表单/传输测试合计 5 文件 89 项通过；新增 Python 合同 22 项通过。
- TypeScript、ESLint、49 项脚本检查、Ruff、mypy（202 源文件）、OpenAPI 一致性、renderer/main/preload 构建通过。完整输出见 evidence/f5-credential-protocol。
- 浏览器完成已有测试元数据的编辑 → 保存 → 刷新回显，见 browser-validation.md。
- 上一轮全量 269 文件/3,123 用例不覆盖本批新增测试，不以它冒充本批全量回归。

## 源码对应及交接限制

依据 reference/WebRPA/backend/app/api/credentials.py 与 services/credential_manager.py。改名目标冲突继续采用 AutoFlow 已有 409（旧服务 ValueError 映射 400）；缺失为 404。HTTP 方法错误 405。请求形状错误 422，空名称/空字段在 Mock 业务验证为 400；未来注册正式路由时应保留此映射，不能直接把 DTO 验证错误统一当 422。

本批没有新增真实业务路由或数据库。凭据改名界面、字段移除/改名、可引用命名语法、修订/幂等与配置离开协调仍见 credential-contract-gaps.md。路径含斜杠的历史名称没有完成跨实际路由匹配验收。DTO 的静态类型不替代所有消费者的运行时读校验。
