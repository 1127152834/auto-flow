# PM9 正式 Studio 必填规则接口

- 日期：2026-09-23
- 状态：confirmed 定向 HTTP 与正式 ARM 窗口子范围；完整候选验收以专项 JSON 为准
- 范围：已有只读协议的生产装配缺陷；不是 W1–W3 会话/停靠新架构，也不扩大节点执行准入

原正式 Studio 请求 `/api/system/module-required-fields` 返回 404；同协议 DTO、冻结 AST 提取器和前端消费早已存在，仅开发 Mock 提供响应。新增正式路由，复用现有 DTO/实例认证/错误处理，注册在正式 bootstrap 和 OpenAPI 共用的工作流路由装配函数。提取器同步生成后端静态资源；PyInstaller 显式携带该资源，运行时不读取 reference 或开发目录。

来源为已授权 `reference/WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb` 的 `backend/app/services/ai_assistant_module_schemas.py`，SHA256 与覆盖名单见 `docs/migration/studio-frontend-completion/required-field-source-coverage.json`。227 个保留来源节点中覆盖 69、未覆盖 158，三个项目专用节点没有来自此来源的规则。不能按目录名生成规则或把未覆盖解释为无需字段。

验证：正式 HTTP 新增断言首先得到 404（1 failed/14 passed），修复后 17 passed；包括错误实例凭据 401、缺失/损坏资源 500。测试阶段最初误重复启动同一 fixture 应用 lifespan 导致跨 event-loop shutdown 错误，改用无二次 lifespan 的只读请求后通过；不是产品回归。前端现有规则消费 45 passed/3 files，101 scripts、4 coverage 检查、Ruff/mypy 408、typecheck/lint/OpenAPI 通过。生产 ARM 包空网址提示与项目节点未覆盖提示已由实际窗口和截图证明。

更完整的运行时间、资源哈希、全量结果、CI SHA 及局限记录在 `docs/project-management/implementation/pm9/studio-metadata-follow-through.json`。界面仍可见图像资源/全局快捷键 404 及未实现辅助命令 501；不把本片扩写为完整 Studio 或发行验收。W/AD/FR/L/M 附录和外部条件保持原状态，releaseAccepted=false。

2026-09-24 验收脚本诊断（confirmed）：两次完整 ARM smoke 在已通过真实 worker 链后，卡于两帧测量。补错误上下文后实际记录 `visibility=hidden, focused=true`，属于原测量没有要求原生窗口可见而等待后台 requestAnimationFrame。脚本在同一测量前调用 `Page.bringToFront` 并断言可见，原 5 秒响应阈值、请求超时与万行规模不变。两份负向报告单独保留；修正后完整结果见专项 JSON，不把早期失败改成成功。

最终本机：完整后端3486 passed/78 skipped/1010.08秒；完整ARM桌面通过，前置显示后的两帧5ms。实际10000行五路单条写入76475ms/0busy，1004真实worker日志37234ms；固定1000条合成输入60038ms/最大滞后92ms，分别记录。原始报告和21张成功截图保留于 `.tmp-tests/pm9-studio-metadata-2026-09-23/`，两次负向报告在其negative目录。前端app.asar与632caf6d逐字节哈希相同，复用其5473全量结果并重跑45定向及生成类型检查。

最终生产候选 `69baeeb2` 已推送；三平台 Actions 35886627514 指向该 SHA，三个原生job均in_progress。旧632caf6d矩阵35881272086不含本片，已确认cancelled；误在push完成前触发的35886555555已核对为旧3fb223a3并取消，未计入通过。
