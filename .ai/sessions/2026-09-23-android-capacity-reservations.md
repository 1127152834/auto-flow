# Android 共享运行环境的持久容量预算

- 日期：2026-09-23；状态：confirmed，本增量；完整目标 active/partial。
- 来源：基线19755811，同提交的 `docs/qa/android-management/2026-09-23-capacity-verification.md`。
- 根因：生命周期全局锁只保护活动进程，超时/取消释放锁后，Docker暂未运行或已停止的未知操作不再计入原预算；connect另有直接start旁路。
- 在运行时根目录以格式1原子保存预算，冻结workspace/device/generation/完整containerId/marker/内存；复用现有全局锁，保持生命周期并发1。只在状态核实或明确未派发时释放，不设TTL。
- connect不再隐式启动；prepare显式调用管理启动。运行限额不重复计费，实际Memory=0或预留未知/损坏失败关闭，实际限额大于配置时采用更大预算。
- RED→GREEN覆盖18项集成；最终Android+迁移head289通过、相关Ruff/compileall/OpenAPI/结构通过。无公开DTO或工作区DB形状变化，head仍am01_management_operations。
- 真实双工作区实验：第一台1536MiB实际启动/停止后丢响应，第二台6144MiB只创建停止容器并做准入；新runtime仍拒绝，原workspace核实后才准入。各自容器/卷0，共享预算恢复实验前内容；Lima恢复Stopped。
- 最后新增的发布失败撤销与名称规范化只自动化验证；不声称真实磁盘故障、创建丢响应、两台同时运行或规模性能通过。
- 本轮未运行完整前端/构建（无前端修改）；完整后端/Ruff/前端/脚本的既有失败仍未解除。继续AM4、跨重启应用恢复、规模/真实应用验收和最终分支审查。
