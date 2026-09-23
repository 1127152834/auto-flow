# 项目任务自定义模块执行证据

分类：AutoFlow 必要适配。复用 Studio 已迁入的 `CustomModuleService.freeze_closure`、`_WorkerCustomModules` 和生产节点注册表；项目准备时冻结递归依赖，项目 worker 使用同一份快照，不在运行时读取可变模块定义。

- 真实 SQLite／独立 worker：`test_project_batch_freezes_and_executes_custom_module` 验证两层模块、准备后修改定义不影响执行、子节点的执行作用域、输出值 42、worker 退出。`test_project_rejects_excluded_node_inside_custom_module` 验证已排除通知节点在启动前拒绝。`test_project_detects_browser_requirement_inside_custom_module` 验证网页节点触发 CloakBrowser 资源要求。
- 证据查询：子节点名称来自冻结模块；尝试、日志和输出保留执行作用域。循环头执行前后的作用域可以变化，尝试记录以完成时作用域为准；旧记录没有该字段时仍可读取。
- 正式 Electron 开发入口：[真实 UI 结果](../formal-project-control-electron-rYfmyx/result.json)、[项目模块任务画面](../formal-project-control-electron-rYfmyx/project-custom-module-task.png)。用户在 Studio 创建模块、声明输出、拖入项目流程、保存，然后从项目页创建自动化并启动真实 worker；结果 `project_module_result=42`，子节点作用域可查，临时 CloakBrowser 无残留。
- 回归：后端项目 worker／证据／模块 32 项，前端任务详情相关 28 项；Ruff、mypy、TypeScript、ESLint、OpenAPI 一致性和 renderer/main/preload 构建通过。首次正式脚本失败于视图切换时序，另一次暴露并修复了循环作用域误判；失败记录保留在相邻 `formal-project-control-electron-hoxY4s`、`YCWAoA`、`o75wKo`。

边界：仅 macOS arm64 开发入口通过；冻结包与 Windows／Intel 待单独验收。项目任务中的运行期交互命令、跨工作流文件调用和其他模块分支仍按缺口登记，不能由本次纯数据／网页模块证据推断通过。用户数据库未接触；213 节点范围及 14 个已排除通知节点不变。
