# 项目任务实用数据工具节点族（2026-09-23）

- 项目目录新增冻结 WebRPA `utility_tools.py` 已批准的 9 个节点：随机密码、URL 编解码、MD5、SHA、时间戳、RGB→HSV、RGB→CMYK、HEX→CMYK、UUID。执行器已迁入 Studio，本批只接入项目任务目录，没有复制算法或增加浏览器依赖。项目可运行入口由 102 增至 111，Studio 批准范围仍为 213。
- 真实项目 worker 在一条九节点流程中持久化全部输出及九次成功尝试，并断言编码、摘要、颜色值、UUID 版本与资源清理。冻结源码差分和项目关联回归 166 项通过；Ruff、mypy、OpenAPI 一致性通过。
- 正式 Electron 开发入口使用真实 UI 编排 URL 编码→MD5→SHA，保存、关窗、建立项目自动化并运行。三个输出和节点记录均核验；未启动 CloakBrowser，使用独立临时工作区且未触碰用户数据库：[开发入口结果](../formal-project-utility-electron-VT9kmk/result.json)。
- PyInstaller 冻结后端和 macOS arm64 本地未签名 Electron 目录包构建成功；[包内结果](../formal-project-utility-electron-XS7rqD/result.json)以同一 UI 链路通过。包内 `app.asar` SHA-256 `8861a9e54b8f3c583c9bdff1bbf63422d58e16b75b64b4391eb99b0612518190`，`backend/autoflow-backend` SHA-256 `aa75a8f66df691b9e55cdab5973912f300fea11a51db0e7eba2a74f609146654`，Electron 可执行文件 SHA-256 `afa086d829713c1385c6f15999898a8b959af24abb46df949ac324047afc30a7`。[数学链路包内回归](../formal-project-math-electron-1aj0nL/result.json)也通过。
- 首次正式脚本把输出名 `sha` 用 Tab 提交，原版变量补全按前缀选中既有的 `sha_hash`；真实摘要正确，脚本改用不与既有变量重名的 `final_sha` 后通过。此为测试输入与既有交互不符，未修改产品行为。
- `list_export` 仍未开放：项目文本产物需要把目标文件发布、快照和 SQLite ACK 的不确定状态安全协调；当前截图专用的清理规则不覆盖该情况。本缺口阻塞 `list_export` 项目任务，不阻塞本族九个纯数据节点。
- 本记录只核销这九个节点的真实 worker、正式开发入口及 macOS arm64 本地未签名包；macOS Intel 和 Windows 尚未据此标通过。两份实用工具 `result.json` 的 `gitHead` 均为测试启动时的父提交 `39074bb7`，本批改动是在工作树内构建并测试，包哈希指向实际二进制。
