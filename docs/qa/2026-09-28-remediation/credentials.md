# SEC-03 工作区凭据隔离

日期：2026-09-28。状态：本机隔离回归通过，完整 UI 切换/打包验收待最终阶段。置信度：高（本机范围）。提交：见本文件所在修复提交。

根因是旧秘密键仅由名称 hash 决定，而元数据按工作区 SQLite 隔离。同名凭据因此能互相覆盖、重命名或删除。

最终行为：studio_credential_state 新增持久 UUID，在 BEGIN IMMEDIATE 事务内只初始化一次。所有读写、字段修改、重命名、删除共用 `studio-credential:v2:<workspace UUID>:<name hash>`。移动工作区及服务重启保留身份。创建独立数据库得到独立身份；复制整个数据库是同一逻辑工作区的备份，不是“克隆为新工作区”功能。当前没有新增克隆语义。

旧键无法证明归属，系统不自动读取、认领、迁移或删除。元数据存在但本工作区秘密不存在时返回 CREDENTIAL_REENTRY_REQUIRED（409）；用户在现有编辑入口重新录入全部字段即可恢复。只录入部分字段不会与旧全局秘密拼接。UI 说明空值与重新录入方式。删除只操作本工作区新键和元数据，原全局条目保留。

改动：application/workflows/credentials.py、infrastructure/database/studio_credentials.py、workflow_models.py、新增 0024_studio_credential_namespace.py、CredentialSettings.tsx。

## 证据

- credentials-before.log/xml：4 个新隔离检查，旧行为 3 失败、1 通过；使用真实迁移 SQLite，系统存储在单元边界替代。
- credentials-expanded-before.log/xml：扩展回归 20 通过、6 失败；均为旧测试期望敏感输出事件 value=null，而当前 project_graph 明确不输出 sensitive_variables。修改期望为不存在输出事件，同时新增节点生命周期及秘密不落持久事件的断言，未改变生产脱敏行为。
- credentials-after.log/xml：26 通过，含真实生产 worker、SQLite 与凭据管道、契约测试。
- credentials-ui.log：6 文件、109 测试通过。
- real_credentials.py → credentials-native.json：两个独立真实 SQLite、macOS SystemCredentialStore、专属 UUID 条目，9 个检查全部通过。包括同名隔离、重命名、删除、重启、旧键拒绝/显式恢复及最终清理。仅本次测试条目被删除，输出无秘密。
- 定向 Ruff 和普通 mypy 通过；前端 tsc 通过（electron-typecheck.log，包含同时进行的入口安全修复）。

## 升级与恢复

0024 是新增 nullable 字段的兼容迁移，不改任何历史迁移，不读取系统秘密。新建测试库通过全部历史迁移再升至新 head；现有真实用户库未被本次脚本打开或迁移。

升级前保留一致 SQLite 备份。恢复应同时恢复对应版本代码及数据库备份；单独 downgrade 删除 UUID 后再 upgrade 将创建新身份，必须重新录入秘密，旧 v2 条目仍保留。旧版本本身有已确认隔离缺陷，因此恢复旧代码不代表安全修复仍有效。没有自动清理无法归属的历史系统条目。

Windows 系统凭据、macOS Intel、完整 UI 切换及打包应用验收尚未执行；不得从本机 Keychain 结果推定通过。跨进程同时修改同一逻辑工作区的系统秘密仍沿用原单宿主所有权，不宣称新增分布式原子事务。
