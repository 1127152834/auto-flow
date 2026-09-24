# 安卓命令树回收与真实 AM4 故障续行

- 日期：2026-09-24；状态：confirmed（下列执行部分），目标 active/partial。
- 基线：隔离 `codex/android-management-complete@162fa380`。上轮属于 progress；本轮继续可执行故障链，未因 GApps/十台条件不足停止可做工作。
- 来源：[恢复故障报告](../../docs/qa/android-management/2026-09-24-restore-cancel-and-disk-full.md)、[清理硬中断](../../docs/qa/android-management/2026-09-24-cleanup-interruption.md)及各 JSON。
- 实测发现取消后目标仍持续写入。根因是 run/run_file 仅 kill limactl，SSH 子进程继续持有归档描述符。四个真实进程取消/超时测试先 RED（4 failed），改为独立 POSIX 进程组及共用回收方法后运行时 63 passed。未修改归属、Operation、锁、代次、幂等、OpenAPI 或迁移。
- 真实 16MiB 目标 tmpfs ENOSPC、解包中请求任务取消、重启隔离、普通 recover 不能解除未完成恢复、新请求读回均通过；真实 backup ENOSPC/取消、backup/restore 传输中强杀自有进程树也通过。源及正常备份摘要保持，全部自建设备/卷/备份/私有挂载已清理。
- 同脚本加入独立第二份真实备份的故意损坏并重跑：409 BACKUP_CORRUPT、父failed、新目标卷确为空，重启和重放保护通过。磁盘/取消再跑通过；正常备份289280431字节读回，五台自建实例/卷和两份备份清理。不能把QA损坏样本解释为产品修改源备份。
- 真实多对象清理首项删除且回执提交后 SIGKILL：重启父 needs_verification，原请求不续删，核实503，新预览才删除余项；外部路径探针不变。首轮QA误用新核实请求ID被409拦截，修正请求后完整重跑，未降低生产保护。
- Android 聚焦451 passed / 2 warnings（30.99s），全src/tests Ruff和compileall通过；唯一Alembic head am01_management_operations。完整后端4035 passed / 26 skipped / 2 warnings（842.30s），OpenAPI再检查通过。前端源码未改，前一提交424文件5626项及类型/lint/build仍对应同一树。最终9台自建已删实例再经生产归属核实全部missing。
- T18/T19已列功能证据补足；无归属来源旧客体文件继续排除，不应为了清理覆盖率推断其可删除。历史RED缺证和其他阶段真实未运行项保持原状态。
- 三个Studio文档SHA与进入时一致，排除提交。目标仍有桌面控制/断线/窗口与性能、真实批次未知结果、自定义镜像阶段链和外部GApps/十台条件；不标整体完成。
- T20.2 的列明故障已补实际证据并关闭；当前102步骤为82 passed、17 not_run、3 blocked。T20.3仍包含其他阶段尚未运行的真实验收，不将整个T20勾完。
