# 项目任务 JSON／随机数／时间变量族（2026-09-24）

- 项目可运行目录从 136 增至 139；复用已迁入的冻结 WebRPA `control_variable` 执行器，不修改解析、随机和时间算法。JSON 解析任务输出取执行器实际写入的 `variableName`，即使旧文档同时带有 `resultVariable` 默认字段也不登记错名；随机数和时间任务输出取真实变量值，而不是节点摘要对象。
- [真实项目 worker 测试](../../../../../../apps/backend/tests/integration/test_project_data_worker.py)使用临时 SQLite 和独立进程，无 Profile 或 CloakBrowser 依赖。JSON 路径得到“乙”，固定边界随机数得到 7，时间为日期字符串，三项输出名与实际变量一致。关联项目数据、冻结源码差分及项目适配 84 项通过；Ruff、mypy 和 OpenAPI 一致性通过。
- [正式 Electron 开发入口](../formal-project-variable-electron-yjv1ZR/result.json)经真实鼠标、键盘声明初值，配置并保存三节点流程，正常关闭 Studio 后从项目自动化运行并读取三个结果；未启动浏览器。真实 worker 红测揭示项目适配曾按旧默认字段登记 JSON 结果；[首次正式尝试](../formal-project-variable-electron-MAhWQ0/blocked.json)及[再次尝试](../formal-project-variable-electron-HXtBs4/blocked.json)还暴露测试脚本按 Tab 时选中了旧变量名建议。脚本改用实际键盘 Escape 关闭建议再离开输入框，保存断言与项目结果均复验通过；产品输入组件未因测试改动。
- [macOS arm64 本地未签名包](../formal-project-variable-electron-kmkhPi/result.json)通过同一真实 UI 链路。包内 `app.asar` SHA-256：`949ec3a3ec6e42e1659ef75587ccea4f3279fcef41e01e9022fc1689b59dc3d9`；冻结后端：`f4455804e5e76ef5342d200d1e7c8e7bcd621312d2d420b2b83119fd5701f61c`；Electron 可执行文件：`afa086d829713c1385c6f15999898a8b959af24abb46df949ac324047afc30a7`。正式 `result.json.gitHead` 是验收开始时的上一个提交，以上哈希对应实际运行的包。
- Base64 节点的文件读取／写入分支仍依赖项目文本及二进制产物服务，未开放项目任务入口；打印日志的成功级别尚未纳入项目日志合同，也未开放。网络采集的大结果合同同样未完成。macOS Intel、Windows 与用户数据库未实测。
