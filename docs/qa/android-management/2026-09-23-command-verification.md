# Android 应用命令完成语义核验（2026-09-23）

- 状态：partial；完整目标 active。本增量基线 `6098b571`，代码与本页同提交。
- 根因：ADB 响应丢失后，旧运行时仅凭 shell 退出码核实成功；`am`/`pm` 文本失败但退出码 0 会被误判。
- 改动：原命令 shell 内先验证启动的 Status、包操作的 Success 或 force-stop 的空输出，再写 `v2:<rc>`；不持久化原始应用输出。旧非零标记仍可证明失败；旧 `0` 标记保持 unknown，不自动重放。启动文本 `Status: timeout` 或无法识别输出使用 `v2:124` 保持 unknown；不能将等待超时等同确定失败。
- 保留原 marker 路径/归属校验、requestId 绑定、generation、回执先持久化后清理，以及未知状态下写入隔离。设备恢复可接受旧/新完成格式，但完成不等于应用成功。
- 没有公共 DTO 或 DB 结构变化；唯一迁移 head 仍是 `am01_management_operations`。

## RED → GREEN

1. 真实本机 sh 执行生产命令脚本，只替换 Android IO 和 marker 路径；5 条语义失败均被旧脚本写成 0，首次 `5 failed / 5 passed`。
2. 新格式读回与旧零退出码保护先 `2 failed`；改实现后运行时 `34 passed`。
3. APK 安装路径补测先 `2 failed / 2 passed`；同一完成脚本用于安装后 `36 passed`。
4. Android 完整聚焦首次 `2 failed / 264 passed`，原因是两个回执持久顺序测试仍提供旧零标记。将成功 fixture 更新为 `v2:0`，保留旧零标记拒绝测试后，**266 passed / 2 warnings，30.68s**。

5. 真实设备返回 `Status: timeout` 后，新增“必须保持 unknown”的断言先失败，再将完成码 124 定义为未核实。运行时/控制台/应用契约复跑 **56 passed / 1 warning，2.43s**。

6. 同类无法识别输出（启动/停止/卸载/清数据/安装）先 **5 failed**，修复为保留unknown，且不覆盖原非零退出码；最终聚焦 **271 passed / 2 warnings，9.74s**。

上述本机 shell 测试不是 macOS/ReDroid 真实验收。

## 自动验证

cwd：`apps/backend`。

| 命令 | 实际结果 |
| --- | --- |
| `uv run pytest tests/contract/test_android*.py tests/unit/test_android*.py tests/integration/test_android*.py tests/integration/test_migration_heads.py -q` | 最终代码 271 passed，2 warnings，9.74s |
| `uv run ruff check src/autoflow/providers/android/mac_runtime.py tests/unit/test_android_runtime.py tests/unit/test_android_console_lifecycle.py` | All checks passed |
| `uv run python -m compileall -q src/autoflow` | exit 0 |
| `uv run alembic -c src/autoflow/infrastructure/database/alembic.ini heads` | am01_management_operations (head) |
| `uv run ruff check src tests` | failed：118 errors，111 fixable；未绕过全量门槛 |

OpenAPI generate/check、指定 Node22 前端与构建输出见 [前端记录](2026-09-23-frontend-validation.md)。完整 `uv run pytest -x -q` 再次失败：**278 passed / 1 failed / 1 warning，477.56s**；停在 `tests/contract/test_proxy_runtime.py:67`，全 OpenAPI 的 password 禁令与已有 `local_workflows.WebDavConfig.password` 冲突。该次全量开始于最后的启动超时细分修复之前，最终 Android 聚焦271项已重跑通过；不能声称最终分支全量通过。

## 真实运行时

- 首轮新建 workspace `/tmp/autoflow-android-semantic-smoke-20260923`；device `eeee7269-c128-4c8a-af76-8e9690ecca0e`，workspace hash `97a0cfccbafbc021ecee3fdb1ba3e6ee9c8bbe9a72de934c091b71b1129e5bd7`。
- 固定镜像 ID：`sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b`。
- 首轮在启动设置应用时得到 `ANDROID_COMMAND_FAILED`，未进入人工丢响应；不计 passed。finally 经运行时归属检查删除本轮实例和卷，容器/卷均 0。
- 第二轮 workspace 后缀 `-b`；device `7d2918f3-e8ae-4014-be8a-7841c0e85a55`，hash `0ecfafe9cb6c280afa0ae3c4d2d17bd224544ba312467be035c9d6227d7e6ef4`。实际输出 `Status: timeout`、`WaitTime: 10311`，marker 读回 1。该实测暴露出将等待超时分类为失败仍不正确；先保留失败，再按上面的 RED→GREEN 改为 unknown。容器/卷均清理为 0。

- 第三轮 workspace 后缀 `-c`；device `c65eaef0-e59b-483e-bfd4-55c2d156aa75`，hash `fd17ff2c2a6a25b6a942f981e3cb18f5a58f531f76646f60d22aad8ec7e2e846`。实际启动 `Status: ok / LaunchState: WARM / WaitTime: 3791`；人为丢弃真实 ADB 响应后，启动与停止 marker 均核实为 0，前台包分别是 `com.android.settings` 和 `com.android.launcher3`。两次没有重发动作；之后容器/卷均为 0。
- 第三轮 exit 0；[实际结果](2026-09-23-app-command-result.json)和[当次脚本文本](2026-09-23-app-command-smoke.txt)随本页保存。文本是本次实验的原样记录，不是通用 smoke CLI；固定 workspace 防止重用。只有成功路径形成实测证据，未知结果恢复分支并未在第三轮进入。
- 实际命令（cwd `apps/backend`）：`uv run python /tmp/autoflow-android-semantic-smoke-20260923-c.py > /tmp/android-semantic-real-20260923-c.log 2>&1`。前两轮对应无后缀与 `-b` 文件，exit 1；日志同样保留在 `/tmp/android-semantic-real-20260923{,-b}.log`。
- 运行前 Lima 为 Stopped，显式启动既有 `autoflow-redroid`；结束后 `docker ps -q` 无输出，再恢复为 Stopped。未移除既有停止容器或外部卷。
- 边界：本轮验证实际 Mac/Lima/ReDroid/provider 的命令与 marker，故障由脚本在本地丢弃已完成响应注入；不是自然网络故障，也不是 HTTP 会话刷新/重启验收。启动超时保持 unknown 的最终保护由自动化覆盖，第三轮真实启动未超时。第三轮之后仅收紧无法识别输出分类，该最后增量已重跑本机shell/聚焦验证，未再运行真实实例；APK 安装、卸载和清数据的真实链路仍 not_run。

## 仍需推进

AM3 持久容量预留、跨重启应用结果找回及规模指标；AM4 属性/安全内部链接、恢复异常、临时文件与高级日志；全量工程门槛、逐项台账和最终全分支审查仍未完成。
