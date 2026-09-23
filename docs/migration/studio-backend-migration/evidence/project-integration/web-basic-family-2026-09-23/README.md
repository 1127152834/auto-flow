# 项目任务基础网页节点族（2026-09-23）

- 项目可运行目录由 111 增至 122：接入已迁入的 WebRPA `basic.py` 十一种批准节点（`use_opened_page`、`close_page`、`refresh_page`、`go_back`、`go_forward`、`switch_iframe`、`switch_to_main`、`hover_element`、`handle_dialog`、`inject_javascript`、`wait_element`）。没有复制执行器或扩大 Studio 的 213 节点范围；仅使用主应用 CloakBrowser Profile。
- 原版字段 `saveResult`、`saveMessage` 的运行变量通过现有项目事件适配写入输出。原有 `resultVariable`／`variableName` 的输出格式不变；敏感变量不写入项目输出。先出现真实项目批次准入失败，接入后两次真实任务均完成十五节点链，脚本返回页面标题、弹窗消息、iframe 切换和导航历史均正确，节点尝试、输出、停止后的 worker 与资源清理通过。
- 项目默认 Profile 在新场景中由项目配置提供，任务不指定 `profileId`；原有四个批次场景继续以任务显式指定 Profile 通过。项目默认值＋任务显式覆盖符合既有规则，无资源白名单。
- 后端关联回归 274 项、真实 CloakBrowser 项目批次 5 项、敏感输出专项 2 项通过；Ruff、mypy、OpenAPI、renderer/main/preload 构建通过。旧校验用例中 `wait_element` 已变为真实可运行，禁用案例改用仍被项目文本产物边界阻塞的 `list_export`，保留“可保存但不可启动”的断言。
- 正式 Electron [开发入口](../formal-project-web-basic-electron-JbT9CK/result.json)与 [macOS arm64 本地未签名包](../formal-project-web-basic-electron-4q7AGy/result.json)均以真实鼠标/键盘完成项目 Studio 编排、保存、原生关窗、创建自动化、使用项目默认 Profile 启动 CloakBrowser、执行网页动作、查看任务输出并确认进程清理。正式界面链选取打开网页、使用已打开网页、等待元素、悬停元素、提取数据；十一类完整链由真实项目批次集成测试覆盖，不将五节点界面样例冒充十一类均已逐一界面编排。首次包内通过后增加字段类型保护，已重新冻结并以同一主链复验；最终包以本链接为准。
- 当前包的 `app.asar` SHA-256 为 `8861a9e54b8f3c583c9bdff1bbf63422d58e16b75b64b4391eb99b0612518190`，冻结后端为 `0d470cd8167f53fe0953b60d3198575f6e640925d6936037dc952338e947a95e`，Electron 可执行文件为 `afa086d829713c1385c6f15999898a8b959af24abb46df949ac324047afc30a7`。两个 `result.json.gitHead` 是验收启动时的父提交，实际改动为本次工作树构建。
- 未核销：macOS Intel、Windows、用户真实数据库和其余未接入的项目节点族。`list_export` 的项目文本产物安全发布仍是独立阻塞项。
