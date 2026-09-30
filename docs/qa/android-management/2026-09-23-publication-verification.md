# 2026-09-23 AM4 备份发布与失败隔离

日期：2026-09-23。状态：本增量 `passed`，完整目标 `active/partial`。基线 `codex/android-management-complete@715cdb16`，代码与本证据在同一增量提交；未覆盖既有 3 个 Studio 文档修改。

## 行为变化

- 备份根目录不再解析并接受符号链接；根、staging、final 及单个备份目录均保持 0700，归档及 manifest 保持 0600。
- 摘要与字节数在 staging 中计算。任何读取失败都发生在发布前，避免发布后读盘失败留下孤立 final。
- 发布前 fsync 文件及 staging 目录；rename 后 fsync 源/目标父目录及根目录和其父目录。rename 后同步失败会清理本次创建的 final；不删除已存在的备份。
- `complete_backup` 使用同一 SQLite 事务写入备份记录与操作 succeeded，条件绑定 workspace、device、requestId、requestDigest、action 和 running 状态，无迁移/API 形状变更。
- 提交异常后重新读取操作和备份记录：已确实提交则保留归档并返回已核实结果；确认未提交则清理本次 final；无法核实则保留文件、记录 needs_verification 并阻止同请求重放。修复重复推进终态造成的状态冲突掩盖原始错误。
- 在提交前取消保持取消信号，不生成 available 记录；已提交后取消不能撤销实际成功事务。

## RED → GREEN

| 实际命令/阶段 | 实际输出 |
| --- | --- |
| `uv run pytest tests/unit/test_android_backup_storage.py -q`（实现前） | `4 failed, 4 passed in 0.11s`：根链接、宽松权限、fsync 顺序和发布后同步失败 |
| `uv run pytest tests/integration/test_android_backups.py -q`（记录写失败） | `1 failed, 8 passed in 1.92s`：重复终态转换导致 `ANDROID_OPERATION_STATE_CONFLICT` |
| 同命令（加入原子事务与回执丢失测试、实现前） | `3 failed, 8 passed in 2.35s` |
| 同命令（加入提交前取消测试、修复前） | `1 failed, 12 passed in 2.62s`：取消被错误转换成普通错误 |
| `uv run pytest tests/contract/test_android*.py tests/unit/test_android*.py tests/integration/test_android*.py tests/integration/test_migration_heads.py -q` | **`328 passed, 2 warnings in 16.02s`** |
| `uv run ruff check src/autoflow/providers/android/backup_storage.py src/autoflow/application/android/backups.py src/autoflow/infrastructure/database/android_operations.py tests/unit/test_android_backup_storage.py tests/integration/test_android_backups.py` | `All checks passed!` |
| `uv run python -m compileall -q src/autoflow` | exit 0 |
| `uv run alembic -c src/autoflow/infrastructure/database/alembic.ini heads` | `am01_management_operations (head)` |
| `npm exec --offline --yes --package=node@22.23.2 -c 'node --version && npm run openapi:generate && npm run openapi:check && npm run test:structure'` | Node `v22.23.2`，OpenAPI generate/check exit 0、无生成 diff；结构 `4 passed` |
| `git diff --check -- apps/backend .ai docs/qa/android-management` | exit 0 |

pytest/Ruff/compileall/Alembic 在 `apps/backend` 执行；npm/git 在根目录。警告为现有 Starlette anyio 废弃别名、故意重复 ZIP 条目测试。

新增 14 项自动测试使用真实文件系统和 SQLite，替换 Docker IO 或在 write/read/fsync/rename/数据库 flush 边界注入异常；覆盖 ENOSPC、权限、文件/父目录同步、rename、记录写入、事务回滚、提交回执丢失、取消、结果无法核实，以及重建 repository 后无可用伪结果且不重放。**这是可重复故障注入，不是实际填满磁盘、拔盘或断电。**

## 真实验证

命令：`uv run --project apps/backend python /tmp/autoflow-publication-smoke-20260923.py > /tmp/android-publication-real.log 2>&1`，exit 0。

[原始结果](2026-09-23-publication-result.json)，[实验脚本](2026-09-23-publication-smoke.txt)。脚本固定一次性隔离路径，拒绝复用 workspace。

- 源 `240402a1-83ba-44a1-884e-7bef621076c6` → 新目标 `194d09a0-0a44-4025-8579-8f60952a6a4f`。
- workspace hash `683d1bdbf5db84a8d34a380279b45097c3ab46e44446f84bde979d590da6420a`，相同镜像摘要 `sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b`。
- 备份通过真实 macOS 文件/目录同步和 SQLite 原子提交，包含 manifest 共 `18,274,988` bytes。
- 目标卷归档中测试文件 UID10001/GID2000/mode0640、相对/绝对内部符号链接与硬链接均与源一致；新实例启动后经三条路径读回 `metadata-proof`，源测试条目保持不变。
- 两个实例容器/卷均清理为 0、deleted=true；测试备份已删除。确认无运行中容器后将 Lima 停回 Stopped。
- 本轮真实链验证正常发布/恢复，故障边界证据来自上面的文件/SQLite 故障注入，未冒充真实设备故障演练。

## 未完成与风险

本增量没有前端修改，未重跑前端全量/type/lint/build；历史结果见 [前端验证](2026-09-23-frontend-validation.md)。全量 backend/Ruff/frontend/scripts 的既有失败仍需修复，完整分支审查尚未完成。

T17 的原子备份发布已补齐，但进程硬中断后孤立 staging/final 的受控核实与清理仍待实现；结果无法核实时保留文件是当前保护策略。T18 恢复到新卷的部分写入/取消/进程重启和 xattrs 能力仍未验收。模块临时文件、高级日志、应用会话重建核实、1/5/10 指标等仍是软件或未执行验证事项。GApps 候选镜像/网络/账号条件为 blocked；不能把软件待办归为环境阻塞。

本增量结论置信度：高。完整目标仍未达成。
