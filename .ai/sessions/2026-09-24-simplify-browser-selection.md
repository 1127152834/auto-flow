# 简化打开网页的浏览器选择

- 日期：2026-09-24；状态：implemented，完整验收仍有已记录缺口。
- 来源：用户要求浏览器配置必须明确指定，移除来源选项；确认相同配置“共用”。分支 codex/simplify-browser-selection，基于已合并 baseline 7401e46d；主目录未修改。
- UI 只提供必选浏览器配置、沿用配置/无代理/指定代理、沿用配置/已安装内核；不提供节点代理池、环境来源、项目默认配置回填。
- 新声明 source=profile 由原节点契约校验并冻结；Studio 与项目 worker 使用同一比较规则复用相同配置的活动会话。宿主首次初始化、原命令恢复、占用与取消清理不改；配置不同拒绝替换。
- 兼容：历史 newFromProfile/current/fixedEnvironment/inputEnvironment 不隐式迁移，仅保留读取和原语义运行。新建节点只用 profile，旧节点通过明确选择配置改为新语义。
- RED 已观察：前端 3 项（默认来源、配置入口、必选约束）；后端新契约拒绝；真实 Studio/PM 第二节点均失败；受控 worker 共用场景失败。修复后相关后端 51 passed，真实录制/拾取及其资源边界 5 passed，组件 9 passed。
- 隔离 Electron 通过：实际 UI 保存 profile/代理/内核，两个相同配置节点运行完成，模板未变。未重启用户应用或修改用户项目。真实内核来自此前隔离验收工作区的 145.0.7632.109.2 副本；ensure_binary 调用返回了本机不同版本，未使用该返回值作为指定版本证据。
- 最终完整回归、提交与远端结果待追加。既有 CI/签名/OAuth/实机缺口不因本修正消失，releaseAccepted=false。

- 后续复查：非法 source/proxy.mode 的数组/对象曾抛 TypeError，4 项 RED 后修复为正常 WorkflowError；最新契约/worker/inspection/coordinator 70 passed，全量 Ruff 和 5 个变更源文件 mypy 通过。前端完整 5860 passed/445 文件，scripts 108、类型/lint/build/OpenAPI 通过。完整后端首个串行执行为缩短耗时在约 2% 主动中断（保留退出 traceback），改为按文件 SHA256 分桶的四个互斥 pytest 分片；不把中断运行计为通过。

## 最终回归（2026-09-24，confirmed）

- 四个按文件互斥分片覆盖收集的 5222 项：5091 passed / 1 failed / 130 skipped，唯一失败仍为 OCR stop 3.247 秒 > 3 秒。后补 4 项非法 JSON 类型测试随最新 70 项定向回归通过，未混入全量计数。全量 mypy 65 项 Android 相关错误保留。
- 实现候选 ada81955 已推送，草稿 PR #3：https://github.com/1127152834/auto-flow/pull/3；当前 CI：https://github.com/1127152834/auto-flow/actions/runs/35998571394。Windows 与 Apple Silicon 节点浏览器专项通过；Intel 安装阻断未进入专项。
- 桌面截图附带发现汇总显示执行 1 节点；隔离数据库确认 open、again 均成功且后台汇总为 2，前端计数偏差单独保留待查，不改变真实 Cookie/会话共用结论。证据保存到 docs/qa/simplify-browser-selection/2026-09-24/。

- 当前候选 CI 已全部结束：Windows/Apple Silicon 节点专项通过；完整任务 Windows test:scripts、ARM mypy、Intel 安装失败，公开证据见 ci-results.json。Windows 具体错误仍需可用日志授权，不能仅凭步骤同名断言根因。仅更新证据时使用 [skip ci]；未合并或发布，也未强制重启用户应用。

## 用户授权合并（2026-09-24，confirmed）

- 用户获知上述实现和验收结果后明确要求“合并”。将 PR #3 来源 codex/simplify-browser-selection@8d93438e 合入 codex/architecture-baseline，目标原为 7401e46d，本地与远端一致。
- 普通 --no-ff 合并无冲突；追加本记录前，合并索引与来源 tree 完全一致；diff --check 通过。本次只增加合并记录，生产代码和测试内容保持已验证候选，不重复执行完整回归。
- 此节取代上文“未合并”的阶段状态；远端落点以 Git 与 PR 合并状态为准。保留来源分支，不修改主目录或其他工作区，不发布或重启应用。既有 CI、OCR 耗时、界面汇总计数与外部验收缺口保留，releaseAccepted=false。
