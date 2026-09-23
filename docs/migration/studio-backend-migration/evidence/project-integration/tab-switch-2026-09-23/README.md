# 项目任务标签页切换（2026-09-23）

- 项目可运行目录从 135 增至 136，新增已迁入的冻结 WebRPA `switch_tab.py`，未扩充 Studio 批准范围。原版索引、标题、URL、前后及首末页选择仍由共享执行器完成；项目适配只登记它写出的索引、标题、URL 三个变量。敏感 URL 保留在受控运行上下文，不进入公开任务输出。
- [真实 CloakBrowser 批次测试](../../../../../../apps/backend/tests/integration/test_project_batch_real_cloakbrowser.py)使用独立临时工作区、项目默认 Profile 和两条任务。每条任务打开两个受控页面，按标题切回首个页面、再切到末页，并分别读取元素；六次节点调度、三个切换输出、页面 URL 和实际元素值均验证。全批次八个场景通过，worker、浏览器和资源锁已清理。
- 冻结源码差分与项目事件适配专项 38 项通过；敏感 URL 不进入任务输出。Ruff、mypy、OpenAPI 一致性、PyInstaller 冻结和 Electron 目录打包均通过。
- [正式 Electron 开发入口](../formal-project-tab-switch-electron-qXwVJr/result.json)与 [macOS arm64 本地未签名包](../formal-project-tab-switch-electron-7rNR04/result.json)通过真实鼠标和键盘从项目 Studio 编排、保存、正常关窗，再从项目页启动任务并查看输出。两次均使用真实 CloakBrowser；HTTP 仅用于夹具准备及读取证据，未直接修改 Store。
- 冻结包 SHA-256：`app.asar` 为 `949ec3a3ec6e42e1659ef75587ccea4f3279fcef41e01e9022fc1689b59dc3d9`，后端为 `bd4ef36c952af6ec299b069d12acbbb038caeaf3754b9428bd4f18c1a6ea7f95`，Electron 可执行文件为 `afa086d829713c1385c6f15999898a8b959af24abb46df949ac324047afc30a7`。正式结果中的 `gitHead` 是验收启动时的上一个提交；上述哈希对应实际运行的包。
- Studio Profile 和模型资源继续采用已确认的项目默认值、任务显式覆盖规则，不设白名单。网络采集的大结果仍需项目输出容量合同，不能由本次标签页验收推定已支持。macOS Intel、Windows 和用户数据库未实测。
