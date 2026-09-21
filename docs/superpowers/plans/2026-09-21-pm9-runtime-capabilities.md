# PM9 新增运行能力实施计划

> 执行技能：superpowers:executing-plans。状态：proposed，尚未取得本轮新增架构批准，不执行下面的代码步骤。

日期：2026-09-21。来源：用户后续任务、[新增能力规格](../specs/2026-09-21-pm9-runtime-capability-completion.md)、当前 PM9 工作区代码。已有修复的交付不依赖本计划获批。

目标：依次接通冻结项目子流程、声明式人工输入与合法继续位置、安全并行控制流、Windows 安全输出和有身份的进程终止。始终复用共享 WorkflowRuntime、既有 worker RPC、Task/Run/执行代次及保存账本。

工作区固定为 `/Users/zhangtiancheng/.codex/worktrees/pm9-runtime/autoflow`，分支 `codex/project-management-pm9-runtime`。以下路径均相对此工作区。不得修改并行 Studio 工作区、复制执行器、增加跨进程人工恢复或开放未验收节点。

## S1：项目子流程

### S1.1 冻结依赖及准入

文件：`apps/backend/src/autoflow/application/workflows/core_runtime.py`、`domain/workflows/run_validation.py`、`domain/workflows/runtime.py`；测试复用 `apps/backend/tests/unit/test_workflow_run_validation.py`、`integration/test_workflow_runtime_repository.py`。

1. 先写失败断言：准备后修改画布子图，本次执行仍读准备时内容；缺失依赖、调用环、超过规格深度的调用被拒绝，返回调用路径。
2. 复用既有 PreparedContent.document 中已冻结的 canvas 子图；补实际调用关系索引与校验，不重复存储同一文档。旧计划保留原含义，不允许运行时读取最新 Studio 文档，未批准的外部工作流节点继续拒绝。
3. 验证依赖节点权限和输入输出声明。子 End 暂不允许；根 End 唯一负责最终保存。
4. 跑上述两组测试以及旧内容兼容用例；本步骤不先开放项目节点目录。

### S1.2 调用身份、变量隔离及项目能力

文件：`apps/backend/src/autoflow/providers/browser/project_graph.py`、`application/workflows/runtime.py`、`application/workflows/executors/subflow.py`、`domain/workflows/execution.py`、`application/project_runs/worker_capabilities.py`、`domain/project_runs/worker_commands.py`。参考并复用 `providers/browser/workflow_worker.py` 已有 canvas 子图入口；不复制其执行循环。

1. 用重复调用同名子节点的失败测试确定 invocation path、nodeVisitId 和 commandId 的关系，避免命令被误判为另一调用的重试。
2. 复制声明输入 JSON 值，子变量/循环帧独立；共享 `_WorkflowScheduler` 子调用入口把输入/调用身份传入既有 gateway 并接回具名结果，仅成功的声明输出写回父变量。补 gateway 契约测试，不能只验证配置解析。
3. parent 从冻结依赖定位实际节点；子权限只可收窄父权限。沿用同 Task/Run、执行代次、取消令牌。
4. 在 `tests/integration/test_project_batch_real_cloakbrowser.py` 增加准备后编辑、双调用隔离、父取消后的迟到写拒绝。查询账本验证失败前已提交数据仍保留。
5. 定向后端、真实 worker、相关 Runtime 差分回归均通过才修改 `domain/workflows/catalog.py` 的项目准入；提交实现、文档和 evidence。

## S2：人工声明输入与继续位置

### S2.1 冻结契约与服务端校验

文件：`domain/workflows/run_validation.py`、`application/workflows/runtime.py`、`providers/browser/project_graph.py`、`application/project_runs/manual_runtime.py`、`application/environments/manual.py`、`adapters/http/project_environment_schemas.py`；测试复用 `tests/contract/test_project_environments.py` 与真实批次测试。

1. 先写必填/类型/未知键/非法目标/旧 checkpoint/旧代次的拒绝断言，确认失败不改变检查点或接受新操作。
2. PreparedContent 和 checkpoint 固定 inputSchema/resumeTargets。只允许同一调用、同一分支的合法直接后继，不跨循环、调用、join 或跳过收尾。
3. 验证项目可写、现场所有权、版本与 TTL 后接受命令；沿用当前状态 CAS，不创建新 Run，不重放已完成节点。
4. 补继续/终结/到期/停止竞争及原命令恢复断言。真实 worker 仅收到声明变量；隐藏执行身份和权限不可被输入覆盖。
5. worker 人工节点返回独立的目标控制结果，共享 scheduler 只调度被选直接后继，其余出边沿用条件路由的未选路径处理；无目标保持原语义。补真实两后继只执行所选分支的正向断言，声明值必须进入该分支变量。
6. 生成 OpenAPI 客户端，再进行 UI 联调。

### S2.2 组件与页面闭环

文件：`apps/desktop/src/renderer/domains/project-runs/pages/ManualDetailPage.tsx` 及其现有测试；必要控件位于该领域 components 目录，复用 shared 控件与字段校验。

1. 先测试声明字段、目标选项、错误提示、过期只读、未提交草稿和双击保护，再组装详情入口。
2. 项目运行/环境入口读取同一人工项与 operation 状态，不各自保存一份事实。
3. 用生产 HTTP/真实 worker/browser 从页面提交值，验证节点不重跑、值真实进入声明变量，响应丢失仍用原命令身份查回。
4. 通过该页面 Vitest、typecheck/lint/OpenAPI 和源应用验收后提交；其他界面设计不在此片顺带改造。

## S3：分支状态隔离与准入

文件：`apps/backend/src/autoflow/application/workflows/runtime.py`、`domain/workflows/execution.py`、`domain/workflows/run_validation.py`、`providers/browser/project_graph.py`；测试复用 `tests/unit/workflows/test_runtime_control_flow_core.py`、`tests/differential/workflows/test_b3_control_flow_runtime_contract.py` 及真实批次测试。

1. 先以两个循环分支、不同迭代次数和同名临时变量复现共享状态污染。确认失败来自共享上下文，而非人为放宽准入。
2. 在既有 scheduler 中隔离分支变量、循环帧、executed/pending/executing、break/continue 和 visit 路径；Run 取消、事件序列及能力账本仍共享。
3. prepare 验证结构化 fork/join、分支边界和显式合并输出；重复目的变量、跨分支回边、无唯一收尾拒绝。
4. 验证先失败分支取消其他分支并等待清理，已提交数据保持；End 仅在唯一汇合后一次执行。
5. 人工节点先请求其他分支停在安全节点边界，确认没有在途浏览器操作，再开放页面。worker 在人工 capability 请求前排队取得唯一资格，安全边界确认后才建持久检查点，避免向 waiting_manual Run 发第二请求。成功 resume 且 parent 已为 running 后先交接下一排队项，再释放普通分支；finish/expire/stop 取消队列。人工 TTL 从每项持久创建起算，队列不重置截止时间；自动预算仅在持久 waiting_manual 时暂停，静默屏障前及交接中的 running 继续计时。补双分支同时到达、串行建项、无提前 TTL、预算不被清零及取消排队项的断言。
6. 两循环互不串值、局部 break、乱序 join、人工期间无后台浏览器操作及父取消真实链全部通过，既有 Studio Runtime/差分回归无退化，才移除对应形状的准入拒绝。其他形状继续拒绝。

## S4：Windows 原生边界

### S4.1 安全文件输出

文件：`apps/backend/src/autoflow/infrastructure/filesystem/workflow_artifacts.py`、`new_file.py`；测试复用 `tests/unit/test_new_file.py`、`tests/integration/test_workflow_artifacts.py`。

1. 在 Windows runner 上写重解析点、目录替换、目标身份变化、未授权覆盖及取消清理的失败测试。测试不得仅 monkeypatch sys.platform。
2. 核对现有 ctypes/原生文件句柄封装和依赖，先做最小原生实验，固定能保持句柄身份的目录核验、同卷暂存与发布方案；无必要不新增库。
3. 在共享产物登记和取消流程内接入适配器，持有经过核验的目标身份直至提交；失败只删除本命令暂存文件。
4. Windows 原生测试及真实 worker 输出通过后才撤销对应 501；项目 Excel 导出与受控产物回归保持通过。

### S4.2 同句柄进程所有权

文件：`apps/backend/src/autoflow/infrastructure/process/browser_processes.py`、`project_browser_processes.py`；测试复用 `tests/unit/test_browser_processes.py`、`tests/integration/test_workflow_worker_process.py`。

1. 确认已有 birth identity/拥有的子进程树事实，测试 PID 复用、句柄失效、权限拒绝和孤儿进程。
2. 身份核验与终止作用于同一已验证句柄；未知归属继续 quarantine，拒绝后保持可见 blocker，不按相似命令行猜测。
3. Windows 实际 worker 普通停止、强停、父退出与重启清理通过；无法证明的实机/权限条件单独保留。

## 每片验证与交付

- 修改过程中只跑受影响测试；新增一项能力必须留下拒绝分支和真实运行证据，不能仅记录测试数量。
- 后端：`uv run --directory apps/backend pytest -q <上述测试文件>`、`ruff check .`、`mypy src`；前端涉及时 `npm run typecheck`、`npm run lint`、相应 Vitest；契约变化执行 `npm run openapi:generate` 与 `npm run openapi:check`。
- 真实浏览器沿用 `AUTOFLOW_TEST_CLOAKBROWSER`；脚本复用 `scripts/project-runtime-smoke.mjs`。每片完成更新 coverage 对应 scope/gaps、PM9 报告和 `.ai/sessions`，保持可单独审查的提交。
- 稳定生产候选执行完整回归与现有三平台 CI，保留一个有效流水线，源码/打包/安装包证据绑定实际提交。更新现有草稿 PR，不合并或发布。
- 放行仅针对有证据的切片。其余功能、原生 UI、OAuth/当前打包 Sheets、实机安装及签名公证仍按各自条件验收，完整退出前 `releaseAccepted=false`。
