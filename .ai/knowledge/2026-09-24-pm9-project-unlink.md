# PM9 项目删除与独立文档保留

2026-09-24 AU-08项目删除解除关联补证（confirmed本机子范围）：当前cb040daf未签名ARM包中，同一独立文档公开编辑后由真实worker执行，项目归档停止并取消Task，再精确名称删除项目；工作区原命令查询/重放一致，项目级查询404、冻结快照清空，原文档ID/版本/节点/边保留并在新项目关联。完整桌面passed/23截图，新关联画面已目视核对；102脚本、4映射/251引用通过。两次查询地址/可选DTO默认值夹具错误保留，非产品修复。仅补测试与证据，不重跑无改动生产全量/构建；CLI401仍阻断新矩阵。AU-08 Studio占用/绑定去向/文档所有权/持久文件清理及持久身份反例仍保留；251状态和241生产/19实现/8测试/24外部缺口计数不变，releaseAccepted=false。详见project-unlink-follow-through.json。

来源与验证：`scripts/smoke-project-management-desktop.mjs::checkAutomationDeletion`；日志和23张截图位于 `.tmp-tests/pm9-project-unlink-2026-09-24/`，SHA256及具体边界见 `docs/project-management/implementation/pm9/project-unlink-follow-through.json`。原始失败目录 `initial-desktop/` 与 `receipt-desktop/` 保留。

既有契约：删除后的命令在工作区查询，项目地址404；DELETE响应包含可选字段默认值，而查询排除未设置字段。只比较这两个DTO表示差异，不放松操作身份或实际删除结果断言。

下一步：当前新原生矩阵需恢复GitHub认证或手动触发；I/G/L/M/S4/FR/AD/W/P均保持待确认的独立架构方案。AU-08不升级为verified。
