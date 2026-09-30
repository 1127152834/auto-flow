# 安卓批次真实失败与结果未知续行

- 日期：2026-09-24；状态：confirmed（本轮范围），完整目标 active/partial。
- 基线：隔离 codex/android-management-complete@0c67bffc；上一轮为 progress，命令树修复及 AM4 故障证据已提交，三个 Studio 文件原样保留。
- 来源：[真实批次报告](../../docs/qa/android-management/2026-09-24-bulk-runtime-fault.md)与结果 JSON。新增 opt-in QA 脚本复用真实 HTTP/SQLite/Mac runtime，不改生产代码。
- Lima 初始已停止，启动现有 VM 后继续；预算不变。第一故障场景真实 Docker 对已消失自有容器 stop 返回非零，先部分失败；recover → restore → retryFailed 后成功。第二场景真实 stop 后回执前 SIGKILL，重启为 needs_verification，retryFailed 不重放，verify 后成功且 generation 不变。两台重启读回探针均一致。
- QA 初版遗漏 retained 实例显式 restore 被生产保护拒绝；修正脚本并完整重跑通过。不是新增生产代码 RED→GREEN，不改变安全语义。
- 定向批次/容量回归43 passed in5.76s；QA Ruff通过。最终与失败轮四台自建实例生产 verify_deleted 均missing。全量门槛沿用代码未变的上一轮4035/26和前端5626，不冒称重新运行。
- T13/AM-AC15由partial补足为passed；102个步骤仍82 passed/17 not_run/3 blocked。桌面控制/真实断线/精确缩放、前台与探测指标、自定义候选镜像、APK实际断连，以及GApps/十台容量仍未完成。
