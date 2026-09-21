# PM9 remaining runtime capabilities — approved

日期：2026-09-21。状态：approved；2026-09-21 用户在收到 S1–S5 后要求“继续实现”。来源：用户 PM9 后续指令、已批准 R1–R4、当前代码审查。既有运行链验证和缺陷修复继续执行。

## 设计时边界（历史；实施进度见 completion-gaps）

- `application/workflows/runtime.py` 的 `_WorkflowScheduler` 共享 ExecutionContext 和 executed/pending 状态；不能只扩大 `run_validation.py` 的准入。
- 现有 canvas subflow gateway 可以执行组，但项目 prepared content / capability 尚未支持冻结子调用身份。
- `project_runs/manual_runtime.py` 明确拒绝 targetNodeId 与非空 inputs；目前仅同一存活 worker 的原检查点继续。
- Windows 已有 GetProcessTimes birth identity，并非完全缺进程识别；未知归属仍不能杀进程。任意输出路径的部分操作仍 501；受控产物与项目 Excel 导出已可用。

## S1 项目子流程

首先接通已有 canvas subflow 的定义与调用。复用 prepared execution plan 已冻结的 document 保存子图内容，建立指向该内容的调用依赖索引，不复制一份子文档存储，也不在执行时重读 Studio。沿用现有 subflow 节点和 gateway，不创建第二 Run 或第二执行器。外部工作流引用不随本片扩大为全部 Studio 节点接入；旧计划保持原解释。

准备时递归解析实际画布子图依赖、校验节点能力、检测调用环；沿用既有 gateway 的深度上限 32，超限给出调用路径。`subflow` 节点显式声明 `inputs`（名称到表达式）、`outputs`（子结果到父变量名称）。输入在调用时复制 JSON 值；子变量、循环栈、临时输出独立，只有声明输出在成功返回时提交父变量。失败保留此前真实数据效果，不提交未完成的父变量输出。

共享 `_WorkflowScheduler` 的子调用消费入口同时扩展：将解析并复制后的声明输入和调用身份传给既有 gateway，接回具名结果，仅在成功时按 outputs 映射写父上下文；不能只改 subflow 节点的配置。

父 Run/Task/执行代次/取消令牌保持不变。每个调用有稳定 invocation path；nodeVisitId 包含调用身份，避免重复节点 ID 的事件和命令串用。parent 端从冻结依赖定位真实节点；子权限为父声明权限与子所需权限的交集，不能因子引用扩大项目/表权限。父撤销后迟到调用被既有代次检查拒绝。先拒绝子流程内 End；唯一根 End 负责关闭/保存。人工仍限制为单一活跃检查点。

验收：准备后编辑画布子图不改变本次结果；两个调用同名变量不串值；未声明输出不泄漏；环/深度/缺依赖拒绝；父取消后子数据写拒绝；重试同一 visit 不重复新增。单元 + 父子真实 worker HTTP 链共同通过后开放项目 subflow。

## S2 人工声明输入与合法继续位置

沿用现有 resume 请求的 `inputs` 与 `targetNodeId`；冻结节点配置新增 `inputSchema` 和 `resumeTargets`。无配置保持现有空输入/原位置行为。第一版目标只能是检查点直接后继，且必须在同一调用与分支内；不支持跳回已执行节点、跨循环/调用边界、跳到 End 或绕过 join。错误在接受命令之前返回 422，并列出字段/目标原因。

S2 字段契约：`inputSchema` 是 `{name, type, required?, enum?, title?}` 数组，沿用 JSON 的 string/number/integer/boolean/array/object 类型；名称不允许隐藏系统绑定。`resumeTargets` 是 `{nodeId, title?, requiredVariables?}` 数组；requiredVariables 检查当前调用变量或本次声明输入存在。worker 只传当前变量名，不传敏感值，parent 从冻结节点保存声明和该 owning worker 的变量名快照。多候选必须选择一个目标；没有候选保持原位置继续，单候选不显式选择时仍检查前置条件。

检查点事件保存 schema/targets 的冻结摘要。服务端先校验精确键、类型、必填/枚举和目标，再在已有事务中校验项目状态、checkpointRevision、statusRevision、Run 代次、TTL 和拥有的实例。失败不改检查点；resume/finish/expire/stop 只有一个有效转换。输入仅绑定声明变量，不能覆盖执行上下文、capability 或隐藏系统变量。

worker 的 `_ProjectManualNode` 将服务端已校验的继续目标作为独立控制结果交给共享 `_WorkflowScheduler`，声明输入先绑定到当前调用/分支变量。显式选择时只放行选定的直接后继，其他出边按既有条件路由的未选路径处理，不执行、不产生副作用；无 targetNodeId 时维持原路由。不能仅让 API 接受目标而忽略调度消费。验收必须包含两个候选后继、仅所选节点写入的正向断言。

在现有人工详情组件中先增加字段控件与错误状态，再接运行/环境页面。缺输入保留草稿；过期/已处理变只读；响应丢失查询原 operation。继续仍依赖存活 worker，重启/worker 丢失后只能收尾，不能恢复浏览器步骤。

验收：必填/类型/未声明键、非法目标、检查点旧版本、双击和到期并发；同一真实 worker 收到声明值且已执行节点不重跑；两入口展示相同处理状态。

## S3 分支状态隔离后开放循环/人工并行图

在共享 Runtime 内按结构化 fork 建立分支执行状态：变量快照、循环帧、executed/executing/pending、局部停止、visit 路径归分支所有。Run 取消、持久事件序列和 capability ledger 仍归 Run。先要求 fork 具有可验证的单一 join；拒绝跨分支回边、循环体跨 join、没有唯一收尾的形状。

S3 字段契约：沿用 `set_variable` 作为无浏览器副作用的 fork，增加 `parallel: {joinNodeId, outputs}`。至少两个普通出边；outputs 为分支入口 ID 到 `{子变量: 父变量}` 的映射，可显式为空。join 不得是分支入口，不得接收本 fork 之外的边；分支彼此不交叉，没有绕过 join 的出口，循环体末端保持既有隐式返回语义。父 scheduler 只执行 fork 和 join，分支由同一 WorkflowRuntime 的独立上下文执行；嵌套循环每轮分别汇合。持久事件 scope 保存 fork node/visit、branchNodeId 和 joinNodeId，父端从冻结图和仍执行中的 fork 验证后才允许能力请求。

join 不隐式合并互相覆盖的变量；只接受显式输出映射，同名目的地冲突在 prepare 阶段拒绝。分支 break/continue 只影响本分支循环；分支失败取消其余分支并等待清理，已提交数据不回滚；唯一根 End 等全部分支汇合后执行一次。

单浏览器上下文仍是共享资源。人工暂停必须先使其他分支到安全节点边界并确认没有在途浏览器命令，再交给人工；worker 在发出人工 capability 请求之前按到达顺序取得唯一人工处理资格，先等待所有其他分支停在安全边界，再发请求创建持久检查点；排队分支尚无持久人工项，不得向 waiting_manual Run 发送第二个请求。当前检查点成功 resume 且 parent 已回到 running 后，先交接给排队项，再释放普通分支；finish/expire/stop 取消整个队列，不新建人工项。队列不另设人工 TTL，每项仅从持久检查点创建时起计算冻结的 timeoutSeconds/manualDeadline；排队本身不重置任何已存在截止时间。自动执行预算继续按 Run 的 running 累计，只有已持久化 waiting_manual 的时段暂停；到安全边界之前及两项交接的 running 时段仍计入自动预算。不同分支的数据命令保留各自 visit，但共用 Task 权限与数据库版本检查。未完成这些约束前继续拒绝并行人工/循环。

验收：两个循环计数/变量隔离、只退出本分支、乱序汇合 End 一次、人工窗口无后台浏览器操作、两个分支同时到达人工时严格串行建项且 TTL/自动预算符合上述规则、父取消清理全部分支、失败后数据效果保留。沿用 Runtime 差分测试，并补项目真实 worker 图；不复制 scheduler。

## S4 Windows 文件与进程边界

复用 `workflow_artifacts` 的登记/取消/摘要与 `new_file` 发布逻辑；只增加 Windows 原生路径适配。先打开目录/目标句柄并核验最终路径、卷与文件身份，拒绝重解析点、设备/UNC 不支持形状、路径替换和未授权覆盖；同卷临时文件写完 flush 后原子发布，不按字符串检查一次后再次盲开。现有文件写必须匹配 expected identity；失败清理仅属于本操作的临时文件。原生 API 的最小组合在 Windows CI 验证可行后固定，不能用模拟 sys.platform 证明安全。

进程使用现有 kernel birth identity，并使终止操作在同一已验证句柄上完成，避免检查后 PID 复用；直接拥有的 worker/browser 子树才可终止。重启发现未知进程保持 quarantine，权限不足保持 blocker，不以命令行相似推断归属。不要为通过清理测试取消保护。

验收：Windows 原生重解析点/目录替换/覆盖冲突/取消清理、PID 复用与权限拒绝、父结束后子进程回收；安装包实机仍独立保留待验收。

## 实施切片与放行

顺序 S1 → S2 → S3 → S4；每片先契约/失败测试、实现、组件与真实链（如涉及 UI）、文档和 `.ai`，定向检查后再提交。S3 共用状态改动必须补既有 Studio Runtime 回归。每片未通过全部自身准入前不开放对应节点/图形。

确认范围仅以上四片，不含跨进程人工恢复、全部 Studio 节点、第二执行器、自动发布或合并。发布级退出仍由 coverage/verification 的逐项证据决定，releaseAccepted 保持 false。

文件级实施顺序、失败断言与验证命令见 [新增能力实施计划](../plans/2026-09-21-pm9-runtime-capabilities.md)，已由本轮继续实现指令批准。
