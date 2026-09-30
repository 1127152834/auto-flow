# Android 管理核验与诊断增量

- 日期：2026-09-23。
- 状态：confirmed（本轮修复与命令）；目标状态 active/partial。
- 来源：隔离分支 `codex/android-management-complete`，父提交 `3ee61947`；详见 `docs/qa/android-management/2026-09-23-validation.md`。
- T15：完成标记缺失保持 unknown，原请求绑定、持久回执先于标记释放；磁盘错误保留可核验证据，未知回执拒绝后续写入，安装后观察失败不伪装确定失败。
- T13：Docker 未限额内存、枚举失败和缺失容器信息均按容量未知拒绝准入。
- T19：诊断归属用 runtime workspace hash；默认只导出状态、时间、错误码白名单。
- 验证：后端 Android+迁移 head 集合 253 passed/2 warnings；Android Ruff、compileall、OpenAPI check 通过，唯一迁移 head 为 am01_management_operations。完整 Ruff 118 errors；全后端最终重跑 278 passed/1 failed，停在 proxy password-schema 断言。最终完整门槛未通过。
- 真实：隔离 smoke 102/102 应用，截图 652550 bytes，stop/start/delete 完成；标签查询无容器/卷残留，Lima 恢复 Stopped。
- 后续：持久容量预留、预览取消、前端核验失败解锁、命令语义、备份元数据/安全链接、中断恢复、高级日志/临时文件、完整门槛与最终审查。不要把这些软件工作标成外部 blocked。
- 保护：3 个既有 Studio 文档改动不覆盖、不提交。9 月 22 日历史文档的错误 commit 引用已纠正为 3ee61947。
