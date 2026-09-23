# 项目任务跨工作流调用（2026-09-23）

- 范围：保留节点 `run_workflow_file`；项目 Studio 从当前项目的真实文档中选择子工作流并保存稳定 ID。独立 Studio 的原本地文件行为保持不变。
- 准备：复用现有工作流依赖冻结与自定义模块闭包；项目范围内解析依赖，将子流程快照纳入运行计划。其他项目的引用在启动前拒绝；依赖中的浏览器和模型要求在资源选择前计算。
- 执行：项目 worker 复用 Studio 的嵌套工作流执行器、变量回收和事件作用域；重复调用不读取执行时修改的子流程。失败且父节点配置继续时，子节点失败证据保留，父任务可成功。
- 自动检查：`test_project_data_worker.py` 与 `test_project_graph_executor.py` 共 28 项通过；图执行器边界复核 4 项通过。前端专项 51 项、TypeScript、ESLint、OpenAPI、renderer/main/preload 构建及 PyInstaller 通过。
- 正式 Electron 开发入口：[`formal-project-control-electron-IVC9bC/result.json`](../formal-project-control-electron-IVC9bC/result.json) 为通过；真实 UI 创建子流程与调用方、保存、从项目自动化启动，独立 CloakBrowser 打开本地受控网页，子节点上下文、输出 42、日志与进程清理均核验。临时工作区，未动用户数据库。
- macOS arm64 本地未签名包：[`formal-project-control-electron-IHRniA/result.json`](../formal-project-control-electron-IHRniA/result.json) 为通过，针对代码提交 `06171cd2` 重建并按相同真实 UI 路径执行。包内 `AutoFlow` SHA-256 为 `afa086d829713c1385c6f15999898a8b959af24abb46df949ac324047afc30a7`，`app.asar` 为 `a976f4fa7cef548632553c6c349d253dc0bb1b9be4d40bfe47d73e56930b09e3`，冻结后端为 `33f1a6b4346d8ba4170376c8c3e68b640a88b8e7ee8cf1c3e2826d7316cf8928`。
- 关联广域回归中四项旧断言曾要求将默认字段写回 v3 冻结文档；按现有预检语义改为断言快照与保存文档一致且未改写默认字段。`test_studio_document_catalog.py` 28 项通过，`test_project_run_start.py` 16 项通过。
- 尚未核销：项目任务中需要运行期交互命令的子流程、macOS Intel/Windows、真实用户数据；本条不把 Mock 合同当作真实执行。
