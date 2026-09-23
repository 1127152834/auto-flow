# 安卓恢复中断隔离与发布

- 日期：2026-09-23；状态：confirmed（本增量），全目标 active/partial。
- 基线：`codex/android-management-complete@be067690`；来源：本轮代码、RED/GREEN、真实 Mac 实验，详见 `docs/qa/android-management/2026-09-23-restore-isolation-verification.md` 及相邻 JSON/脚本。
- 根因：HTTP config 的恢复元数据未被真实 new_device 复制；测试运行时展开 config 掩盖差异。recover 清除控制异常，但未隔离部分恢复；异常处理保存未提交的 restored 本地对象；成功设备/回执原先分两次提交。
- 完成：IO前保存恢复意图；管理/控制/连接/预览/备份共用隔离规则；恢复创建拒绝start=true；成功事务绑定目标/generation/工作区/请求/备份/未删除状态；异常读回数据库识别提交回执丢失；取消不解除隔离；管理 restoreState 契约/OpenAPI/UI及去重原因。既有JSON字段，无新增迁移，head仍am01_management_operations。
- 验证：有效RED分别8/6/1项失败，契约及UI各1项失败；最终Android后端362 passed、Node22前端14文件105 passed、定向Ruff/compileall/type/lint/build/OpenAPI/结构通过。未重跑全后端/全Ruff/全前端/全scripts；旧失败仍需处理。
- 真实：独立源0ef36cb9-635e-45de-8aad-f34553af4d24，部分目标842e6206-385c-54c6-b530-6eab5a4810b5，正常目标ee9569d6-2b83-5c8f-9ea7-8b4c342151da。实际部分卷写入后注入Timeout；recover后仍拒绝start/restart/restore/control/backup。正常HTTP恢复及重放202，启动读回测试内容，UID/GID/mode及源测试条目不变。三个容器/卷全部清理，备份删除，LimaStopped。没有把受控异常注入当成kill -9/断电，也未宣称完成真实Electron窗口验收。
- 待办：xattrs、manifest/格式校验、直接恢复服务新目标约束、硬进程中断/完整重启、APK临时清理、高级脱敏日志、真实应用动作、1/5/10性能及全分支审查。GApps外部条件blocked；这些软件缺口为未完成。
- 保护：三份既有Studio未提交文档未覆盖/未纳入；没有恢复工作流执行链。
