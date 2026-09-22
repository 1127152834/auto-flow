# AM1 基础管理验收

审计基线：`edf3906b`；来源：[总体验收记录](2026-09-22-validation.md)。计划 T01–T07 的 35 个 checkbox 已附状态；状态以自动化证据和真实条件逐项判定。

| 任务 | 状态 | 证据与限制 |
| --- | --- | --- |
| T01 夹具与基线 | `passed` | `tests/fixtures/android_management.py`、前端 `tests/management-fixtures.ts`；UUID/未知设备 404 测试通过；主工作区 Studio 改动未复制。 |
| T02 状态与动作策略 | `passed` | `management_models.py`、`management_rules.py`；unknown/stale、retained、delete 状态测试；前端 `ManagementState.test.ts`。 |
| T03 环境诊断 | `passed` | `test_android_management_environment.py`、`test_android_runtime.py`；逐项 platform/ADB/Lima/SSH/scrcpy/VM/Docker/binder/images/capacity/disk 检查；真实 `environment()` 返回 `available: true`。 |
| T04 持久操作与迁移 | `passed` | `test_android_management_operations.py` 与契约测试覆盖幂等、摘要冲突、状态栅栏、needs_verification、compact；新增 `transition_with_device` 以同一 SQLAlchemy 事务提交操作状态和设备投影；迁移 head 为 `am01_management_operations`，父节点为当前 `0019_recording_commands`。旧 1000 条回执上限已移除，聚焦集合 `126 passed, 1 warning`。 |
| T05 控制会话 | `blocked` | ConsoleController、heartbeat 和 generation 身份测试存在；原生 scrcpy 窗口、切换写端、30 秒失联、重启后会话和中断恢复没有完整真实证据。 |
| T06 管理首页 | `not_run` | AndroidPage/ManagementOverview 有局部测试并证明不请求 workflows/allocations/runs；计划指定的 `DeviceManagementPage.test.tsx`、长名称/缩放/键盘/断线/保留数据完整流程无证据。 |
| T07 AM1 真实链 | `blocked` | smoke 参数保护 `2 passed`；真实实例 create/connect/app_info/screenshot/stop→connect 通过；测试 APK、中文输入、AutoFlow 重启、中断恢复和原生窗口未执行。 |

## 已执行命令摘要

```text
cd apps/backend && uv run pytest tests/unit/test_android_management_smoke_args.py -q
2 passed

cd apps/backend && uv run pytest tests/contract/test_android*.py tests/unit/test_android*.py tests/integration/test_android*.py -q
126 passed, 1 warning
```

真实 Lima/ReDroid 细节、镜像 digest、设备和截图数据见总记录；未提供测试 APK 或人工窗口结果，不标记为通过。
