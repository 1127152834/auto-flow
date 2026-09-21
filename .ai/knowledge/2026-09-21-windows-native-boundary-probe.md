# Windows 原生边界实验与当前实现

日期：2026-09-21。状态：confirmed（实验和 30170c66 原生子集）；0102c047 启动所有权修复原生复验中。来源：现有 GitHub Actions 原生实验、源码和 Microsoft API 文档。

- 历史实验 35574503412：持有拒绝写/删除共享的目标句柄时，FileRenameInfoEx flags 1 返回 error 5，flags 3 返回 error 32；原文件未改变。父目录持有期间改名返回 error 32。这仅否定被测组合，不证明所有 Windows 方案均不可行。
- 当前生产新文件输出沿用现有 artifact 快照/摘要/登记，逐级持有目录句柄并拒绝 reparse/junction/保留名；按暂存文件句柄发布到不存在路径，冲突不覆盖，取消/登记失败只删除拥有的暂存对象。既有文件覆盖、追加、安全读取仍 501；完整 S4 未完成。
- 原生 35577767754（30170c66）：83 passed、27 skipped，包括真实 workflow-worker Base64 发布和登记快照一致、路径/目录冲突及 Job 恢复。项目数据节点准入未扩张成全部 Studio 节点。
- 进程复用 kill-on-close Job 与 birth 核验。Windows venv python.exe launcher 和实际解释器不是同一进程；只有直接拥有 launcher 的监督者能在同一句柄核验 birth 后将它加入 Job，恢复路径只能核验已有成员，不能扩展成员。
- 最终审查发现 ready 前取消缺少整树确认；0102c047 将 Job 创建提前到父端 spawn 前，子 bootstrap 加入父 Job，父端持久化 launcher 所有权后才发送 start，结束时核验 Job active=0。未确认身份/权限拒绝保留 blocker。新增原生取消/超时案例正在 CI 复验。
- `terminate_verified_windows_process` 独立实验 helper 已删除，生产只保留现有 Job 路径，不维护第二终止实现。实验脚本保留为显式手动可行性探针，不作为日常完整矩阵的额外实现。

参考：[文件重命名契约](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-fscc/4217551b-d2c0-42cb-9dc1-69a716cf6d0c)、[SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle)、[Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)。

### 2026-09-21 原生进程句柄复验与修复（confirmed / native fix pending）

35582165961 @6f1390a1：87 passed、27 skipped、2 failed。wrong-birth/denied 负向保护之后的合法恢复已删目录，但终止前持有的子进程句柄 WaitForSingleObject(0) 返回 WAIT_TIMEOUT (258)。这推翻了“可能只是重新打开 PID 的保守探测”的推断，证实 Job active=0 不能单独证明进程对象已退出。

共享 terminate_worker_job 在 TerminateJobObject 前取得并验证 Job 成员句柄；保留原 accounting 归零检查，并在同一个清理期限内等待每个持有句柄报告 WAIT_OBJECT_0。拒绝访问、身份不明、等待失败和超时仍抛错，调用方保留目录/容量。查询名单按原生 NumberOfAssignedProcesses 扩容，PID 重用到其他 Job 不获得操作权限。没有按 PID 杀进程、固定 sleep 或放宽测试断言。

最小反例 3 种等待结果 RED→GREEN；相关进程/恢复测试 63 passed、8 native-only skipped，ruff/mypy passed。Windows 原生回归待新 Actions，不把本机模拟检查写成原生成功。

来源：[TerminateJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-terminatejobobject)、[Job process ID list](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_process_id_list)。
