# 项目任务等待、断言与停止节点（2026-09-24）

- `wait`、`assert_checkpoint`、`stop_workflow` 复用已迁入的冻结 WebRPA 执行器，进入项目任务目录 154→157。断言输出登记执行器写入的实际布尔变量；停止节点成功结束流程，后继步骤不执行。
- [真实项目 worker](../../../../../../apps/backend/tests/integration/test_project_data_worker.py) 验证固定等待、值断言、停止后继步骤及输出；[真实 CloakBrowser 双任务批次](../../../../../../apps/backend/tests/integration/test_project_batch_real_cloakbrowser.py) 验证元素等待、页面元素断言、项目默认 Profile、终态和资源清理。冻结源码差分、项目启动与关联回归共 100 项通过；真实浏览器专项 1 项通过。Ruff、mypy、OpenAPI、目录和脚本语法检查通过。
- 正式 Electron [开发入口](../formal-project-control-primitives-electron-SWpqmd/result.json)与[本地未签名 macOS arm64 包](../formal-project-control-primitives-electron-4MSFrA/result.json)均经主窗口真实点击进入 Studio，配置四节点、保存、正常关窗并运行项目任务；任务页显示 `checked=true`，停止后的 `must_not_run` 未出现，无浏览器残留。首次 UI 脚本以模糊“等待”选中了“等待页面加载完成”，保留[失败现场](../formal-project-control-primitives-electron-7z6dO1/blocked.json)；改用原有“固定等待”入口后复验通过。
- 包内 `app.asar` SHA-256：`14f031e677a83b8dc3041589fce3445fe0b9ba7f0d72919c537700eb512ccbbd`；冻结后端：`018ddb6428dd6b64930668a7ed7769e63b161b62984d1cfafac4410013cb766c`；Electron：`afa086d829713c1385c6f15999898a8b959af24abb46df949ac324047afc30a7`。Studio 批准范围 213 不变，项目目录余下 56 个节点。macOS Intel、Windows 和用户数据库未实测。
