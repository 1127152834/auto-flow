# 项目任务定时与概率节点族（2026-09-24）

- `scheduled_task`、`probability_trigger` 直接复用已迁入的 `timing_probability.py`（冻结 WebRPA@5ccb900e 的 control/probability 模块）。仅将两个批准入口加入项目执行目录 172→174；时间解析、概率算法、错误结果和分支路由均未重写。Studio 范围仍为 213；项目目录余下 39 个入口，包含画布工具，不能据此宣布整体完成。
- 真实项目文档保存、任务启动及独立 worker 通过：延迟 1 秒、过期日期、0%/100% 两条路径、无效延迟、无效概率、30 秒等待中的取消。每条运行只留下被选中路径的尝试和日志，取消在 3 秒内回收 worker，不申请浏览器资源。该阈值为测试环境实测，不是所有机器的延迟承诺。
- `cd apps/backend && uv run pytest tests/integration/test_project_timing_worker.py tests/differential/workflows/test_b6_timing_probability_parity.py tests/integration/test_project_ssh_worker.py -q`：19 项通过（32.04 秒）；原版差分独立检查默认值、分支和错误。测试首轮因目录未准入而失败，准入后发现测试把 `print_log.logMessage` 写成 `message`；按既有源字段修正测试，保留实际用户日志断言。Ruff、mypy、OpenAPI 和脚本语法通过。
- 正式 Electron [开发入口](../formal-project-timing-electron-fr5ZAP/result.json)：主窗口进入项目 Studio，以真实鼠标和输入配置定时与概率节点、两个日志分支及 sourceHandle 连线，保存、正常关闭、创建项目自动化并启动。过期定时器成功，概率路径一有记录，路径二没有副作用。未调用 Store 或页面内部业务函数。
- [macOS arm64 本地未签名包](../formal-project-timing-electron-1jR13A/result.json)通过相同真实 UI 主链；PyInstaller 构建 173.9 秒并完成目录打包。包内 app.asar SHA-256：`6e7de4e80636aa7bb855a9dcaa19ec0a38708d615ecb278a3cc5fff08eb10127`；后端：`3d7d88836816c3424bdb5618dc4050b7775a9ecd75dd3fe6dd68893efc099eb5`；Electron：`afa086d829713c1385c6f15999898a8b959af24abb46df949ac324047afc30a7`。前端业务未改，复用已通过 renderer 构建；本次正式包重新验证真实入口。证据 gitHead 为本次提交前基线。
- [画布落点遮挡](../formal-project-timing-electron-zBeYDj/blocked.json)和[快速缩放时出现收藏选择器](../formal-project-timing-electron-hvYBT9/blocked.json)保留失败现场。用可见空白位置完成同一编排链，未放宽节点/连线断言。快速缩放现象来源为原生 UI 自动化重复点击，根因尚未核实，列为后续画布交互核查项，不宣称已修复。
- 不修改用户数据库；不调用第三方网站。正常正式窗口链路与 worker 的错误/取消链路分别记账。macOS Intel、Windows、长时间休眠/时钟调整尚未实测。
