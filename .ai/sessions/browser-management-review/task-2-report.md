# 任务 2 完成报告

- 日期：2026-09-12
- 状态：confirmed
- 范围：profiles 领域校验、SQLAlchemy/Alembic 浏览器资源数据库、路径与启动迁移、对应单元/集成测试。

## 改动

- 新增纯 Python `ProfileSpec`/`Profile` frozen dataclass、ProfileValidationError 与 ProfileRepository Protocol；领域层不导入 FastAPI 或 SQLAlchemy。
- 覆盖全部计划字段：起始网址、locale/timezone、viewport、UA、主题、扩展、高级参数、浏览器版本/版次/渠道及代理模式互斥值。公开版只接受 Stable，高级参数拦截危险启动参数。
- 新增 SQLAlchemy 2 映射和 Profile 仓储；增加 `profiles`、`proxies`、`proxy_pools`、`kernel_settings`、`kernel_operations` 表。代理表保持最小字段，供后续查询和引用完整性使用。
- 新增 Alembic 首个迁移，`migrate_database` 对嵌套空库和重复 upgrade 幂等；`create_session_factory` 支持事务上下文及 engine dispose。
- AppPaths 增加 `workspace/profiles` 与 `data/kernels`，应用启动先创建目录并迁移数据库；迁移失败会阻止应用创建完成。
- 更新 backend 依赖、uv.lock 和结构说明。

## 验证

```text
uv run --directory apps/backend pytest -q
18 passed, 2 warnings

uv run --directory apps/backend pytest tests/unit/test_profile_validation.py tests/integration/test_browser_database.py -q
7 passed

uv run --directory apps/backend ruff check ...
All checks passed

uv run --directory apps/backend mypy src/autoflow/domain src/autoflow/infrastructure/database src/autoflow/bootstrap
Success: no issues found in 18 source files
```

## 规格自审与疑虑

- 已验证空库首次迁移、连续两次迁移、engine 重建后完整字段往返及路径启动迁移。
- 当前任务只实现存储和领域校验；代理/内核业务用例、HTTP API、目录安全删除和内核 worker 属于后续任务。
- locale 校验采用轻量 BCP47 形态检查；更完整的语言标签策略应在 API/schema 任务中补充。
- Alembic 配置以包内 `alembic.ini` 为入口，未引入项目根级迁移配置。

## 独立复审修复（2026-09-12）

- `main()` 现在先完成 `create_app()` 及数据库迁移，成功后才绑定监听端口并输出 ready；失败测试确认迁移异常时 stdout 不含 ready。
- 高级参数校验同时拦截 `--option=value` 和 `--option value`，覆盖代理与用户数据目录绕过形式。
- 补齐 URL host、BCP47 形态、timezone、viewport 错误转换、browser edition/channel、human preset、color scheme 和非空 browser version 校验。
- 数据库验收改为完整 Profile 对象往返，并增加两个独立 session 竞争同名配置、唯一约束失败后 rollback/session 可继续查询的测试。

```text
聚焦测试：23 passed
全量后端测试：34 passed, 2 warnings
ruff：All checks passed
mypy：Success: no issues found in 19 source files
```

## 独立复审修复 2（2026-09-12）

- URL 解析现在主动求值 hostname/port，并将畸形 IPv6、非法端口等 `urlparse` 错误统一转为 `ProfileValidationError`。
- timezone 将空 key、绝对路径、系统路径错误等 ZoneInfo 异常统一转为领域错误。
- locale 改为按 BCP47 子标签结构解析，支持 extension、private-use 和 grandfathered 标签，拒绝重复 region、重复 variant/singleton 与缺失 extension/private-use 内容。

```text
ProfileSpec 聚焦测试：29 passed
全量后端测试：46 passed, 2 warnings
ruff：All checks passed
mypy：Success: no issues found in 19 source files
```
