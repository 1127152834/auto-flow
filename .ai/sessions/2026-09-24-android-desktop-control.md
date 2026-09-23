# Android 桌面控制增量

- 日期：2026-09-24；状态：confirmed（本轮修复和证据），完整目标仍active/partial。
- 来源：隔离分支5eedb18e基础上的真实Electron/CUA、Mac/Lima/ReDroid、失败测试与独立增量审查。
- 实际修复：正常成功命令保留ADB后台服务，异常/超时/取消仍清理自己的进程组；切端暂停新输入及旧心跳，查询身份包含generation/endpoint，transition绑定backend/会话；ADB断线的转发及随机jar清理必须可核实，不隐藏未知结果。
- 真实控制链：自建设备bf8fe420-30c6-4996-8255-98c59a44742e完成嵌入/原生往返、原生跨模块保留、受控SSH断线、结束后文件与归属清理、重连输入及嵌入离页；最终容器/卷missing。恢复磁盘不足/取消再次真实通过。审查修复后另建设备473df9d4-3277-4c89-92ab-30a08b3510c2，最终构建重复原生跨页/切回/输入/离页释放，generation3→4，最终容器/卷missing。T05/AC05/AC06关闭；102步骤仍83passed/16not_run/3blocked。
- 审查：2项Important（只读同generation缓存覆盖、跨backend暂停串扰）已RED→GREEN，定向44项通过；独立运行时/stream69项通过。最终后端4041passed/26skipped/2warnings in823.04s、前端424files/5631passed in333.39s；类型/lint/OpenAPI/build通过。先前两次计时失败及单独重跑保留在报告，未改断言。
- 未完成：精确200%与指定窗口、APK实际写入期间断线/进程终止、前台规模指标、阶段回退及GApps外部条件。不可把局部控制链扩大为完整AM1–AM4通过。
- [详细证据](../../docs/qa/android-management/2026-09-24-desktop-control.md)。三份既有Studio脏文档保持原SHA256，不纳入提交。
