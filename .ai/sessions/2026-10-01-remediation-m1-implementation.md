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
