# 项目任务列表导出（2026-09-24）

- `list_export` 进入项目可运行目录，目录从 139 增至 140。执行器仍使用冻结 WebRPA 的列表序列化、分隔符、编码和追加规则；项目 worker 复用 AutoFlow 原有安全文件存储与事件 ACK，产物快照单独登记。项目文件下载统一以 `application/octet-stream` 返回，避免文本内容被当作网页执行。
- [真实独立 worker 用例](../../../../../../apps/backend/tests/integration/test_project_data_worker.py)使用临时 SQLite、项目自动化与无浏览器任务，核对覆盖、追加和空列表文件的三份不可变快照。共享文件存储的大小上限在覆盖输出前检查，超限保留原文件；[文件边界用例](../../../../../../apps/backend/tests/integration/test_project_screenshot_writer.py)核对 ACK 前不得报告成功、文件哈希、空文件及取消清理。关联测试 76 项通过；Ruff、mypy、OpenAPI 与脚本语法检查通过。
- [正式 Electron 开发入口](../formal-project-list-export-electron-KCRnvq/result.json)：从主窗口真实点击进入 Studio，声明列表、配置覆盖和追加两节点、保存、正常关闭后在项目创建自动化并启动任务。任务页显示两个可下载文件；正式内容接口的字节和 SHA-256 分别核对为 `甲\n乙`、`甲\n乙\n甲\n乙`；无 CloakBrowser 进程。首次尝试仅因验收断言把缺省 `appendMode` 当作显式 `false` 而中断，生产代码未因此改变。
- [macOS arm64 本地未签名包](../formal-project-list-export-electron-5LDYhz/result.json)通过同一真实 UI 链路。包内 `app.asar` SHA-256：`949ec3a3ec6e42e1659ef75587ccea4f3279fcef41e01e9022fc1689b59dc3d9`；冻结后端：`d0d18fac6c5f3e75574fc1adf3f608294b74a4400a40f53683f0ae9944287ea1`；Electron：`afa086d829713c1385c6f15999898a8b959af24abb46df949ac324047afc30a7`。macOS Intel、Windows 与用户数据库未实测；Windows 安全文件输出仍按现有边界明确拒绝，不假定通过。
