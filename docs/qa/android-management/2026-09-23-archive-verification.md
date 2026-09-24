# 2026-09-23 AM4 归档安全与文件属性增量

日期：2026-09-23。状态：`partial`；本增量自动化及真实验证 passed，T17–T20 和完整目标仍未完成。代码基线为隔离分支 `codex/android-management-complete@233c09dd`，修复与本证据在同一提交内。3 个 Studio 文档既有改动未覆盖、未纳入提交。

## 已完成

- 整体检查 tar 路径图，允许 `/data` 内的相对/绝对符号链接、链接链及指向已出现普通文件的硬链接；拒绝越界、循环、重复路径、非目录父节点、透过链接写入（不论归档顺序）、未知类型、设备/FIFO、稀疏文件。硬链接必须指向先出现的普通文件，前向链接和硬链接链仍不支持，显式拒绝。
- 恢复使用 `docker cp -a` 保留源 UID/GID。Docker 官方语义依据：[docker container cp](https://docs.docker.com/reference/cli/docker/container/cp/)。本次同时用真实归档往返验证 UID/GID/mode 和链接类型。
- 恢复传入运行时的归档字节直接复用通过摘要校验的内存内容，消除摘要校验后第二次读盘。
- 即使调用方提供 stopped 快照，备份仍在运行时锁内重新 inspect；拒绝将备份恢复到源 deviceId。
- 没有更改 API 数据形状、数据库模型或迁移；OpenAPI 生成无 diff，唯一迁移 head 保持 `am01_management_operations`。

## RED → GREEN 与命令

以下命令在隔离 worktree 下执行；pytest/Ruff/Alembic 在 `apps/backend`，npm 在仓库根。

| 命令 | 实际输出摘要 |
| --- | --- |
| `uv run pytest tests/unit/test_android_archive_validation.py tests/unit/test_android_backup.py tests/unit/test_android_runtime.py -q`（实现前） | `11 failed, 67 passed in 1.41s`；链接误拒、越界/歧义漏检、重复读盘和缺少 archive 标志可观察失败 |
| `uv run pytest tests/unit/test_android_backup.py -q`（新增状态/源保护、实现前） | `2 failed, 15 passed in 0.14s` |
| `uv run pytest tests/contract/test_android*.py tests/unit/test_android*.py tests/integration/test_android*.py tests/integration/test_migration_heads.py -q` | `314 passed, 2 warnings in 14.84s` |
| `uv run ruff check src/autoflow/providers/android/backup_storage.py src/autoflow/application/android/backups.py src/autoflow/providers/android/mac_runtime.py tests/unit/test_android_archive_validation.py tests/unit/test_android_backup.py tests/unit/test_android_runtime.py` | `All checks passed!` |
| `uv run python -m compileall -q src/autoflow` | exit 0 |
| `uv run alembic -c src/autoflow/infrastructure/database/alembic.ini heads` | `am01_management_operations (head)` |
| `npm exec --offline --yes --package=node@22.23.2 -c 'node --version && npm run openapi:generate && npm run openapi:check && npm run test:structure'` | Node `v22.23.2`，generate/check exit 0，结构 `4 passed` |
| `git diff --check -- apps/backend` | exit 0 |

本增量没有前端修改；前端全量、类型、lint 和构建未在本增量重跑，已有准确记录见 [前端验证](2026-09-23-frontend-validation.md)。完整 backend/Ruff/frontend/scripts 的已知失败仍未修复，不以聚焦通过代替最终门槛。

## 真实 macOS/Lima/ReDroid

执行：`uv run python /tmp/autoflow-archive-metadata-smoke-20260923.py > /tmp/android-archive-real-c.log 2>&1`，exit 0。

[归档脚本](2026-09-23-archive-smoke.txt)是本次有固定隔离路径的实验记录；拒绝复用已有 workspace，不是通用可重复运行 CLI。[原始 JSON 结果](2026-09-23-archive-result.json)。

- 源实例 `ef626943-e3d0-4ac5-b84b-c66a65799115`，新目标 `c9af9887-4d5b-4e62-bfed-94a75e5f893b`。
- 镜像 `sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b`，备份含 manifest 总计 `18,241,708` bytes。
- 在已启动源实例中通过 Docker root exec 写入专用测试数据：UID `10001`、GID `2000`、mode `0640`，以及一条相对符号链接、一条 `/data` 内绝对符号链接、一条硬链接。
- 停机备份→全新设备/容器/卷→恢复→重新归档，四个测试条目的 UID/GID/mode/type/link/content 与源一致。
- 目标实际启动完成后，ADB 经三条链接均读取 `metadata-proof`；源卷四个测试条目的内容和属性仍一致。此断言覆盖测试条目，不宣称整个 Android 文件系统逐字节不变。
- 两个实例按标签核验，容器与卷都为 `0`、`deleted=true`；测试备份已删除。确认无其他运行中容器后停回 Lima。
- [前两次失败记录](2026-09-23-archive-attempts.json)保留：第一轮实验脚本 ADB shell 引号错误，第二轮 shell 用户没有 chown 权限。均发生在备份之前，均清理自建实例；第三轮改为 root Docker exec 设置测试属性，通过实际 shell 读取验收。未把失败轮次写成通过，也未改变生产权限绕过检查。

## 剩余风险及后续

- xattrs 仍显式拒绝受识别的 tar xattr 标头；未完成源卷 xattr 检测及经验证的支持能力，不能宣称完整 Android 属性保真。
- 本轮覆盖真实复制与启动，未覆盖恢复部分写入/取消/磁盘不足/权限失败、恢复发布与进程重启核实；新目标失败隔离仍需逐项审计。
- staging→final 已有 rename，但 fsync 耐久性、发布失败后的清理和重启恢复仍待补齐。
- 临时文件清理、高级日志的显式选择/时间/体积限制、应用会话重建核实、1/5/10 性能及完整分支审查仍有工作。
- GApps 候选镜像/账号/网络条件继续 `blocked`；上述软件缺口为未完成，不能标为环境阻塞。

结论置信度：本增量行为高；AM4 完整验收尚无充分证据。
