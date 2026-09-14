# Task 11 参数批次持久化审查

2026-09-15，confirmed；范围仅原子启动/UoW/迁移。尚未包含用户启动页面、HTTP或真实批次执行。

规格审查后工程复核均通过，独立审查者 pm3_management_components_quality。

| 问题 | 修复与证据 |
|---|---|
| P1 嵌套 DTO 日期不能 JSON 保存 | 分别转换 automation 与 batch DTO 的日期；共享 helper 不改。真实 SQLite 启动验证通过。 |
| P1 DBAPI COMMIT 抛错后连接仍持有未提交事务 | commit 异常调用 Session.invalidate；物理 COMMIT 故障 RED 复现，后续读取无残留、下一次 start 可用。 |
| 请求或配置后续变更污染快照 | 独立 Task 身份及不可变参数映射；原请求修改后数据库保持原值。 |
| 归档后原键找回/提交确认丢失 | 独立故障验证原接受快照、1 Batch/2 Task，无重复执行创建。 |

主协调定向核验：原子启动/迁移/UoW/规则 47 passed；独立两个集成文件20 passed；核心共享事务相关64 passed是最终COMMIT修复前回归，不能代替最终修复的47项。
Ruff通过，mypy241源文件通过，唯一Alembic head pm04_project_runs。主项目只读。

未执行：Task12运行协调、HTTP、管理页面E2E；Windows/其他架构/打包/用户手测。
