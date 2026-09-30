# 安卓清理目录与文件保护

- 日期：2026-09-23；状态：confirmed（本增量），完整目标 active/partial。
- 基线：`codex/android-management-complete@a47bbb9d`；来源：本次代码和 `docs/qa/android-management/2026-09-23-cleanup-verification.md`，附真实 JSON/脚本。
- 完成：GET cleanup/resources 契约/OpenAPI/UI对象选择；暂存和未登记备份目录；内容/inode/ctime等指纹；来源引用/归属/不可逆影响；同大小变化409；备份/恢复/清理共用工作区文件锁；只有明确retained状态列作保留数据。
- 验证：后端346 passed、前端Node22 Android14文件104 passed，定向Ruff、compileall、类型/lint/build、OpenAPI和结构4项通过；唯一migration head仍am01_management_operations。全量旧失败未重跑/未解决。
- 真实：30490d8a-197f-48f2-a85c-252b51173c63→ea99d205-af43-473a-b709-05e5592aff3e，HTTP目录/同大小变化409/仅选中两临时产物删除/恢复期间清理拒绝/新实例启动读回通过；所有自建容器卷清理0，LimaStopped。临时产物是显式实验创建，不冒充崩溃演练。
- 剩余：APK遗留临时文件、恢复中断隔离/核实、xattrs、高级日志、规模性能、完整门槛及全分支审查。既有3份Studio文档未覆盖。
