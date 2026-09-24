# 节点浏览器环境实施

- 日期：2026-09-24；状态：implemented，完整发布验收未通过；以下逐片记录按时间保留，最新结论见末尾。
- 来源：用户已批准 15088ecb 的书面规格并明确开始实施；分支 codex/node-browser-environments。
- 计划：docs/superpowers/plans/2026-09-24-node-browser-environments.md；对应 .superpowers/sdd ledger 保存测试日志与步骤。
- 切片 1 已接入：可空持久身份列及单一迁移 head；实例保存/恢复实际 Profile 快照、seed、内核；任务及维护恢复不再采用后来模板值。已有环境不应用项目默认代理；占用和内容/身份代次竞争受同一事务守卫。
- 身份候选从宿主数据库写入，忽略浏览器提供的同名文件；发布元数据摘要检查覆盖身份内容。旧记录不伪造身份，启动明确拒绝；不把该变化称为旧记录自动迁移完成。
- RED：任务恢复 seed 999 而非 42、缺身份未拒绝、维护漂移、候选篡改未拒绝、预检读取后来模板、旧代次预约未拒绝均已复现后修复。
- 当前针对性回归：155 passed / 2 skipped / 1 Starlette 依赖警告，43.62 秒。两项真实浏览器测试缺 AUTOFLOW_TEST_CLOAKBROWSER，尚未执行；不是实机验收通过。变更文件 Ruff 通过，14 个变更源文件 mypy --follow-imports=silent 通过。
- 全量 mypy 首查有 66 处错误：本轮 retention 联合异常类型 1 处已修复，其余报告在并入的 Android 相关路径；最终全量复查仍待完成，不声称全仓库类型检查通过。
- 未完成：实例代理/内核编辑和维护启动代理/授权接入、项目设置表单与布局、节点延迟启动、Studio 顶部入口切换、兼容迁移、真实联合回归和三平台验证。releaseAccepted 保持 false。
- 本轮未修改主目录、用户项目数据，未推送、合并或发布。

## 切片 2（2026-09-24）

- confirmed：实例代理 PATCH、内容代次/元数据修订、占用与项目状态检查已接入。生成新副本并保留旧代次 Cookie；未知结果持久化原命令，恢复文件发布后数据库提交中断，不会重复创建代次。
- confirmed：维护启动从实例快照获取资源锁、授权与代理，凭据留在本地中继；确认关闭后才释放锁。前端详情显示实例设置，旧缺失身份不可维护打开；代理编辑接入真实目录和保存 API。
- 能力边界：缺少内核配置目录迁移兼容性证据，严格拒绝不同 edition/version 的已有登录态迁移；原内核缺失要求重新安装。新建实例内核选择在切片 4/5 实现，不能把该守卫说成任意跨内核迁移已支持。
- 验证：后端 58 passed / 2 skipped / 1 依赖警告；前端环境域 27 passed（含响应丢失后卸载/重新打开仍重放同一代理、版本和 key）；5 个相关后端源文件 mypy、前端 typecheck、OpenAPI 检查通过。真实浏览器集成两项仍跳过，未称实机通过。
- 未完成：项目默认设置/去除右侧卡片、节点延迟启动、Studio 入口/兼容迁移、最终全量回归及独立审查。releaseAccepted=false。

## 切片 3（2026-09-24）

- confirmed：环境页删除右侧两张概览卡片，主内容改为单列。新建环境默认设置可选真实模板及模板代理/无代理/固定代理/代理池，沿用 Project PATCH 与原命令恢复；保持 modelProviderId，保存带原管理修订，目录刷新不覆盖草稿。
- 验证：环境域和项目 API 合计 39 项前端测试通过；项目资源解析 13 项测试通过（已有环境不采用项目默认代理）；前端 typecheck 和环境域 ESLint 通过。
- 切片 2 的新增测试最初含无效 Testing Library exact 选项，已去掉并重新通过 typecheck，提交为 01171e27；不影响产品逻辑。
- 后续主任务仍为节点契约/延迟启动、Studio 控件切换与兼容迁移；当前不是完整交付。

## 切片 4（2026-09-24，运行链已接通，最终联合验收待切片 5）

- confirmed：版本 1 节点契约、引用校验和准备时资源冻结；项目任务与 Studio 共享冻结器、OpenPageExecutor 和 Runtime。新模式不再要求全局 Profile，真正执行初始化节点时才经宿主通道取得资源并启动。原节点命令重放复用实例；第二次初始化、失效执行代次、未授权目录字段拒绝。后续 current 节点复用实例，分支未进入零启动。
- confirmed：PM 宿主以 Run/代次/节点访问命令身份预约唯一工作实例；输入关联来源在领取事务冻结。延迟资源纳入原所有权、停止及 End 保存链。Studio 用现有 worker 私有目录保存临时工作副本，退出确认后释放 lease；固定环境预览校验项目/代次/身份/占用后复制，不反写源环境、不自动保存。数据输入关联仍需项目 Task，独立 Studio 调试提示选择固定环境。
- confirmed：Studio 原初始化响应丢失重发、启动期间停止不返回可启动资源且清理确认前保留锁；固定来源复制后改预览 Cookie 不影响源，旧代次拒绝。已保存实例跨内核迁移仍按切片 2 限制。
- 验证：项目定向回归 163 passed；Studio/worker/契约回归 111 passed / 3 skipped；新增取消和响应丢失后 coordinator 8 passed；固定来源复制 1 passed。真实已安装 CloakBrowser 三项通过（10.09 秒）：宿主单实例重放、PM 登录→current 读登录态→End 保存身份、Studio 无全局 Profile→登录态连续→确认清理。相关 28 源文件 mypy 通过，Ruff 修正导入后通过，OpenAPI 已生成。原生测试使用临时 SQLite/目录和本地 HTTP，未操作用户项目 q。
- 验证过程保留：Studio 新测试最初夹具 migrate_database 参数错误、事件属性 kind/type 错误均已修正；生产首次缺 pending browser future 与动态内核清理已修复。完整后端 mypy 的既存 Android 诊断未在本切片修复。
- 未完成：Studio 节点控件、显式迁移、录制/拾取配置联动、自动化资源页、全量回归、真实代理/界面联合场景、三平台和整分支独立审查。并行共享浏览器仍明确拒绝；不宣称完整 PM9 验收。releaseAccepted=false。

## Task 5 — 节点界面与入口（2026-09-24，implemented / final acceptance pending）

- 打开网页节点使用真实模板、代理、已安装内核和项目环境目录；环境来源显式配置。顶部浏览器选择器删除，运行、录制和拾取不得回退旧全局值。
- 旧文档保持原版本；明确选择迁移入口后写新版标记，其他导航使用 current。导入导出、历史撤销、AI 回滚和自定义模块备份保留版本；跨版本浏览器节点合并拒绝，避免隐式迁移。远程协作在当前产品中已禁用，不扩展其协议。
- 录制／拾取沿用真实 worker、资源授权和私有工作目录；固定环境复制冻结内容，启动重试复用原会话配置。自动化的新模式资源表单保留模型配置，浏览器由节点维护。
- 验证：新增组件与模块/草稿保护 77 passed；旧入口协议适配后 116 passed；真实 inspection worker 两种模式 2 passed；HTTP/inspection 29 passed。typecheck、lint、build 通过。完整回归和隔离 Electron 正在执行，结果尚未声明通过。
- CI 新增三平台节点初始化真实 worker 检查，内核版本与平台实际安装版本一致。未改 releaseAccepted，不合并发布。

## 最终本地验收（2026-09-24，confirmed）

- 前述“未完成”切片内容均由后续切片及本节取代，不再代表当前实现状态。代码完成节点资源入口、独立实例、实例设置、项目默认值和界面调整。
- 真实隔离 Electron＋sidecar＋worker：项目默认模板通过界面保存回读，节点模板/代理/内核保存回读，UI Run completed，模板不被修改。截图、机器结果与范围见 docs/qa/node-browser-environments/2026-09-24/。
- 全量前端 445 文件 / 5859 passed；scripts 108 passed；typecheck、lint、build、OpenAPI、Ruff 通过；45 个变更后端文件 scoped mypy 通过。
- 完整后端按四组执行共 5213：初次 5083 passed / 3 failed / 127 skipped。两处预约测试仍提供旧的不完整资源快照，已改用真实 freeze，整个文件重跑 16 passed；剩余 OCR stop 耗时失败约 3.3 秒，干净 baseline 15088ecb 复验约 3.27 秒同样失败。未改变 3 秒断言。
- 全仓库 mypy 65 项 Android 错误，在干净 15088ecb 也复现 65 项；这是既有 baseline 问题，未修改主目录 Android/Studio 工作。
- 独立审查 2 项 P2 均修复并反例验证：失败截图使用当前 context.browser；AI 装载传递版本。桌面发现的 Studio/维护目录误用 Task 校验也已修复；项目任务权限校验未削弱。
- 架构边界保留：跨内核实例迁移须兼容性证据，旧缺失身份不猜测恢复，子流程首次初始化未开放，禁用远程协作不扩展，模板原引用可用性仍检查。
- 三平台 CI 将在候选分支验证；完整门禁预计仍受上述既有类型错误阻断。OAuth、签名、Windows/Intel 实机不由本轮源码验收替代，releaseAccepted=false。
- 远端 codex/architecture-baseline 仍为 c6e02427，本地 baseline 已是 1bc6b24d；本分支继承已在本地完成的合并历史。只推送功能分支，不擅自推送或改写共享 baseline；草稿 PR 须注明本轮实现审查范围从 15088ecb 开始。

- 最终真实浏览器链：节点初始化及持久登录态保存恢复 5 passed（17.58 秒），覆盖直接保存与 End 保存。
