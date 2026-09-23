# AM1 基础管理验收

审计基线：`3ee61947`；来源：[总体验收记录](2026-09-22-validation.md)。计划 T01–T07 的 35 个 checkbox 已附状态；状态以自动化证据和真实条件逐项判定。

| 任务 | 状态 | 证据与限制 |
| --- | --- | --- |
| T01 夹具与基线 | `passed` | `tests/fixtures/android_management.py`、前端 `tests/management-fixtures.ts`；UUID/未知设备 404 测试通过；主工作区 Studio 改动未复制。 |
| T02 状态与动作策略 | `passed` | `management_models.py`、`management_rules.py`；unknown/stale、retained、delete 状态测试；前端 `ManagementState.test.ts`。 |
| T03 环境诊断 | `passed` | `test_android_management_environment.py`、`test_android_runtime.py`；逐项 platform/ADB/Lima/SSH/scrcpy/VM/Docker/binder/images/capacity/disk 检查；真实 `environment()` 返回 `available: true`。 |
| T04 持久操作与迁移 | `passed` | `test_android_management_operations.py` 与契约测试覆盖幂等、摘要冲突、状态栅栏、needs_verification、compact；新增 `transition_with_device` 以同一 SQLAlchemy 事务提交操作状态和设备投影；迁移 head 为 `am01_management_operations`，父节点为当前 `0019_recording_commands`。旧 1000 条回执上限已移除，Android 聚焦集合 `235 passed, 2 warnings`。 |
| T05 控制会话 | `partial` | ConsoleController、heartbeat 和 generation 身份测试存在；[原生 scrcpy 手动/只读窗口进程](2026-09-23-persistent-metadata-verification.md)已真实验证且关闭不停止实例。[本轮页面竞态](2026-09-23-control-session-verification.md)补齐迟到响应、旧输入、路由守卫、原生归属及回收核实的 RED→GREEN；人工输入/切换写端、30 秒失联、完整重启和中断恢复没有真实端到端证据。 |
| T06 管理首页 | `partial` | AndroidPage/ManagementOverview 使用 management devices 快照，不再轮询旧 `/api/v1/android/devices` 或详情 `/runs`；[控制会话测试](2026-09-23-control-session-verification.md)确认退役入口移除及原生归属/显式结束可见。[操作历史增量](2026-09-23-operation-history-verification.md)提供正确设备过滤、分页、原请求核实、键盘焦点及模拟断线只读；长名称/200% 缩放/真实断线/保留数据完整流程仍缺证据。 |
| T07 AM1 真实链 | `not_run`（整任务） | smoke 参数保护 `3 passed`；guarded smoke 真实完成停止、启动、移除运行环境和清理独立数据，应用清单 `102/102`、截图 `553476` bytes；测试 APK、中文输入、AutoFlow 重启、中断恢复仍未执行，原生窗口进程另有真实证据。 |

## 已执行命令摘要

```text
cd apps/backend && uv run pytest tests/unit/test_android_management_smoke_args.py -q
3 passed

cd apps/backend && uv run pytest tests/contract/test_android*.py tests/unit/test_android*.py tests/integration/test_android*.py -q
235 passed, 2 warnings
```

真实 Lima/ReDroid 细节、镜像 digest、设备和截图数据见总记录；未提供测试 APK 或人工窗口结果，不标记为通过。
