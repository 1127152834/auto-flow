# M1 止血实施记录与交接

日期：2026-10-01。分支：`remediation/m1-stop-silent-failures`（基于基线 639aabc，后续已与基线合并，见 Git 历史）。状态：**代码完成并通过独立评审后的整改；M1 尚未验收完成**，缺 Mac/CI 同环境证据。

## 已做（每项有测试）
- Task 1 SQLite WAL/NORMAL/busy_timeout，代理管理共用主引擎，复制主库前必须 checkpoint。
- Task 2/3 批量运行失败日志带真实原因；v2 出错语义贯穿递归/fork/子流程，旧流程保持旧语义；共享 `application/workflows/event_translation.py`。
- Task 4–6 未生效设置（重试、出错策略、超时动作）在设置面板隐藏、运行前提示、批量日志报告一次；新建流程用 v2。
- Task 7–9 执行名额与存活浏览器分开计数；人工等待不占执行名额；内存 ≥85% 且已有运行任务时暂停新派发；容量设置按修订号有序应用并持久化（`rm1_app_settings` 迁移、`ExecutionSettingsService`、设置页）。
- Task 10 数据领取在线程中执行，取消 tick 时持锁等待领取落定。
- Task 11 worker stderr 有界落盘与脱敏尾部；丢失消息含日志路径。
- Task 12/13 `press_key` 节点（后端执行器、真实 CloakBrowser 测试、前端模块与录制）。
- Task 14 黄金场景 G3 点击版/回车版分别校验；目录说明与旧并发计划标注 superseded。

## 验证（如实）
- 容器（Linux，非 Mac、非 CI）：后端单元 1920 通过；集成/契约的 M1 相关文件通过；前端 typecheck/lint/脚本测试通过，vitest 5984 通过。已知容器限制导致的失败：缺 cv2/skimage/faster_whisper/PyInstaller、`backendVersion` 元数据、需真实 Linux 边车子进程的测试、worker_protocol 真实进程测试、安卓诊断页日期文案、设置集成测试需要真实边车。
- 未取得：AC1-09/10/13/15 的 Mac/CI 同环境数据（见 knowledge 文档 M1 评审段）。**不要把容器数字当作 Mac 数字。**
- 评审后修复：见 e9be594 与 knowledge 文档。

## 已知缺口（保留，不是通过）
- Windows 输出写入只支持新建文件，追加/替换/身份校验写入返回 501 `ARTIFACT_PLATFORM_UNSUPPORTED`。
- OCR（EasyOCR）真实模型用例在 Windows 上显式跳过（用户决定不验收）；单独计时表明 EasyOCR 本身 15 秒内可跑完，worker 内 60 秒超时的根因未查明。
- Studio `workflow_worker.py` 的 stderr 仍为 DEVNULL。
- worker 磁盘日志 `worker-stderr.log` 是原文；仅返回给 API 的尾部做了脱敏。
- 迁移 `rm1_app_settings` 降级会删除设置表（可接受）。

## 下一步（交给 Claude Code）
1. 在 Mac 上跑 `bench_claim_loop_lag --rows 10000`、`bench_event_commit` 与 M0 基线对比；CI 上 dispatch `golden.yml`（rows=30）读取 G2/G3 两版报告。
2. 取得以上证据后把 `.ai/plans/2026-09-30-remediation-program.md` 中 M1 改为 done，并开始 M2 细化。

## 合并与验证更新（2026-10-02）
- M1 已快进并入默认分支 codex/architecture-baseline（合并提交 a6ecc5c，类型修复 60ff484）；分支 remediation/m1-stop-silent-failures 与基线一致。**M1 仍不标 done。**
- 合并后 CI：a6ecc5c 的 ARM、Windows 在 mypy 步骤失败（psutil 无类型桩、`Result.rowcount`、严格类型债务新增 4 项/已解决 1 项），已在 60ff484 修复（本地 mypy src、严格债务门 890=890、ruff 通过）；修复后的 CI 结果见交接文档。
- golden rows=30（run 37004030835 @ a6ecc5c，macos-15 真实 CloakBrowser）：G2 28/30 成功；G3 点击版 29/30、回车版 29/30；各自 loop_lag_p99 45.2/29.4/43.3 ms。AC1-15 的"G3 两版跑通"有 30 行 CI 证据。
- **G2 failure_reason_ratio 实测 0.0**（g2-scrape/g3-click/g3-enter 均 0.0）：与 M0 基线（通用原因）相同，M1 在该指标上**没有可见提升**。根因未实证；代码阅读的判断：M1 的节点失败文案（event_translation.node_failure_message）已带具体原因，但 golden 的 metrics 读取 run.error / task.error，这两处在批量运行里仍是通用句（"工作流未完整成功…"等），即指标读取位置与 M1 修改位置不一致。待在 golden 里读节点记录/运行日志确认，再决定改指标读取还是把原因同步到 run.error。这是 M1 退出前要追的项，不是通过。
- 仍缺 Mac 同环境数据：AC1-09（bench_claim_loop_lag 1 万行）、AC1-10（event_commit_ms_p50 对比 M0）、AC1-13（Mac 真实 CloakBrowser press_key；CI 上 golden G3 回车版已在真实浏览器通过，可作为部分证据）。
