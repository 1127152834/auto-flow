# 2026-09-23 AM4 清理目录与文件保护

日期：2026-09-23。状态：本增量自动化与真实链 `passed`；完整 T19、AM4 和总目标仍 `active/partial`。基线 `codex/android-management-complete@a47bbb9d`，代码与证据同一增量提交。3 个 Studio 文档既有改动保留。

## 已完成

- 新增 `GET /management/cleanup/resources`，返回当前工作区的保留数据、已登记备份、暂存备份与未登记 final 备份；不是只能由调用方猜测临时文件 ID。Pydantic 与生成的 OpenAPI TypeScript 类型同步，无模型/迁移变化。
- 页面从服务端读取目录，默认不选中，显式选择→预览→确认；刷新失败清空旧目录和预览。结果未知时禁用重新预览/刷新/修改选择，保留原请求核实入口。空态、加载、错误、长 ID 换行和原生键盘可访问 checkbox 均有实现。
- 预览显示来源引用、归属、用途、大小、不可逆影响与指纹；JSON 引用对象不再显示 `[object Object]`。未登记备份只读取有限 manifest 白名单字段；无有效 manifest 时明确显示“来源未核实”，不返回配置内容。
- 文件指纹包含内容摘要、名称、inode、ctime/mtime、权限/归属与大小；不把读取导致的 atime 改变当成内容变化。已登记备份也重新读取受控文件指纹，同大小替换、路径/链接/权限变化返回 409。
- 备份创建、恢复及清理共用工作区文件锁；恢复读取和运行时写入整个期间，清理返回 `ANDROID_BACKUP_BUSY`。未登记 final 只在当前目录中、没有备份记录占用该 ID 时列为候选。
- 清理“保留的数据”要求持久状态明确为 retained；有运行环境或状态未知的实例，即使遗留 `dataRetained=true`，也不列作待清理保留卷。

## RED → GREEN

| 命令/阶段 | 实际输出 |
| --- | --- |
| `uv run pytest tests/integration/test_android_cleanup_files.py -q`（初始实现前） | `6 failed in 1.84s`：无目录入口、同大小变化漏检、无文件锁 |
| `uv run pytest tests/contract/test_android_cleanup.py -q`（新增 GET 前） | `1 failed, 1 passed`：GET 返回 404 |
| Node22 `vitest run src/renderer/domains/android/tests/ManagementTools.test.tsx`（新 UI 前） | `2 failed, 19 passed`：临时对象不可发现/选择 |
| 来源引用测试（实现前） | 后端 `1 failed, 10 passed`；前端源名称未显示，修复后通过 |
| 文件不可读测试（实现前） | `1 failed, 11 passed`：原始 PermissionError 未转成 409 |
| retained 筛选测试（实现前） | `5 failed, 17 passed`：ready/starting/stopped/unknown/缺失状态被误列入 |
| Android 后端 + migration heads 全聚焦 | **`346 passed, 2 warnings in 18.39s`** |
| Android 前端全聚焦 | **`14 files, 104 passed`**，Node22.23.2，7.74s |

后端最初一项旧测试的简化 storage 缺少真实目录接口，改用真实 BackupStorage 和仅包含暂存文件的仓储；保留原“发现并调用受控 discard”断言。页面联调发现空/非法目录响应会使整个页面崩溃，补边界校验和回归；未删除失败断言。

最终命令（pytest/Ruff/compileall/Alembic 在 `apps/backend`，Vitest/type/lint/build 在 `apps/desktop`，OpenAPI/structure 在根目录）：

```text
uv run pytest tests/contract/test_android*.py tests/unit/test_android*.py tests/integration/test_android*.py tests/integration/test_migration_heads.py -q
# 346 passed, 2 warnings in 18.39s

uv run ruff check src/autoflow/providers/android/backup_storage.py src/autoflow/application/android/backups.py src/autoflow/application/android/cleanup.py src/autoflow/adapters/http/android_management.py src/autoflow/adapters/http/android_management_schemas.py tests/integration/test_android_cleanup_files.py tests/contract/test_android_cleanup.py tests/unit/test_android_cleanup_contract.py
# All checks passed!
uv run python -m compileall -q src/autoflow
# exit 0
uv run alembic -c src/autoflow/infrastructure/database/alembic.ini heads
# am01_management_operations (head)

npm exec --offline --yes --package=node@22.23.2 -c 'vitest run src/renderer/domains/android/tests && npm run typecheck && npm run lint && npm run build'
# 14 files / 104 passed; typecheck/lint/build exit 0; renderer built in 37.70s
# 保留既有 zod PURE annotation 与 workflow import 构建提示。

npm exec --offline --yes --package=node@22.23.2 -c 'npm run openapi:generate'
# exit 0，generated.ts 增加目录查询契约
npm exec --offline --yes --package=node@22.23.2 -c 'node --version && npm run openapi:check && npm run test:structure'
# v22.23.2；OpenAPI check exit 0；structure 4 passed

git diff --check -- apps/backend apps/desktop
# exit 0
```

本轮未重跑全后端、全 Ruff、全前端及全脚本；已有全量失败仍未解决，不用聚焦或构建通过代替这些门槛。

## 真实 macOS/Lima/ReDroid 与 HTTP

命令：`uv run --project apps/backend python /tmp/autoflow-cleanup-smoke-20260923-final.py > /tmp/android-cleanup-real-final.log 2>&1`，exit 0。[脚本](2026-09-23-cleanup-smoke.txt)与[原始结果](2026-09-23-cleanup-result.json)。固定独立 workspace，拒绝复用已存在路径；只处理本次创建且标签匹配的实例/卷。

- 源实例 `30490d8a-197f-48f2-a85c-252b51173c63`；新目标 `ea99d205-af43-473a-b709-05e5592aff3e`。
- 镜像 `sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b`；实际备份包含 manifest 为 `17,545,388` bytes。
- 真实数据卷备份后，HTTP 目录返回 backup、backup-staging、backup-orphan 三类。两份临时文件由本次实验显式创建，用来复现未发布/未登记产物，**不是伪称做了进程崩溃**。
- 暂存数据在预览后由 `old-content` 改为同字节数的 `new-content`；清理 HTTP 返回 409，文件保留。
- 重新预览并确认两份临时产物后，HTTP 返回 `state=succeeded`；仅两项被删除，已登记源备份保留。
- 真实恢复方法执行期间插入 HTTP 清理请求，返回 `ANDROID_BACKUP_BUSY`；随后继续真实 Docker 恢复，无 mock 数据卷。
- 新目标启动后 ADB 经相对/绝对符号链接及硬链接读回三个 `metadata-proof`；源测试条目的属性和数据不变。
- 两个实例容器和卷清理数均为 0、deleted=true；测试备份删除。确认无运行中容器后 Lima 停回 Stopped。
- 最终新增的 retained 状态筛选有五项自动回归；本次真实 HTTP 清理范围是备份/暂存/未登记产物，未把它当作五种设备状态的真实验证。前端证据为 Vitest，未宣称已做真实 Electron 点击验收。

## 剩余工作

- 仍需把 APK 安装的宿主/设备遗留临时文件纳入受控清理；当前目录查询覆盖备份相关临时产物。
- 硬中断后的备份/恢复操作核实、恢复部分写入目标的持续隔离、xattrs 能力尚未闭环。
- 特殊/不可读目录目前拒绝整个预览而不删除；未知来源提示不会推断业务成功。
- 文件全量摘要为显式操作，超大备份可能使预览变慢；尚无规模性能证据。
- 高级脱敏日志、应用会话重建核实、1/5/10 性能、全量失败门槛和最终全分支审查仍待完成。GApps 镜像/账号/网络为外部 blocked，以上软件缺口仍是未完成。

本增量结论置信度高，完整交付状态仍 partial。
