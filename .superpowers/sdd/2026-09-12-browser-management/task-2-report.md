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
