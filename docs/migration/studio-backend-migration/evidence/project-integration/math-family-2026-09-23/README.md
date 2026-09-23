# 项目任务数学／统计节点族（2026-09-23）

- 项目运行目录新增 31 个已批准的列表运算、数学和统计节点；执行器继续使用从冻结 WebRPA 迁入的 Studio 实现，未增加第二套算法。项目可运行目录由 71 增至 102，Studio 批准范围仍为 213。
- 真实项目 worker 串联执行 31 节点，输出和 31 条成功节点记录持久化；包含求和、幂和中位数断言，不请求浏览器资源。冻结源码差分与项目关联测试共 270 项通过，Ruff、mypy、OpenAPI 一致性通过。
- 正式 Electron 开发入口通过真实鼠标和键盘，在项目 Studio 保存 `list_sum → math_round → math_abs`，关闭工作台后创建项目自动化并运行。三个输出分别为 6、6、7；节点尝试、输出和无 CloakBrowser 残留均已核对：[开发入口结果](../formal-project-math-electron-ImyUUv/result.json)。使用独立临时工作区，未修改用户数据库。
- PyInstaller 冻结后端及 macOS arm64 本地未签名 Electron 目录包构建成功；同一真实 UI 链路在[包内结果](../formal-project-math-electron-dupCiH/result.json)再次通过。包内 `app.asar` SHA-256 `8861a9e54b8f3c583c9bdff1bbf63422d58e16b75b64b4391eb99b0612518190`，`backend/autoflow-backend` SHA-256 `03e5516aef043cc3c88cf335da61a20680c733e7c59287be789272c8b93f6958`，Electron 可执行文件 SHA-256 `afa086d829713c1385c6f15999898a8b959af24abb46df949ac324047afc30a7`。
- 该验收暴露共享前端缺陷：数学节点面板显示默认输出名，但新节点文档没有对应字段；`math_round` 因缺少 `resultVariable` 失败。现在从现有默认变量表在创建节点时写入 31 类输出默认值，显式覆盖仍优先；31 类保存重开专项、前端类型和 lint、renderer/main/preload 构建通过。[失败诊断](../formal-project-math-electron-umISF5/blocked.json)保留。
- 项目资源遵循用户确认的项目默认值＋任务显式覆盖，不增加白名单。`list_export` 仍需项目文本产物持久化和 ACK 边界，未开放。
- 本记录只核销该节点族的开发和 macOS arm64 本地未签名包入口；macOS Intel、Windows 及其他节点族未据此标通过。
- 两份 `result.json` 的 `gitHead` 是测试启动时的父提交 `e6c9bbd9`；本轮改动在工作树内完成后才构建和验收，正式包哈希标识本次实际二进制。未将父提交误报为已包含本轮代码。
- 后续项目实用工具包调整了正式验收脚本的下拉框等待操作；同一新 macOS arm64 包的[数学链路回归](../formal-project-math-electron-1aj0nL/result.json)再次通过。该回归对应的新后端包哈希见[实用工具证据](../utility-family-2026-09-23/README.md)。
