# 后台启动失败：恢复缺失迁移历史

日期：2026-09-26。状态：confirmed。来源：用户截图、真实 sidecar 日志、现有集成 Git 历史、数据库副本和桌面 UI 验证。

## 根因与修复

开发版 Electron 已打开，但后台日志报 `Can't locate revision identified by '0023_merge_studio_android'`。只确认 Vite HTTP 200 或 Electron 进程不足以宣称应用启动完成。
用户当前工作区数据库已由集成版本升级至 `0023_merge_studio_android`，而 `codex/project-management-pm9` 缺少相关 6 个迁移文件；此问题与代理切换请求无关。
从现有提交 `1bc6b24d` 原字节恢复以下文件，不降级、stamp、删除或新建用户业务数据库：

- `pm09_shared_sheet_identity.py`
- `pm10_shared_sheet_cursors.py`
- `am01_management_operations.py`
- `0020_merge_android_pm9.py`
- `0022_merge_studio_pm10.py`
- `0023_merge_studio_android.py`

这些是已有迁移历史的恢复，不代表相应 Android/共享表业务功能全量合入。数据库版本关系及迁移内容沿用原提交，测试固定其 SHA-256 防止后续改写。

## 验证

- 先修改迁移头契约并增加旧版本升级、集成版本重复启动的数据保持测试，观察 **3 failed / 1 passed**，其中包含与实机相同的缺失 revision 错误。
- 用 SQLite read-only 连接将真实工作区备份到权限隔离的临时目录，只对副本调用迁移；修复后迁移成功，完整 SQL dump 的 SHA-256 前后相等，integrity_check 为 ok。
- 数据库迁移头、共享表 identity/sync/recovery 和外键定向测试 **24 passed**，1 条既有 Starlette 弃用警告。
- 增加历史文件摘要锁定并格式化后，迁移头测试再次 **4 passed**。
- Ruff 检查修复涉及的 Python 文件；mypy 全后端通过。业务前端未修改。
- 在真实 Electron 设置页点击“重启服务”，AX 观察由“启动失败”转为“本地服务正常”“本地服务已连接”“运行正常”，访问范围“仅限本机”，API v1。supervisor 的 ready 状态已经过带身份验证的健康检查。
- 原工作区未提交文件保留；未发起供应商代理写入、未推送或发布。

运行命令：

```sh
PYTHONPATH="$PWD/apps/backend/src" apps/backend/.venv/bin/python -m pytest -q -c apps/backend/pyproject.toml apps/backend/tests/integration/test_migration_heads.py apps/backend/tests/integration/test_project_sheets_identity.py apps/backend/tests/integration/test_project_sheets_sync.py apps/backend/tests/integration/test_project_sheets_recovery.py apps/backend/tests/integration/test_database_foreign_keys.py
PYTHONPATH="$PWD/apps/backend/src" apps/backend/.venv/bin/python -m pytest -q -c apps/backend/pyproject.toml apps/backend/tests/integration/test_migration_heads.py
apps/backend/.venv/bin/mypy apps/backend/src
```

本机临时测试输出为 `/tmp/autoflow-startup-migration-red.txt`、`/tmp/autoflow-startup-migration-green.txt`、`/tmp/autoflow-startup-mypy.txt`。Windows 与打包环境未重新验收。
