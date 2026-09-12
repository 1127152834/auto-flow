# 控件统一首批 T0–T2

- 日期：2026-09-12；状态：confirmed（本批代码和本机 G0），专项未完成。
- 用户授权：“好的 开始吧”；执行范围为前一轮推荐的 T0–T2。
- 使用 Superpowers using-superpowers / executing-plans / test-driven-development / systematic-debugging / verification-before-completion；沿用 using-git-worktrees 隔离；ponytail 仅指导复用，不用原生 select 替代用户要求的自有选项面板。
- 在 codex/ui-controls-plan 合入已提交 a1f3925 → dff8860；没有复制主目录未提交内容。225 个保护源码 hash 与 T0 一致。
- 已实现：tokens.css、controls.css、DEV #/__ui、RHF 本地案例、最小 overlay host / depth。没有 T3+ 领域迁移。
- TDD：tokens 初次 10 红后 10 绿；overlay 缺层级标记时红后绿；展示页初次缺入口时红后绿。真实 Electron 发现 Escape 父层误关和 popup 高度问题，修改并保留回归脚本。不要将动画期间的 toBeVisible 当成 dialog 仍 open。
- 视觉续验：色板暴露未静态引用的 Tailwind token 被裁掉，改 @theme static；运行时断言先复现 success 缺失、只读覆盖 disabled 背景，再修正通过；密度往返32/40纳入检查。
- 最新结果：47 文件/273 测试、令牌10/结构3、typecheck/lint/build 通过；独立 Electron macOS 26.4.1 G0 六组通过；生产 JS 无 DEV lab marker/fixture。
- 报告：docs/design-system/verification/choice-overlay-gate.md，含环境、截图、机器结果和未执行项。
- 下一步：T3 按钮/输入/Field；T4 radio/checkbox/switch；T5 选择 API。G0 probe 不可直接被领域引用；更换 Portal API 后复跑 G0。
- Windows、读屏、真实业务页面视觉与全套状态尚未验收。不把首批完成写成整个专项完成。
