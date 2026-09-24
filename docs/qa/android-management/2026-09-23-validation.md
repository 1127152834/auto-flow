# 安卓管理增量验收（2026-09-23）

- 状态：`partial`；完整开发与验收目标仍 `active`，不是代码交付完成。
- 来源：隔离 worktree `codex/android-management-complete`，本轮父提交 `3ee61947`，本文件随本轮实现和测试一起提交。历史文档中 amend 前的 `c60148fb` 引用已纠正。
- 保护范围：worktree 中既有 Studio `component-tools.json`、`contract-matrix.md`、`service-inventory.json` 保留，不纳入本轮提交。
- 迁移：唯一 head `am01_management_operations`；本轮未改表结构或旧迁移字节。

## 已完成的增量修复

| 任务 | RED 证据 | GREEN 行为 |
| --- | --- | --- |
| T15 应用操作核验 | 第一轮 `4 failed, 31 passed`：缺标记误判成功、核验提前消费标记、安装后查询失败误分类、新请求越过未知回执 | 缺证据保持 unknown；未知回执阻止新写入；安装命令完成与包版本观察分开记录 |
| T15 持久回执 | 第二轮 `3 failed, 12 passed`，随后补充安装清单不能证明超时命令结束、失败回执写盘失败两条 RED | 完成标记绑定原请求；先持久化终态，再清理标记；落盘失败不丢证据，可重复核验但不重放副作用 |
| T13 容量准入 | `4 failed, 11 passed`：Memory=0、inspect 空/错配清单、ps 失败 | 未限额不算零占用；枚举和 inspect 必须完整一致；未知容量拒绝准入 |
| T19 默认诊断 | 契约先失败于设备变成 `unowned`；修复归属后失败于导出含 `private-token` | 使用 runtime workspace hash，排除外部及无归属设备；默认只导出审核过的状态/时间/错误码字段，排除名字、配置快照、原始错误消息、legacy 及任意新增元数据 |

以上是实际生产路径回归。ADB/Docker 的自动测试以 IO 替身隔离；不能据此声称真实丢响应或磁盘故障验收已通过。

## 本轮命令与实际输出

从仓库根运行，后端命令先 `cd apps/backend`。

| 命令 | 实际结果 |
| --- | --- |
| `uv run pytest tests/contract/test_android*.py tests/unit/test_android*.py tests/integration/test_android*.py tests/integration/test_migration_heads.py -q` | `253 passed, 2 warnings in 10.18s`；其中包含 migration heads 测试，不直接与旧 235 项集合比较 |
| `uv run ruff check src/autoflow/application/android src/autoflow/providers/android src/autoflow/adapters/http/android*.py tests/unit/test_android*.py tests/contract/test_android*.py tests/integration/test_android*.py` | `All checks passed!`，exit 0 |
| `uv run python -m compileall -q src tests` | 无错误输出，exit 0 |
| `uv run alembic -c src/autoflow/infrastructure/database/alembic.ini heads` | `am01_management_operations (head)`，唯一 head |
| `npm run openapi:check` | exit 0，无生成类型漂移；本轮无公开 DTO 形状变化 |
| `uv run ruff check src tests` | exit 1：`Found 118 errors`，其中 111 项可自动修复；完整 Ruff 门槛失败，未用局部通过替代 |
| `uv run pytest -x -q` | `1 failed, 278 passed, 1 warning in 318.71s`；停在 `tests/contract/test_proxy_runtime.py::test_runtime_mounts_proxies_but_never_publishes_host_contract` 第 67 行，全 OpenAPI 的 password 属性断言与既有 WebDavConfig 冲突；未删除或跳过该断言 |

完整 Ruff 的 118 项分布：I001 92、RUF100 17、S110 4、DTZ005 2、UP035 1、UP037 1、RUF007 1。行为相关项位于既有 workflow executors 与 integrations gateway；本轮未自动改写这些实现或删除测试。

两项 warning 为 anyio `BlockingPortal` 废弃提示，以及故意构造重复 APK Manifest 的 ZIP fixture 警告。

命令纠正记录：第一次直接 `uv run alembic heads` 缺 `script_location`，exit 255；改用仓库实际配置后通过。一次从仓库根展开后端 glob 被 zsh 拒绝，未执行测试；已在后端 cwd 重新运行实际集合。没有把环境或命令错误当成功能 RED。

## 真实 macOS/Lima/ReDroid

实际命令：

```sh
cd apps/backend
uv run python scripts/android-management-smoke.py \
  --workspace /tmp/autoflow-android-smoke-20260923-verification \
  --allow-device-mutation \
  --scrcpy-archive /Users/zhangtiancheng/.autoflow/android-runtime/scrcpy-macos-aarch64-v3.3.4.tar.gz
```

首次 exit 3，Lima 报告 VM stopped。执行 `limactl start autoflow-redroid` 成功后重跑，exit 0：

```json
{
  "status": "passed",
  "deviceId": "e5846e69-03fc-4a62-a0ed-9de70c0db785",
  "workspaceId": "6760757a7508f300cd370ab203834df2946f4e96ddc40316c23dac969ff947bc",
  "applicationCount": 102,
  "resumedApplicationCount": 102,
  "screenshotBytes": 652550,
  "stages": ["停止 Android，保留数据", "启动 Android", "移除实例运行环境", "清理独立数据"],
  "cleanup": {"deleted": true, "dataRetained": false}
}
```

随后 `docker ps -a --filter label=io.autoflow.android.workspace=<上述 hash>` 和 `docker volume ls` 同标签过滤均无输出；全 VM 的 `docker ps -q` 也无输出。恢复本轮前状态，`limactl stop autoflow-redroid` 成功，`limactl list` 显示 Stopped。

该 smoke 只证明本轮真实单实例生命周期、读取应用、截图和标签范围清理。它不覆盖真实应用安装/卸载/清数据、原生窗口、丢响应、备份中断或容量竞态。

## 仍需继续的软件工作和验收

这些工作可继续推进，不应伪装成外部条件 `blocked`：

1. T13 实际持久容量预留尚未接入。现有全局生命周期锁及纯规则不等于“命令超时后仍在启动”的跨工作区预留证据。
2. T14 预览等待队列的取消清理、隐藏后在途请求取消和首次离屏请求仍需回归与修复。
3. T15 核验确认失败后，前端仍可能保留 unknown 写入锁；Android 命令的退出码与启动输出语义还需一致性验证。重启后的应用回执核验与真实丢响应未闭环。
4. T17/T18 安全内部链接、UID/GID/mode、恢复中断、staging 原子发布及磁盘/权限失败的完整软件与真实证据仍需审计。
5. T19 默认白名单已修复；应用版本字段、高级日志的单次同意/时间/体积限制、临时文件清理仍未完成。
6. 完整后端测试、全量 Ruff、历史全前端 20 个失败及 3 个脚本失败尚未全部解决；最终全分支审查及修复后的完整验证未完成。
7. 实施计划旧 checkbox 与当前实现仍需逐项校准，不使用旧的 `25/70/5` 分布表示当前完成率。

外部条件或未运行项单独记录：GApps 候选镜像/专用账号/商店链路仍缺验收条件（沿用历史 blocked，未制造账号或登录结果）；测试 APK、中文输入、原生 scrcpy、AutoFlow 重启与受控中断、1/5/10 台性能指标均尚无本轮完整真实证据。硬件可满足的部分应继续实测，不能一律写成硬件阻塞。

前端本轮未改动。9 月 22 日历史证据为 Android `13 files / 81 tests passed`、typecheck/lint/OpenAPI/build 通过；完整前端 `417 files passed / 6 failed`、`4663 tests passed / 20 failed`。这些历史结果不冒充本轮新跑结果。
