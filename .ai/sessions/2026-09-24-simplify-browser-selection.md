# 简化打开网页的浏览器选择

- 日期：2026-09-24；状态：implemented，回归验证进行中。
- 来源：用户要求浏览器配置必须明确指定，移除来源选项；确认相同配置“共用”。分支 codex/simplify-browser-selection，基于已合并 baseline 7401e46d；主目录未修改。
- UI 只提供必选浏览器配置、沿用配置/无代理/指定代理、沿用配置/已安装内核；不提供节点代理池、环境来源、项目默认配置回填。
- 新声明 source=profile 由原节点契约校验并冻结；Studio 与项目 worker 使用同一比较规则复用相同配置的活动会话。宿主首次初始化、原命令恢复、占用与取消清理不改；配置不同拒绝替换。
- 兼容：历史 newFromProfile/current/fixedEnvironment/inputEnvironment 不隐式迁移，仅保留读取和原语义运行。新建节点只用 profile，旧节点通过明确选择配置改为新语义。
- RED 已观察：前端 3 项（默认来源、配置入口、必选约束）；后端新契约拒绝；真实 Studio/PM 第二节点均失败；受控 worker 共用场景失败。修复后相关后端 51 passed，真实录制/拾取及其资源边界 5 passed，组件 9 passed。
- 隔离 Electron 通过：实际 UI 保存 profile/代理/内核，两个相同配置节点运行完成，模板未变。未重启用户应用或修改用户项目。真实内核来自此前隔离验收工作区的 145.0.7632.109.2 副本；ensure_binary 调用返回了本机不同版本，未使用该返回值作为指定版本证据。
- 最终完整回归、提交与远端结果待追加。既有 CI/签名/OAuth/实机缺口不因本修正消失，releaseAccepted=false。

- 后续复查：非法 source/proxy.mode 的数组/对象曾抛 TypeError，4 项 RED 后修复为正常 WorkflowError；最新契约/worker/inspection/coordinator 70 passed，全量 Ruff 和 5 个变更源文件 mypy 通过。前端完整 5860 passed/445 文件，scripts 108、类型/lint/build/OpenAPI 通过。完整后端首个串行执行为缩短耗时在约 2% 主动中断（保留退出 traceback），改为按文件 SHA256 分桶的四个互斥 pytest 分片；不把中断运行计为通过。
