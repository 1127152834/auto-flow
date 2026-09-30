# 浏览器配置必选与会话共用验收

日期：2026-09-24。状态：本机功能验收通过，完整回归已执行，完整验收仍有缺口；releaseAccepted=false。

新建“打开网页”节点只提供浏览器配置、代理、内核。浏览器配置必选，不使用项目默认配置自动补齐；代理默认沿用所选配置，不提供工作流代理池/轮换/并发策略。相同配置连续打开网页共用浏览器与登录状态，配置不一致明确拒绝替换。

- 前端完整回归：445 文件、5860 passed；脚本 108 passed；类型、lint、build、OpenAPI 检查通过。
- 后端针对性：最新契约、worker、inspection、coordinator 共 70 passed；修改源文件 mypy 5 文件、全量 Ruff 通过。
- 真实浏览器：Studio 和项目 worker 两种旧/新声明的初始化、Cookie 连续性、End 保存与清理共 5 passed；真实 inspection 新/旧模式 3 项及资源单测 2 项，共 5 passed。
- [实际节点界面](open-page-settings.png)：没有环境来源，只有浏览器配置、代理、内核。截图中的节点名称由验收脚本设置。
- [双节点运行完成](shared-browser-run.png)：隔离 Electron、生产 HTTP、真实 worker；两个相同配置节点运行完成，原模板不变，见 desktop-result.json。
- 错误分支：不同配置、代理、内核不会产生第二次启动；非法 source/proxy JSON 类型经过反例测试后正常拒绝；历史声明继续兼容，不隐式迁移已存文档。

验证使用此前隔离验收目录内真实 145.0.7632.109.2 内核副本。不是签名安装包、OAuth 或 Windows/Intel 实机证据。原 baseline 的完整 mypy/CI/OCR 停止耗时缺口不被本功能通过所替代。完整后端四分片合计 5091 passed / 1 failed / 130 skipped，唯一失败 OCR stop 实测 3.247 秒超过 3 秒原断言。4 项非法 JSON 类型反例在全量收集后添加，另随最新 70 项定向回归通过。全仓库 mypy 65 项 Android 错误保留。当前提交 Windows/Apple Silicon CI 的节点浏览器专项通过；完整 CI 最终步骤见 verification.json。

界面附带发现：完成日志的前端汇总计数显示 1，隔离数据库中 open、again 两个 execution:node-succeeded 均存在，后台汇总明确为 2。会话共用验收依据真实 Cookie 和持久事件；前端汇总计数偏差单独保留待查，不据此声称整个 Studio 显示已无缺陷。

当前代码候选 ada81955 的 [CI](https://github.com/1127152834/auto-flow/actions/runs/35998571394) 已结束：Windows/Apple Silicon 节点专项通过，完整任务分别在 Windows test:scripts、ARM mypy、Intel 依赖安装失败。公开步骤原始结论见 ci-results.json；Windows 失败原因仍缺有效认证日志，不根据同名失败步骤推定根因相同。纯证据收尾使用 [skip ci]，不重复矩阵。
