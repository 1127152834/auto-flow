# AM3 多实例效率验收

[2026-09-24 真实部分失败、重试与取消](2026-09-24-bulk-failure-cancel.md)补齐两台批次 `[succeeded, failed]`、容量等待 `cancelPending` 与资源清理，并修复新设备 `generation=0` 在公开修订号 1 下被批次误判冲突。十台规模因本机 Lima 7921 MiB 小于最低需求 8192 MiB 标记 `blocked`，见[容量记录](2026-09-24-advanced-logs-and-capacity.md)。

历史审计基线：`3ee61947`；下表已按 2026-09-23 自建 Mac 实例和当前隔离分支重新校准。旧聚焦后端 `235 passed, 2 warnings`、前端 Android `13 files, 81 passed` 仅为该基线快照；当前完整后端/前端门槛见 [AM1 新证据](2026-09-23-am1-real-control-retention.md)。

| 任务 | 状态 | 证据与限制 |
| --- | --- | --- |
| T13 批次与容量 | `passed` | 持久容量、双工作区未知预算及真实双实例 start/stop/delete 通过；[真实部分失败、修订冲突项重试和容量取消](2026-09-24-bulk-failure-cancel.md)通过。[真实容器消失失败与回执前强杀](2026-09-24-bulk-runtime-fault.md)补足恢复后重试、未知项禁止重放及重启核实，两个探针保留、资源清理通过。 |
| T14 观察与预览 | `partial` | 3秒/15秒周期、退避、陈旧与无同步 inspect 自动化通过；真实五台快照、双并发 PNG 已验。后台探测计数、隐藏页同链和桌面前台交互指标未完整实测。 |
| T15 应用管理 | `partial` | APK 校验、保护包、控制/确认及未知结果自动化通过；真实安装/版本/启动/停止/清数据/卸载和[跨重建回执核实](2026-09-24-final-branch-review.md)已验。桌面破坏性确认同链与真实 ADB 断连未验。 |
| T16 隔离与性能 | `partial`；十台 `blocked` | 双实例删除隔离、1/5台 API、五台内存和双预览已验；十台最低8192MiB大于Lima7921MiB。探测次数、隐藏页和前台延迟仍未完整记录。 |

## 自动验证命令摘要

```text
cd apps/backend && uv run pytest tests/unit/test_android_bulk.py tests/unit/test_android_capacity_rules.py tests/unit/test_android_observations.py -q
通过（包含在 Android 聚焦集合 235 passed 中）

cd apps/desktop && npm exec vitest run src/renderer/domains/android/tests
13 files, 81 passed（含旧设备列表轮询和 stale/unknown 打开保护回归）
```

上述命令是旧基线的历史输出；当前真实破坏性应用操作另有独立证据，批量性能未用 mock 结果替代。

9 月 23 日增量与软件缺口：[最新记录](2026-09-23-validation.md)。本表的整任务 blocked 不表示缺失实现可由外部条件解释。

T14/T15 的前端响应栅栏、核验失败解锁和预览取消已补齐自动化。Node 运行时偏差与重跑结果见 [前端增量记录](2026-09-23-frontend-validation.md)；阶段真实性能验收未完成。

T15 命令完成语义与人工丢响应读回见 [命令验证](2026-09-23-command-verification.md)；随后真实 HTTP APK 安装/启动/停止/清数据/卸载及完成标记清理分别见 [AM1 实测](2026-09-23-am1-real-control-retention.md)与 [标记增量](2026-09-23-command-marker-verification.md)。保持启动超时 unknown；不把单实例通过冒充批量验收。

T13 最新：[持久容量预留与真实验证](2026-09-23-capacity-verification.md)。前述“尚缺容量integration/持久预留实现”已superseded；此历史描述已 superseded：1/5台局部指标已补，十台容量 blocked，完整前台/探测指标未验。

T13 新增：[真实双实例批量链及响应 DTO 修复](2026-09-23-am3-real-bulk-verification.md)。最初真实接口 `500` 由内部 `workspaceIdentity` 泄入严格 DTO 引起，RED→GREEN 修复后 start/stop/delete 三个批次各自两项均成功；本证据不替代 5/10 台或真实部分失败演练。

T13/T14/T16 后续[五实例真实链](2026-09-23-final-review-remediation.md)已覆盖五台同时 `ready`、20 次管理列表 `median=2.13ms/p95=2.74ms`、两台并发 PNG 预览、五台 Docker 内存读数及逐项清理后无残留容器/卷。下文单实例数字保留为历史快照；10 台容量 blocked；真实部分失败、修订冲突项重试与取消已由 2026-09-24 记录补足。

单实例聚合延迟测量：在隔离工作区启动真实认证 HTTP sidecar，顺序请求 `GET /api/v1/android/management/devices?limit=50` 共 20 次；所有响应为 200 且包含本轮自建 `ready` 实例，脚本输出 `status=passed`。计时使用同机 `time.perf_counter()`，结果为 `min=1.63ms`、`median=1.91ms`、`p95=2.70ms`、`max=4.70ms`。这是单个运行实例下的局部 API 延迟，不包含前端渲染、预览帧或并发 5/10 台的成本。
