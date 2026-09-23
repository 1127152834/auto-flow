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

## 2026-09-15：原子字段变更合同与消费闭环

本节取代此前「字段移除/改名尚未实现」的前端及 Mock 结论。冻结 `reference/WebRPA/backend/app/api/credentials.py` 只有 list/names/upsert/rename/delete，没有字段删除或改名命令；冻结 credential_manager 的 upsert 合并旧字段，不能用于字段删除。因此按已批准缺口增加独立合同，没有修改旧 upsert 的合并、空值保留或描述空值兼容语义，也没有新增真实自动化服务路由。

`POST /api/credentials/fields` 请求使用生成 DTO StudioCredentialFieldsCommand：

```json
{"commandId":"stable-command-id","name":"凭据名称","expectedRevision":1,"operations":[{"kind":"rename","key":"password","newKey":"api_key"},{"kind":"remove","key":"obsolete"}]}
```

命令只携带名称与字段键，不读取或发送旧秘密值。成功响应为 `{success:true, commandId, credential, mock:true}`，credential 为完整打码元数据和新的 revision。API 同时校验命令 ID、凭据名称、递增修订、元数据结构和操作结果，不能把 HTTP 200 或不相关回执当成功。

- list 对旧记录缺少的 revision 初始化为 1；独立字段命令、既有 upsert、rename 均推进修订。持久化全局递增计数保留删除历史，因此删除重建同名记录不会复用旧 revision。
- 校验整批操作后才修改：拒绝缺失源字段、重复源、已占用目标、重复目标、非法请求及删除全部字段。目标即使在同批删除仍判冲突，不引入隐含交换/执行顺序语义。错误保留整条记录。
- Mock 将 entries、revision 和 commands 回执放进同一个版本化存储信封，以单次 localStorage 写入提交；写入失败返回 507，无部分记录或回执落地。旧凭据字典兼容读取。打码值保留；不存测试明文。
- 同 commandId 与相同标准化请求重试返回原回执，不二次修改；同 ID 不同请求返回 409。回执在每次请求从存储重读，可处理提交后响应丢失。只保留已确认成功命令的回执；失败校验不占用 ID。
- 请求 revision 与当前记录不符返回 409。命令回执代表当次提交结果，之后若另有修改，UI 成功后重新读取列表取得最新状态，不将旧回执覆盖当前记录。

真实入口 GlobalConfigDialog → 凭据库 →「管理字段」复用现有编辑表单：只展示打码值，允许已有字段改名/删除，单次保存整批提交；普通内容编辑仍通过旧 upsert，两者不串成伪事务。取消未提交草稿不写；冲突保留输入并允许取消/刷新重开；未确认的网络失败、5xx 或无效回执保留同 commandId 与固定输入，锁定取消/离开，用户再次保存以原命令恢复。工作区/连接变更仍沿既有边界禁止旧编辑向新服务发送；不得以该保护宣称应用崩溃恢复未提交草稿。名称/字段引用仍需手动更新。

验证：credential-fields-protocol.test.ts 内 memory/真实本地 HTTP 相同的 22 项，另有 3 项 API 无效回执；credential-rename-entry.test.tsx 9 项真实组件入口（本次新增字段编辑、取消/最后字段、并发冲突、提交后响应丢失恢复 4 项）。关联 7 文件 143 测试通过；Python DTO 31 项通过；桌面 typecheck 通过，最终打码字段表单 9 项组件复验通过；ESLint、Ruff、OpenAPI 生成一致性通过。日志见 [前端回归](evidence/f5-credential-fields/frontend.log)、[DTO 测试](evidence/f5-credential-fields/pytest.log)。

真实后端交接：用事务或原子文件替换同时提交秘密字段变更、revision 和命令回执；在服务端移动原密文/秘密值，禁止将秘密返回管理 UI；保证同请求幂等、同 ID 异请求冲突、修订比较及持久化失败传播。当前完成的是前端合同消费与 Mock 元数据实现，未证明真实秘密存储、加密原子落盘、真实凭据注入或 Electron 原生交互。

定时停止交接：本切片未提交；未执行整合 Electron 构建或原生 UI 验证。已完成日志保存在 evidence/f5-credential-fields/。恢复从主任务整合构建/原生凭据入口验证开始，不需重新实现字段命令。

## 真实运行消费接入（2026-09-23，macOS arm64 开发及正式包已验收）

上文历史Mock/字段管理的验收边界保留；本项补真实worker此前未注入CredentialReader的缺口。沿冻结源get_field与现有resolve_value支持`{{凭据:名称.字段}}`、`{{cred:名称.字段}}`及省略字段时value，不提前改写流程或复制整库秘密。缺失字段、读取失败保留原文字面量；停止通过CancelledError结束，不伪装为空凭据成功。

既有受管管道新增内部`credential:read/runId/requestId/name/field`与`credential:result/requestId/value`，不构成renderer HTTP/SSE能力。manager验证runId与受管worker一致，父协调器通过同一StudioCredentialService读取系统秘密；响应只进入该worker stdin。stdin唯一读取线程直接唤醒同步解析器，重复/过期请求不应用，EOF/停止解锁等待。子流程和自定义模块继承同一reader。

原生系统凭据库可能等待弹窗。父读取只有3秒等待预算、每run最多一个未返回读取；停止先结束所有权等待，迟到结果丢弃。底层调用留在daemon线程中自然收尾，不占住worker或sidecar退出。实际管道写锁内再次拒绝stopping运行的秘密响应。没有新增秘密文件/明文DB/第二凭据存储；秘密跟踪继续复用现有上下文脱敏。

[证据与边界](../studio-backend-migration/evidence/shared-services/credential-runtime-2026-09-23/result.json)：真实UI保存临时系统凭据→节点写入引用→CloakBrowser密码框输入→受控页面返回正确性标记→保存重开日志→UI删除临时凭据；测试检查明文不进入持久日志、SSE或普通结果。运行执行器测试与系统秘密存储实测分别记账。正式包在同证据记录核销，不据此宣称项目资源ACL或所有外部集成完成。

最终包 `formal-electron-ZMGYx6` 含空名称/字段兼容修正并通过同一真实UI链；此前 `znjbwe` 为前一候选证据，不作为最终构建替代。82项关联回归、最终8项实际worker及5项读取/写锁测试、Ruff/mypy/OpenAPI/目录检查通过。Windows及Intel未实测。
