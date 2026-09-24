# 安卓管理续行：备份真实故障与逐项审计

- 日期：2026-09-24；状态：confirmed（已执行部分），目标仍 active/partial。
- 来源：用户目标附件、当前 30eb0926 工作树、[真实故障 QA](../../docs/qa/android-management/2026-09-24-backup-failure-verification.md)、[逐项追踪](../../docs/qa/android-management/2026-09-24-task-evidence-audit.md)。
- 上轮属于 progress：提交 30eb0926，后端4031/前端5625及真实实例新证据。本轮未将已提交或绿色全量当成目标完成。
- 独立64MiB HFS+映像真实 errno28；备份 failed，无目录/staging；释放容量新请求备份19353772字节。实际传输133120字节时取消，needs_verification，无可用备份/暂存，原请求不重放；源数据读回不变，自建实例/卷与磁盘挂载已清理。
- [真实 HTTP 解包中 SIGKILL](../../docs/qa/android-management/2026-09-24-restore-transfer-interruption.md)两次通过；最终289382827字节备份，256MiB探针在1691648字节时杀独立后端进程组，稳定部分文件4124672字节。重启needs_verification、重放/启动/备份/控制均拦截；删除不完整目标后新请求恢复，源/目标SHA一致，源备份文件摘要不变。三台自建实例/卷与备份均清理，exit0。首轮前置未登记镜像的QA失败已修正并清理，没有降低准入规则。
- 发现 T17/T18 面板遗漏本机未加密及恢复能力边界，先写按钮可访问说明回归：RED 1 failed/25 skipped，最小补两段可见文字和 aria-describedby 后 GREEN 26 passed。后端生产代码未修改。
- 目标附件提到的101步是旧值；当前102步已逐项更新，81 passed/18 not_run/3 blocked。部分历史 RED 没有独立输出，保留缺证，未用当前 GREEN 追认。所有20任务的实现、契约、迁移、前端和测试文件已有明确映射。
- 本轮原命令 Android 聚焦447 passed/2 warnings；UI增量前Android前端14文件135项；唯一迁移head am01_management_operations。UI改动后前端全量424文件5626项通过，894.27s；Node22类型/lint/OpenAPI/build全部exit0，11751模块54.79s。后端树未变，全量4031/26仍有效；QA脚本Ruff通过。
- 继续项：恢复目标磁盘不足/取消恢复、桌面控制/断网/尺寸/前台指标、运行时瞬时故障或未知结果真实核实、候选自定义镜像链；十台容量与 GApps 账号/镜像仍有外部不足。三个既有 Studio 文档受保护，不提交。
