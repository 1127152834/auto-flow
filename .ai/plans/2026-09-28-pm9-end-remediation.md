# PM9 End 修复实施切片

日期：2026-09-28；状态：in_progress。授权来源：用户本次修复任务及 `.ai/decisions/2026-09-20-pm9-production-runtime-approved.md`，规格 `docs/superpowers/specs/2026-09-20-pm9-production-runtime-integration.md`。

## Global Constraints

- 保留项目现有批次/Task/Run 持久模型、operation 幂等、调度器、资源租约、代次撤权和事件表。使用既有 WorkflowRuntime 和生产项目 worker，不新建执行器、数据库访问层或资源管理框架。
- End 等待 worker 确认浏览器关闭后，父进程复用 environments/retention.py::end_task 完成保存、关联与结果核验；只有确定成功后才能推进 Run 终态。资源占用保持至最终化完成或明确失败处置。
- 未到达 End 的失败/取消不得新增保留意图；未知结果按原操作查询，不重跑网页、不重发已确认动作、不清除unknown/cleanup_failed。旧代次不能继续数据写入或发布环境。
- 能力来自固定冻结节点、当前项目Task/Run/代次、已持久ACK的nodeVisit。worker无SQLite、任意宿主路径或renderer令牌；跨项目与工作区拒绝。
- 正式项目记录归项目数据用例；运行内存表仍归ExecutionContext，不能把table_add_row改成项目写入。
- 保留所有其他任务未提交内容。只显式暂存本任务文件，不push、不发布、不改历史审计/历史迁移/AOCI资产。AOCI另一个任务初始化中，不能接管。
- 新增逻辑保留旧行为失败/修复后通过的回归；真实成功必须真实SQLite/生产worker/CloakBrowser，不使用外部成功替身。
- 人工跨应用重启续接仍有一个待裁定的语义差异；本切片只做End，不偷改普通暂停/重启interrupted语义。

## Task 1: 生产 End 纵向闭环

实现已批准R3中的End部分，并验证真实登录环境保存与复用。

1. 读取既有运行器、项目worker私有能力协议、project_data授权、环境保留账本和项目记录关联。以 `docs/project-management/design/execution-and-environment.md` End规则为产品契约：固定endOperation身份、原定业务结果、保存目标/来源代次、RecordRef/expectedLinkRevision/替换授权；默认输入与新增/已写输出可显式选择，查询结果不自动取得写权。不要仅调用管理API来冒充生产节点。
2. 在既有Studio中补一个明确的项目End节点及必要配置/预检，或者复用已经具有End语义的入口（先核实；普通stop_workflow的主动停止语义不能悄悄改成End）。无项目能力明确拒绝，不开放未实现配置。节点/宿主协议固定、有界、校验冻结内容与实际nodeVisit；动态目标必须基于当前Task有效写权/占用、同项目身份及版本。复用现有能力事务/持久事实，不新增并行数据库框架。
3. 持久登记End意图，结束Runtime并确认真实浏览器及worker清理，再在父进程复用EnvironmentService.end；此期间租约不释放，取消/强停/重启有一致的唯一控制权。同步环境IO若经to_thread必须shield并排空，不能协程已取消而后台仍保存；最终发布/关联也必须复验代次/所有权。已有操作账本可复用，不用内存flag冒充恢复。并发End有唯一赢家。
4. 保存与关联完全确认才进入成功终态。saved_unlinked/明确失败保持失败事实与可恢复环境；未知保持核验责任。应用重启发生在End已部分提交时按原账本恢复核验，旧运行一旦终态不得复活。UI读取持久事实，展示完整错误与部分保留状态。
5. API/模型/生成类型变更按现有生成器。尽可能最小修改，不无关重构；新增兼容迁移仅在确有必要时，历史数据和迁移不改写。
6. 有效回归覆盖正常End/不保留/重复命令/丢回执/记录关联版本冲突/非法作用域/旧执行代次/取消与强停竞争/浏览器关闭未知/重启核验。真实正向用专属工作区SQLite、真实本地登录HTTP站、生产worker与已安装CloakBrowser：领取→网页真实会话→正式项目创建或写回并推进状态→End保存关联→另一运行复用登录；不可通过预填cookie或直接改行伪造结果。
7. 对相关切片做测试、Ruff、mypy、前端test/type/lint、构建/迁移/生成检查。完整仓库回归由主控最终统一运行，避免重复十八分钟全量；不能跳过相关失败。真实kernel路径为 `/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2/Chromium.app/Contents/MacOS/Chromium`。仅使用专属临时资源。对本任务源码及证据显式暂存、独立提交。
8. 报告最小实现、精确命令/结果、红绿证据、实际运行身份/文件、限制及提交；不能将本切片标为持久人工恢复或PM9全部完成。

## Task 2: 人工持久恢复（等待用户语义裁定，不派发）

差异方案见 `docs/qa/2026-09-28-remediation/pm9-r3-implementation.md`。等待此前一次问题的回答，不再重复询问。End切片不依赖此决定；其完成并审查后，再按裁定建立人工恢复的具体实施任务。

## Task 3: 项目交互连接恢复反馈

此为原生回归新发现的有界诊断修复，待Task 1结束审查后派发；不依赖Task 2决定。

1. 读取 `ProjectInteractionHost.tsx` 与其组件测试、`interactions.ts` 的真实请求/脚本回执路径。原生已有持久成功的运行却仍显示“项目交互连接中断”，源码证实poll成功不清除此错误。不要把真实运行结果改成成功或重跑脚本。
2. 在现有组件内区分通信中断提示与操作失败，成功完成本轮所需读取后清除相应通信提示。不要清除脚本执行/窗口显示/提交的实际错误，也不能让较旧的成功清除更新故障。使用已有轮询/取消机制，避免新增状态框架。
3. 保留旧实现失败的最小回归：一次真实API边界读取失败后下一次成功，通信提示消失；同时保留实际脚本失败；卸载或连接失效后的迟到结果不改变当前状态。单元边界可mock，不能冒称真实业务链。
4. 用专属应用会话执行真实项目脚本，真实短暂服务断连/重连后核对横幅恢复、原请求未重复执行、SQLite原结果未改写；不能用伪成功响应。若无法安全制造该故障，明确保留真实故障验证缺口，不夸大原生普通成功。
5. 只改相关组件、必要测试及本次验收文档；运行相关组件与交互协议测试、前端类型/lint，独立提交并报告红绿证据。

## Task 4: 已确认归属的退出进程清理

Task 1审查完成后单独实施，修复真实故障注入已复现的共享根因，不与End实现并行。

1. 阅读 `project_browser_processes.py` 全部归属、启动身份、存活与发信号路径及所有调用方。证据为 `docs/qa/2026-09-28-remediation/process-exit-fault-probe.py/json`：本次子进程真实SIGKILL后state=Z、birth仍匹配、kill(0)认为存在、原生参数不可读；capture在已确定worker归属后再次做参数归属判断而抛未知候选异常。
2. 以匹配的内核启动身份和已验证归属为依据，消除已知owned进程的冗余候选身份判断。最终发信号仍复验启动身份，PID重用不得越界。未知活候选、原生参数不可读且无既有所有权的情况继续失败关闭；不要放宽strict_ownership、吞清理错误或延长时限。沿现有共享helper修，不在各manager堆补丁。
3. 增加旧实现失败的有效检查：匹配worker birth且参数已消失仍保留清理责任；已知previous birth同理；不匹配/recycled PID不能跳过归属判断；未知活候选仍拒绝。真实SIGKILL探针修复后不再抛误判，child仍由真实wait回收，不能通过伪造系统响应证明此项。
4. 重新执行原失败相关credential/timing/webhook/interactive、已有进程归属/取消回归；最终完整默认后端统一在全部业务源码稳定后运行，并启用只观察不改变结果的诊断。不能将新检查通过自动解释为原3项失败根因全部确认。
5. 调整sidecar shutdown测试的启动失败诊断，READY为空或非法时提供已有有界stderr原因，保留真实失败断言。所有长程诊断使用专属临时根，避免pytest不同会话互相清理证据。
6. 独立提交业务修复、测试与本次证据，记录平台边界；Windows原有原生句柄/Job路径不在此POSIX修复中。
