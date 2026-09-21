# PM9 follow-through

日期：2026-09-21。状态：in_progress。来源：用户后续任务、当前独立 PM9 工作区与可执行验证。

- 分支 codex/project-management-pm9-runtime，起点 30c4a768，PR #1 草稿；未触碰 Studio 主工作区、未重新归并历史分支。
- 完成 251 条 assertion/gap 映射，保留 73 条原预定缺失路径的历史意图。原 verified 条目发现未闭合条件的回退为 partial，记录旧状态；未批量升级。
- 真实 worker 竞争测试复现：继续 intent 在空读取之后提交，随后 TTL 判断仍返回 expired，Run 错判 timed_out。RED：1 failed / 1 passed。修复为到期先 CAS 相同检查点状态版本；输方重读已提交继续命令。GREEN：9 个实际浏览器人工/丢响应场景通过。
- 写成功响应丢失在 parent→worker delivery 边界注入，Run 安全中断；HTTP 按原 commandId 取回唯一新增记录和成功操作结果。不宣称跨进程恢复网页执行。
- 生产 HTTP smoke 扩展双输入、重复领取、两次连续写入、人工新值冲突和后续浏览器失败保留效果；End 混合关联、saved_unlinked 修复及旧代次保护继续验证中。
- 新增架构方案 docs/superpowers/specs/2026-09-21-pm9-runtime-capability-completion.md 为 proposed；已请求一次确认，未获答复前不实现新协议，继续独立验证修复。
- 本次已有生产代码变更，旧 d59607f3 三平台结果只能作历史基线；新候选必须独立验证，releaseAccepted 保持 false。

更新（confirmed）：独立审查发现 current 读取后才接受 intent 的另一交错；新增真实 worker RED 后通过 intent 后重读/CAS 失配重读修复。End 真实链发现通用 ProjectOperationView 不容纳环境操作导致 500，复用受限 kind 的 EnvironmentOperationSnapshot 修复列表/id/原键，生成 API 已同步。最终本机 16 real browser / 33 定向 / 100 scripts，ruff/mypy/lint/OpenAPI 通过；此处原 typecheck 通过记录已 superseded，实际旧本机日志与 f25b3867 CI 均失败，见后续校正；全量后端在最后契约小改前 3214 passed25skipped，新候选全量由 CI 重验。报告 follow-through.json 保存 source hashes 与注入边界。独立审查 P1/P2 全关闭。当前 203 项有断言、48 项缺直接场景、186 partial65planned0verified。

补充：TTL 先胜的实际 HTTP 在途继续竞争 1 passed，增加非 waiting 分支让出事件循环，最终受影响人工 5 passed。新候选仍待三平台全量，不将此前本机全量冒充最后源树逐行验证。

后续根因修复（confirmed）：补全 XE-A10 实际 worker + 发布边界 ENOSPC，复现关闭候选仍 saving/占用导致 T2 无法开始。修复明确失败转 retained_unsaved、不占现场额度，恢复更新原子重获占用和代次检查；保存/End 复用既有实例 RLock，释放按 environment_id+instance_id 条件删除，未知发布保持占用，旧成功重放不得释放新未决保存。真实旧候选链 passed；30 契约/规则/存储及 8 前端定向通过。清理提示 DTO 类型遗漏已修复并重新类型检查。三平台旧候选失败真实保留，不沿用历史成功。

规划补齐（proposed）：新增能力文件级计划已补在 docs/superpowers/plans/2026-09-21-pm9-runtime-capabilities.md。复核现有 gateway 后，S1 明确优先复用冻结 document 的 canvas 子图和既有 32 层深度限制，不额外复制依赖文档，不扩大外部工作流节点目录。仍等待原新增架构确认，未实施。

本机安装补证（confirmed）：52936b6a ARM CI 全通过且原始 5 报告已保存。该 DMG 本机完整性校验/只读挂载/隔离复制/实际启动与 sidecar 父退出通过，原有应用及资料未触碰。Intel 第一轮仅代理页面初始 findByText 1 秒等待失败（5454 通过）；该文件本机 14 通过。暂只推测调度预算，未声称修复，保留失败日志并等整轮结束后单独重跑失败平台。

新增方案复审（confirmed）：补齐 scheduler 消费子流程输入输出/人工目标的入口与仅选后继断言；并行人工在发 capability 前排队、建项后才起人工 TTL、自动预算仅在持久 waiting_manual 暂停。复审无阻塞发现，规格仍 proposed。补核 DATA-E2E-06/XE-A23 现有直接 capability 断言，明确隔离集成与真实组合的差别，将 Sheets 外部授权缺口单列；未提升验收状态。

原生 ARM UI 补证（confirmed）：使用当前 DMG 安装副本与独立 user-data-dir，经 Computer Use 实际操作 macOS open-panel/save-panel，导入并导出一条自生成 Excel 记录；UI 与 openpyxl 读回确认文本 001/中文，源文件 hash 不变，无 QA dialog override。仅关闭这一原生文件路径子条件，未证明 Google 配置面板、凭据、Gatekeeper 或其他平台实机。

映射收尾（confirmed）：DATA-VER-01 补引用本轮实际 worker 人工竞争中原始 inputSnapshot 值/版本保持的断言；界面时间/版本展示仍为 gap。当前为 204 条有断言/47 条无直接场景，状态仍 186 partial/65 planned/0 verified。

组合补测（confirmed）：同一 52936b6a ARM 包真实 HTTP/worker 首次并发场景中旧人工任务到期后第二任务才完成，未通过并发验收；可复现第二参数批次 blocked/Task queued。脚本修正“无 Task”的错误预期，顺序继续后验证持久 ensureField、第二表精确新增一条、查询/更新和显式状态，清理通过。DATA-E2E-06 仅据此变 partial，FLOW-A02 仍 planned；总计 187 partial/64 planned/0 verified。单 owner/worker 与资源锁是新实现缺口，新增多 Run 设计/文件级切片独立请求确认，未实施。Windows 全 CI 通过（3183/63 后端、5455 前端、7 实际 worker 故障）；Intel 同 SHA attempt 2 已接受。新增手工验收脚本不是 52936b6a CI 的测试内容，另存脚本 hash 与本机报告，不重复触发无关三平台流水线。

补充复审（confirmed）：新手工验收脚本无剩余实质发现；S5 方案修正参数批次 maxTasks 连续创建语义，保持单批次同时最多一个活动实例；明确历史现场核验未完成时全局准入继续关闭。两项仅设计澄清，仍未获实施批准。

2026-09-21 最新校正（confirmed，来源 input-environment-follow-through.json）：XE-A23 真实包链暴露输入环境启动仍要求默认 Profile，修复为实际领取事务冻结所选环境 Profile、忽略无关默认配置、解析失败不创建 Task/lease。54 定向、ruff/mypy/OpenAPI、100 脚本、PyInstaller 和完整真实人员/邮箱/账号恢复链通过，独立复审无 P1/P2。人员预先关联另一环境且全程关联/数据版本不变；邮箱原筛选不再创建 Task，新账号仅一条。当前 204 有断言/47 无直接场景，188 partial/63 planned/0 verified。新增生产改动需要新三平台矩阵；52936b6a Windows/ARM 成功保留，Intel attempt 2 因新候选取消。S1–S5 架构仍待确认，releaseAccepted=false。
