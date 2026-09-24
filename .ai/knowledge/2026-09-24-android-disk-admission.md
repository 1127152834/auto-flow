# 安卓磁盘准入当前事实

- 日期：2026-09-24；状态：confirmed产品与真实后端；完整验收partial。来源：[当前证据](../../docs/qa/android-management/2026-09-24-create-disk-admission.md)、源码ef0af03f及实际Mac/Lima运行。
- AM-R12的备份、镜像拉取、单/批创建、配置复制、保留卷重建和备份恢复均有写入前准入。VM读取实际DockerRootDir；宿主写入检查实际Lima磁盘文件的文件系统。环境面板的宿主workspace数值是另一观测，不能代替写入目标。
- 无法可靠估计增长量时缺省拒绝。严格bool allowUnknownDiskEstimate必须由当前操作显式确认，进入持久请求摘要；false与缺省保留历史回执兼容。模板/来源设备/备份的旧确认不能授权新恢复。零空间与探测失败不可被确认绕过。
- 备份恢复在目标创建后、实际写卷前再次检查；写入已派发或目标已创建后的取消保留needs_verification。失败创建批次的零写入预检链允许显式重试，provider核实任何已有容器/卷后拒绝空白重建。
- 最终真实复跑验证单实例、保留卷恢复、备份恢复、模板批量、配置复制与未确认批次retry仍失败；八条自建记录及备份均已清理。四个确认入口的组件测试通过，真实新UI因Mac锁屏blocked，二者不得混用。
- Task3与Task4独立审查Approved。最终全分支审查和完整后端结果见当前QA报告更新；Node本轮26.7.0，全前端424文件/5683项已通过，不能沿用旧Node22运行标签。
- 本记录supersedes project-context中“创建/拉取磁盘准入未实现”的历史进度；历史真实证据及剩余外部条件保持有效。无新增数据库字段，唯一迁移head仍am01_management_operations。

- 后续最终候选78bf8c92（confirmed）：额外五项全分支审查问题已修复，独立复审C/I均0，后端4118passed/26skipped/2warnings、前端5689passed及规定门禁全部通过；真实Mac增加永久删源后备份恢复并读回，9条自建记录均清理。当前完整签收仍partial，见[最终报告](../../docs/qa/android-management/2026-09-24-final-acceptance.md)。
