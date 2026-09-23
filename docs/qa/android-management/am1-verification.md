# AM1 基础管理验收

当前审计：2026-09-24，`30eb0926` 加本轮增量；[任务逐项追踪](2026-09-24-task-evidence-audit.md)。以下早期自动化数值保留为历史证据。原审计基线：`3ee61947`；来源：[总体验收记录](2026-09-22-validation.md)。计划 T01–T07 的 35 个 checkbox 已附状态；状态以自动化证据和真实条件逐项判定。

| 任务 | 状态 | 证据与限制 |
| --- | --- | --- |
| T01 夹具与基线 | `passed` | `tests/fixtures/android_management.py`、前端 `tests/management-fixtures.ts`；UUID/未知设备 404 测试通过；主工作区 Studio 改动未复制。 |
| T02 状态与动作策略 | `passed` | `management_models.py`、`management_rules.py`；unknown/stale、retained、delete 状态测试；前端 `ManagementState.test.ts`。 |
| T03 环境诊断 | `passed` | `test_android_management_environment.py`、`test_android_runtime.py`；逐项 platform/ADB/Lima/SSH/scrcpy/VM/Docker/binder/images/capacity/disk 检查；真实 `environment()` 返回 `available: true`。 |
| T04 持久操作与迁移 | `passed` | `test_android_management_operations.py` 与契约测试覆盖幂等、摘要冲突、状态栅栏、needs_verification、compact；新增 `transition_with_device` 以同一 SQLAlchemy 事务提交操作状态和设备投影；迁移 head 为 `am01_management_operations`，父节点为当前 `0019_recording_commands`。旧 1000 条回执上限已移除，Android 聚焦集合 `235 passed, 2 warnings`。 |
| T05 控制会话 | `passed` | ConsoleController、heartbeat 和 generation 身份测试存在；[原生窗口与真实会话链](2026-09-23-am1-real-control-retention.md)已验证中文输入、切原生/切回、结束后重进、30 秒租约回收及完整 HTTP 进程重启后的旧会话 410/新会话可用。[页面竞态](2026-09-23-control-session-verification.md)经 RED→GREEN；[最终真实桌面链](2026-09-24-desktop-control.md)补原生离页保留、返回切回、受控SSH/ADB断线锁定、结束清理与重连；两个自建实例均清理。 |
| T06 管理首页 | `partial` | AndroidPage/ManagementOverview 使用管理快照，不再轮询旧 `/api/v1/android/devices` 或详情 `/runs`；[操作历史](2026-09-23-operation-history-verification.md)覆盖设备过滤、分页、原请求核实、键盘焦点和模拟断线。本轮补公开 `restore`、保留实例按钮与普通 `start` 服务端拒绝；[同卷真实读回](2026-09-23-am1-real-control-retention.md)通过。长名称和约 207.36% 原生缩放已有桌面实测；精确 200%、指定窗口尺寸与真实断线旧快照仍缺证据。 |
| T07 AM1 真实链 | `partial` | [本轮真实链](2026-09-23-am1-real-control-retention.md)已执行自建实例创建、测试 APK 安装与应用动作、中文输入与截图、返回重进、切原生/切回、停机启动、HTTP 重启、保留卷恢复，以及双实例中永久删除一台后另一台不变；较早 guarded smoke 已按标签清理另一自建实例。各轮自建实例均有最终清理证据；桌面控制与SSH断线已由[9月24日记录](2026-09-24-desktop-control.md)补齐，[安装命令执行中断](2026-09-24-app-interruption.md)已补ADB断线及HTTP进程树SIGKILL、重启安全核实与原应用数据保留；T07.3通过，T07.2历史RED输出未找到。 |

## 已执行命令摘要

```text
cd apps/backend && uv run pytest tests/unit/test_android_management_smoke_args.py -q
3 passed

cd apps/backend && uv run pytest tests/contract/test_android*.py tests/unit/test_android*.py tests/integration/test_android*.py -q
235 passed, 2 warnings
```

上表是 `3ee61947` 时点的历史自动化输出，不代表当前 HEAD 的完整门槛。最新真实 Lima/ReDroid、测试 APK、原生窗口和保留卷读回见[本轮记录](2026-09-23-am1-real-control-retention.md)；当前切片完整回归以该记录的最终门槛为准。
