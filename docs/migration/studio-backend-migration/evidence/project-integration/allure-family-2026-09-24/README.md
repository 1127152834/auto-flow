# 项目任务 Allure 报告节点族（2026-09-24）

- `allure_init`、`allure_start_test`、`allure_add_step`、`allure_add_attachment`、`allure_stop_test`、`allure_generate_report` 复用已迁入的冻结 WebRPA 执行器与单文件 HTML 生成器，进入项目任务目录 161→167。Studio 批准范围仍为 213 个；项目目录尚有 46 个入口待核销，其中画布工具不应按普通执行节点处理。
- 项目运行器为报告生成节点提供现有文件产物写入器，并在共享文件边界准入 `text/html`。文件仍受 64 MiB、路径防逃逸、原子写入、不可变快照和父进程持久回执约束；节点执行成功不先于产物确认。报告内容与附件仍由原版生成器处理，不创建第二套报告实现。
- [项目真实 worker](../../../../../../apps/backend/tests/integration/test_project_data_worker.py)完整执行六节点并读取报告内容；[产物专项](../../../../../../apps/backend/tests/integration/test_project_screenshot_writer.py)验证 HTML 快照等待回执及 `../` 路径拒绝。冻结源码差分和项目关联共 59 项、产物专项 2 项通过；Ruff、mypy、OpenAPI、目录和脚本语法检查通过。前端业务代码未改，复用上一功能块已通过的 TypeScript、ESLint、renderer/main/preload 构建，并在本次正式包中再次验证入口。
- 正式 Electron [开发入口](../formal-project-allure-electron-0XNm0e/result.json)与[本地未签名 macOS arm64 包](../formal-project-allure-electron-KdlMyB/result.json)均由主窗口真实点击进入 Studio，配置六节点、保存、正常关窗并运行项目任务。任务页显示一份可下载 HTML；报告含套件、用例、步骤和附件，内容接口字节的 SHA-256 与登记值相同；未启动 CloakBrowser，未修改用户数据库。
- 包内 `app.asar` SHA-256：`6e7de4e80636aa7bb855a9dcaa19ec0a38708d615ecb278a3cc5fff08eb10127`；冻结后端：`1152cc07383fee58aa82b686b202f2e4b38a8152fafb9e7d11ea0c983edba459`；Electron：`afa086d829713c1385c6f15999898a8b959af24abb46df949ac324047afc30a7`。验收脚本在源码提交前启动，JSON 的 `gitHead` 是启动基线；哈希标识实际包内容。macOS Intel、Windows 和用户数据库未实测。
