# 安卓管理增量完整门槛与证据边界

- 日期：2026-09-23；状态：`confirmed`（本轮门槛），AM1–AM4 总目标仍 `partial`。
- 来源：隔离 worktree `codex/android-management-complete`，父 HEAD `fe2210dc` 加 T17/T18 恢复归属与客体 tar 增量；真实 Mac 结果见[持久数据属性验收](2026-09-23-persistent-metadata-verification.md)。以下是实际执行输出，不将 fake IO 测试视为设备验收。

| 命令（仓库根目录，后端命令先 `cd apps/backend`） | 实际输出摘要 |
| --- | --- |
| `uv run pytest -q` | exit 0；`3964 passed, 26 skipped, 2 warnings in 845.67s`。两条 warning 分别来自 Starlette/AnyIO 废弃别名及故意重复 Manifest 的 ZIP 夹具。运行开始后仅移除了一个与相邻参数断言重复、名称误称属性保真的测试；生产代码未改，当前定向文件随后重跑。 |
| `uv run pytest tests/unit/test_android_runtime.py tests/unit/test_android_archive_validation.py tests/unit/test_android_backup.py tests/integration/test_android_backup_restore.py tests/integration/test_android_cleanup_files.py -q` | exit 0；当前文件 `118 passed, 1 warning in 6.94s`。此前 RED：恢复目标持久归属 7 例、GNU tar 属性 4 例、根目录与错误路径保护 4 例分别失败，修复后转绿。 |
| `uv run ruff check src tests` | exit 0；`All checks passed!`。 |
| `uv run python -m compileall -q src tests` | exit 0；无错误输出。 |
| `uv run alembic -c src/autoflow/infrastructure/database/alembic.ini heads` | exit 0；`am01_management_operations (head)`，唯一 head；旧迁移未改。 |
| `npm test` | exit 0；`424 Test Files passed, 5595 Tests passed`。 |
| `npm run test:scripts` | exit 0；`95 tests, 95 pass, 0 fail`。该命令会重写三份原有 Studio 目录清单；执行后已恢复其原始未提交内容并逐份校验 SHA-256，未纳入安卓提交。 |
| `npm run typecheck`、`npm run lint`、`npm run openapi:check` | 均 exit 0；分别为 TypeScript 无错误、ESLint 无错误、OpenAPI 生成类型无漂移。 |
| `npm run test:structure`、`npm run build` | 均 exit 0；结构检查 `4 pass, 0 fail`，Electron/Vite 构建 `built in 37.58s`。 |
| `git diff --check` | exit 0；无空白错误。 |

三份受保护 Studio 文档的 SHA-256 分别为 `48cad0b65b70fc9fa43f57f03fb9e3f22a8031179d05be854b3a6443e358e7d0`、`6044837c598e5a0ebdafbfc9eff828f3d608299addacdda795f8fe5a418c8334`、`812d4a8b8c5d0695438e3ca30291a1fb74042f4b62b7ac4b6f974f2a3ee66dcf`，与本轮开始时一致。

真实 Apple Silicon Mac/Lima/ReDroid 的最终恢复脚本 exit 0、JSON `status=passed`：部分写入后 `needs_verification`、直接重试拒绝、正常 HTTP 新卷恢复 202、启动后 ADB 读回、1792 项持久条目及 417 xattrs/55 ACL 源目标摘要一致；三个自建实例最终容器与卷均为 0。另以客体实验确认非默认卷根 UID/GID/mode/xattr、硬链接 inode/链接数、相对软链接文本与内容往返。Lima 已恢复到测试前的 `Stopped`；已有停止状态的其他资源未清理。

完整代码门槛通过不能替代未执行的真实验收。[24 项验收校准](2026-09-23-acceptance-matrix.md)仍列出控制会话人工输入/切端、AM2 账号/网络、AM3 规模指标、APK 真实动作、AM4 磁盘不足/硬中断/高级日志/APK 遗留文件及 T20 完整失败矩阵。SELinux 命令参数已启用，本机没有可验证标签，未声称标签往返通过。
