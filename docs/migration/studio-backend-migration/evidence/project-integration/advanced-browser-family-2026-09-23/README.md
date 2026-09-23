# 项目任务高级网页节点族（2026-09-23）

- 项目目录从 124 增至 135：一次接入冻结 WebRPA `advanced_browser.py` 已迁入的 11 个批准节点；Studio 总范围仍为 213。原版动作、默认值与浏览器会话保持不变，新增的是 AutoFlow 项目运行适配。
- 共享项目产物边界登记截图、下载文件和保存图片，沿用现有原子写入、运行代际路径、SQL 确认及不确定 ACK 保留规则。文件和图片上限 64 MiB；下载文件按登记 ID 和哈希读取，项目任务页显示文件名并提供下载，图片可预览。旧 PNG 截图及失败证据继续可读。
- [项目真实 CloakBrowser 批次测试](../../../../../../apps/backend/tests/integration/test_project_batch_real_cloakbrowser.py)在独立临时工作区运行两条任务，每条 13 个节点（打开网页、11 个高级网页节点、页面加载终点）。两条任务的尝试全部成功，下载文本和图片由项目产物 API 读回；项目默认 Profile、worker、浏览器和资源锁清理通过。该测试的历史 6 个场景一起回归，7 项通过。
- 产物元数据、ACK、清理、项目证据、冻结源码差分及项目图相关后端测试 209 项通过；前端项目运行测试 156 项通过。Ruff、mypy、TypeScript、ESLint、OpenAPI 一致性、renderer/main/preload 构建均通过。
- [正式 Electron 开发入口](../formal-project-advanced-browser-electron-VlLhpK/result.json)和 [macOS arm64 本地未签名包](../formal-project-advanced-browser-electron-ZmMx79/result.json)以真实鼠标、键盘从项目 Studio 编排并保存下拉、勾选、保存图片、下载及子元素流程；正常关窗后启动项目自动化。包内实际 CloakBrowser 执行、输出、文件名、哈希、内容读取、图片预览及进程清理通过。HTTP 仅用于夹具准备和读取证据，未直接改 Store。
- 包内 `app.asar` SHA-256：`949ec3a3ec6e42e1659ef75587ccea4f3279fcef41e01e9022fc1689b59dc3d9`；冻结后端：`76ecaf6d60c97c150f78e8c83c8c4d2653d96f7e253b2e61de2cabee324ff4c9`；Electron 可执行文件：`afa086d829713c1385c6f15999898a8b959af24abb46df949ac324047afc30a7`。`result.json.gitHead` 指向验收启动时的上一个提交；上列哈希是本功能块实际复测的包。
- 项目实际文件上传由真实批次测试覆盖，正式窗口样例覆盖图片与下载。macOS Intel、Windows、用户数据库及余下项目节点族仍未验收；不把这些证据算作真实后端全范围完成。
