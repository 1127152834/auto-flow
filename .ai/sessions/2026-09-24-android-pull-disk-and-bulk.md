# 2026-09-24 拉取磁盘准入与桌面批次

状态confirmed局部/整体partial，来源代码18b75c49、真实Lima/ReDroid/Electron、docs/qa/android-management/2026-09-24-pull-disk-and-bulk.md。

- pull实际VM DockerRootDir+Lima宿主磁盘探测，严格defaultfalse未知确认，真实0pull拒绝/1pull中断重启核实成功，基础镜像保留。
- 真实两台批次取消、新批次、搜索0/2保留选择完成；数据卷/容器已清理。AC15关闭，完整性能不借此关闭。
- 覆盖自动化493后端、最终边界142、184前端与工程门禁通过；旧mypy22项已核对基线；最终全仓套件待Task4。
- Task3独立审查进行中。Task4创建/复制/恢复接入同一检查，所有确认必须绑定当前请求，不继承源配置许可。
- 主工作区未改，三份Studio历史脏文件不纳入提交。

2026-09-24后续confirmed：真实Electron重启发现未知pull、核实前拒绝新请求、显式核实succeeded并清空历史、改引用撤销确认已验；自有登记已撤销。c4b6159d修复202/failed重放误报已接受，187前端回归通过，独立复审进行中。
