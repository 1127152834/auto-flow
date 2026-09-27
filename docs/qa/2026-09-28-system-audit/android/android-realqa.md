# Android 真实设备生命周期 QA

日期：2026-09-28；状态：confirmed，真实启动失败；置信：高。HEAD：`33ae3aa49600840b1700c83723408c494dc201a8`。未修改业务代码、未修复共享 VM/Docker 配置；审计产物由主任务统一提交。

## 结论

实际执行了两次独立 QA 设备的创建、幂等重试、启动、失败恢复、设备和数据卷删除。两次均成功创建，但真实启动失败：Lima VM 中 Docker 元数据仍声明默认 bridge 使用 `docker0`，实际 Linux 网络接口 `docker0` 不存在。设备没有进入运行态，截图和“停止运行中的设备”被此故障阻塞，不能记为通过。

两个 QA 容器及其数据卷已完全删除，两个专属 sidecar 已关闭。前后 6 个既有容器的 ID、状态、StartedAt、镜像、资源配置/标签及已有卷集合一致，没有启动、停止、删除或更改既有设备。

## 执行方式及边界

1. 使用生产 `MacAndroidRuntime.environment()` 和真实 Docker 只读盘点。运行环境报告 available=true、6 核、7921 MiB、1 个已缓存公开 Android 13 ARM64 固定镜像；6 个已有容器全部 exited，活动内存预留为 0，新增 1 核/1536 MiB 符合现有容量规则。
2. 启动随机端口生产 `python -m autoflow`，每次使用全新 SQLite 工作区。新设备 UUID 唯一，独立数据卷名称和 `io.autoflow.android.workspace/device` 标签可核对。未使用 fake runtime、注入镜像、ASGITransport 或 mock 数据。
3. 用真实 HTTP `POST /api/v1/android/devices` 创建 start=false 设备，再原 UUID/原配置重发一次，确认只有一个设备。随后以真实操作接口请求 start。
4. 第二次重现时，在清理前只读捕获本次 QA 容器 `.State` 和日志，定位失败原因；随后真实 HTTP recover → delete（deleteData=true），并核对容器、数据卷和 API 设备列表均已清理。
5. 没有拉镜像、重启共享 VM/Docker、补网络接口、修改系统权限、打开原生窗口、登录账号或调用已退役 Android workflow。旧 `scripts/smoke-android-management.py` 包含暂停参考容器/退役工作流的范围，本轮没有运行。

脚本入口：`apps/backend/.venv/bin/python docs/qa/2026-09-28-system-audit/android/android_real_qa.py`。整体退出码两次均为 1，准确表示启动验收失败，不能因为清理检查通过而把整体标为通过。

## 实测结果

| 项目 | 结果 | 证据 |
|---|---|---|
| 运行环境 HTTP 探测 | PASS：实际返回 available=true | 两次 results.environment |
| 容量预检 | PASS：新增 1536 MiB 在预算内 | preflight.json、results.checks |
| 创建停止态设备和独立数据卷 | PASS，两次均成功且标签匹配 | created、cleanup.beforeDeletion |
| 同 UUID/配置创建重试 | PASS，设备总数仍为 1 | HTTP 记录 |
| 启动 | FAIL，两次约 0.8–0.9 秒失败进入 recovery_required | operation.state=failed；第二次 failureDiagnostics |
| PNG 截图 | NOT_RUN：设备未启动 | 没有制造或使用模拟截图 |
| 停止运行中设备 | NOT_RUN：设备从未进入 running/ready | 未把删除 created 容器算成正常停止验证 |
| 失败后的 recover | PASS | HTTP 操作成功；第二次 operations 中保存结果 |
| 删除本次设备及数据 | PASS，两次容器数=0、volumeExists=false | cleanup.afterDeletion |
| 原有资源保持不变 | PASS | before/after 容器记录和 volume 集合一致 |

第一次运行：2026-09-28 01:20:09–01:20:20 +08:00，设备 `bb73b0cd-8c44-4b18-a49f-9e52ecfb6124`。

第二次诊断重现：2026-09-28 01:20:58–01:21:10 +08:00，设备 `5ce6d47e-2841-4aff-9566-88e2956967bc`。单次包含 8 项环境/创建/清理检查通过，但独立的 start 场景失败；不能合并成“8/8 全通过”。

## 根因与设计不足

第二次本次 QA 容器的 `.State`：

```text
Status=created
Running=false
Pid=0
ExitCode=128
Error=failed to set up container networking: failed to create endpoint ...
      on network bridge: adding interface veth... to bridge docker0 failed:
      Device does not exist
```

只读复核 `ip -j link show docker0` 退出 1，stderr 为 `Device "docker0" does not exist.`。与此同时 `docker network inspect bridge` 仍返回 `com.docker.network.bridge.name=docker0`。这是当前 VM 网络环境的实际故障，证据不支持把 Docker 接口丢失归因于 AutoFlow 业务代码。

可确认的应用诊断不足：

- `apps/backend/src/autoflow/providers/android/mac_runtime.py:89–100` 的环境检查只验证 Docker info、Linux/ARM64、binder、工具与 scrcpy，未验证当前启动依赖的网络接口。因此“运行环境可用”可以与“任何新设备均无法启动”同时出现。建议报告依赖项健康状态，至少区分基础工具可用与设备可启动；修复前不能把 available=true 当成真实设备通过。
- `mac_runtime.py:43–45` 丢弃命令 stderr，统一返回 `ANDROID_COMMAND_FAILED`；`application/android/management.py:105–106` 持久化后仍只有通用中文错误。用户无法从实际 API 错误判断是桥接网络缺失、资源不足还是镜像故障。应保存经过筛选的可操作诊断/分类，而非向 UI 暴露任意原始命令输出。
- 当前管理层正确持久化 failed/recovery_required，要求 recover 后才准入后续操作；本次恢复和仅删除自有设备成功，没有观测到资源误删或错误宣告启动成功。

未修复此环境：修复共享 VM 网络或重启 Docker 会越过本次“仅真实测试、保护已有环境”的边界。后续需完成环境修复，再重跑启动→截图→正常停止链，不能以本次成功清理替代缺失验收。

## 证据

- [只读资源预检](preflight.json)
- [第一次实际执行](run-2d0t650u/results.json) / [HTTP](run-2d0t650u/http.jsonl)
- [第二次诊断重现与清理](run-8d7ylddm/results.json) / [HTTP](run-8d7ylddm/http.jsonl)
- [VM 网络只读复核](network-readonly.json)
- [可运行测试脚本](android_real_qa.py) / [诊断运行输出](diagnostic-runner.log)

未覆盖：Android 工作流接入、原生 scrcpy 窗口、ADB 自动交互、应用安装/账号/Google 组件、设备成功启动后的截图与暂停恢复、长时间稳定性、跨平台。生产 Android 工作流仍由 `CurrentAndroidRunBoundary.start` 显式返回 unavailable，本轮没有借旧测试绕过。
