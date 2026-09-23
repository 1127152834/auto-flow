# 项目任务 Firecrawl 三节点（2026-09-24）

- `firecrawl_scrape/map/crawl` 复用冻结 WebRPA@5ccb900e 的 `executors/firecrawl.py`；项目目录 175→178，批准范围仍为 213，尚有 35 个项目目录入口（含画布工具）待核销。
- AutoFlow 必要适配仅涉及项目注册、已有 PNG 产物端口和节点创建默认值；未增加 Firecrawl 云服务或重写爬取算法。真实 CloakBrowser 访问独立本地网页，沿用项目默认 Profile＋任务显式覆盖。
- [首轮正式 UI 失败](../formal-project-firecrawl-electron-6AaqMA/blocked.json)发现 Sitemap 默认值未写入：界面显示“不忽略”，但原执行器缺省值为忽略。新增默认值测试先复现，随后在现有公共默认值模块统一供流程图添加、线性插入和模块条创建使用。只影响新节点，显式 true 可覆盖，旧文档保留原解释；不是修改原版执行器默认行为。
- [开发版正式 UI](../formal-project-firecrawl-electron-B3Ms7l/result.json)通过：项目进入 Studio，真实鼠标/键盘配置三个节点、保存、正常关闭工作台、创建项目自动化、启动任务、进入任务证据页。API 仅用于夹具准备和读取证据；真实浏览器采集正文、Sitemap 链接及两页爬取结果，PNG 魔数和下载 SHA-256 一致，终态无受管浏览器残留。
- 后端原版差分及节点单测 10 项通过（0.77 秒）；项目图执行器、产物与文档桥关联 13 项通过（3.83 秒）。真实 HTTP/SQLite/CloakBrowser 双任务成功通过（23.08 秒）；执行中停止通过；导航中断失败通过（24.21 秒），失败/停止无后续爬取或输出，worker、调度占用和临时目录清理完成，重复启动幂等回执不变。
- 失败用例初稿将 `waitFor` 缺失误当成失败；实际原版是最多等待后继续抓取。保留生产行为，将失败夹具改为真实 HTTP 连接中断，仍断言任务失败、后续任务取消和失败截图；没有放宽终态断言。停止用例仍在等待期间发出停止。
- 前端默认值、序列化往返和目录往返共 231 项通过（2.70 秒）；TypeScript、受影响 ESLint、Ruff、mypy 三个生产文件、OpenAPI 和 renderer/main/preload 构建通过。[macOS arm64 本地未签名目录包](../formal-project-firecrawl-electron-lYcHpJ/result.json)通过同一真实 UI 主链。PyInstaller 本次构建 285.9 秒，包内后端 SHA-256 `b7f63a91e542951fe70b6c27ab2877a4d32b1dfca87b522f872b40c16120b3a9`，app.asar `af2187dbfae93a6ff28bcfacd5f9694ab2ff37d94961b7b872bfdfeab65bd8e3`；证据 gitHead 为本批提交前基线。
- macOS Intel、Windows、用户数据库未实测。真实浏览器证明本机行为，不代表其他平台通过；没有将合同 Mock 或单测替代正式 UI。
- 截图复核新增非阻塞展示缺口：成功任务中的结果 PNG 仍位于“失败时页面截图”标题下；终态页也显示“待清理”，但本批 worker/占用/进程断言已释放。来源为上述开发版 `project-firecrawl-task.png`，影响任务页文案与清理状态展示；不影响结果内容，本批不切换修改共享任务页，列入项目结果/生命周期展示收尾，尚未宣称修复。
