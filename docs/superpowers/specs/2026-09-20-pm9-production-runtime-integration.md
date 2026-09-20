# PM9 生产执行链接入方案

- 日期：2026-09-20；状态：confirmed，用户于 2026-09-20 明确回复“确认”，授权实施 R1–R4。
- 来源：PM9 总计划、当前生产 bootstrap/callers、独立审查。置信度：高。
- 目标：让同一 Studio 工作流从项目批次运行时，真实执行多表数据、参数、End 环境保留和人工处理；不以 QA 执行器替代。

## 当前断点

`bootstrap/workflows.py::configure_project_workflow_runtime` 装配独立的持久项目 Run 协调器。其 `domain/workflows/catalog.py` 只有 open_page/input_text/click_element/get_element_info，`run_validation.py` 只接受单线链，`providers/browser/project_workflow_worker.py` 使用旧 WorkflowExecutor。新版 Studio 的图执行器 `application/workflows/runtime.py::WorkflowRuntime` 已支持更多控制流和节点，但只接入 Studio worker。

项目数据用例、执行代次 fencing、环境保存、人工命令与统计查询已经存在；隔离 QA 执行器直接驱动这些用例，未证明其生产节点接入。仅扩白名单会造成预检通过、worker 运行失败；直接从项目 UI 调用 Studio start 会丢失项目原子领取、Task/Run 身份和恢复语义。

## 建议实现

保留项目现有批次/Task/Run 持久模型、operation 幂等、调度器、资源租约、代次撤权和事件表。将项目 worker 的节点遍历替换为已存在的 Studio `WorkflowRuntime`，而不是再扩展旧四节点解释循环。

1. **统一文档与冻结能力。** 从当前 Studio 文档编译已保存内容及依赖快照，参数身份继续以现有合同为准。预检只开放项目适配器实际支持的节点/能力；缺少项目绑定时清楚拒绝。保留历史 prepared content 读取，不迁移旧业务状态为成功。
2. **保持进程边界。** 扩展现有项目 worker JSONL 协议，增加受限 capability request/result 消息。消息含 runId、executionGeneration、nodeVisitId、attempt、commandId 和固定能力名；父进程按当前任务身份路由到 `application/project_data/capabilities.py` 与环境用例。worker 不连接 SQLite，不接受 renderer 任意路径，不获取 renderer token。
3. **事件适配。** Studio 节点事件转换为项目现有 nodeAttempt/log/output/checkpoint，仍先持久确认再推进；保留节点访问与重试身份。凭据派生值沿现有敏感标记脱敏，不写快照或日志明文。迟到代次请求拒绝；响应丢失按原 commandId 查询，不换键重放写入。
4. **End 与人工。** End 等待 worker 确认浏览器关闭后，父进程复用 `environments/retention.py::end_task` 完成保存、关联与结果核验；只有确定成功后才能推进 Run 终态。人工暂停持久保存执行检查点与版本，复用 `environments/manual.py` 的命令和过期校验；恢复从检查点继续，不重跑已完成节点。不清除 unknown 或 cleanup_failed 来强行结束。
5. **前端入口。** 复用现有 Studio 配置和项目页面，只补缺少的绑定字段及有效性反馈，不另造执行页面。HTTP DTO 如有必要变更，先更新后端契约，再生成现有唯一客户端。

## 实施切片与验证

- **R1：真实浏览器兼容链。** 项目通过共享 Runtime 执行四个已开放节点，保留事件/停止/重启语义。先让已有真实 CloakBrowser 项目测试在当前 bootstrap 下通过；验证源码与打包 worker。
- **R2：项目数据与完整图。** 有界 capability RPC + 多表读取/条件/写入 + 参数冻结；同一数据写入在响应丢失、重复命令、强停旧代次下只发生一次。新增 `test_project_full_scenarios.py`，使用真实进程与隔离数据库，不能通过直接改行伪造执行结果。
- **R3：End/人工/环境复用。** 本地登录站完成注册、End 保存并关联新记录、另一流程复用登录、人工继续/终结、超时及进程中断。真实浏览器关闭不明确时保持核验状态。既有同节点 input_prompt 不冒充人工业务完成。
- **R4：发行链。** 三平台同版本安装包内执行完整链、Sheets 实网结果引用实际授权资源、统计下钻/失败后续/归档恢复/安全删除。未执行的平台和原生凭据/面板/200%输入行为维持未验收。

全量工程检查继续：pytest、ruff、mypy、前端 test/typecheck/lint/build、OpenAPI、脚本/结构检查；阶段证据落 PM9 目录并更新 coverage。当前验收基础设施包不预先标记这些 R1–R4 完成。

## 取舍与影响

该方案涉及两个现存运行入口的对齐和跨进程协议，属于架构级工作，不是增补一条 smoke。复用稳定持久事实和共享图执行器，避免第三套执行循环；代价是必须重新验证停止、恢复、资源清理、敏感传播和安装包通信。默认保持单个活动项目 worker 的现有容量，性能扩展不在此包。

依据项目 AGENTS.md「架构级工作必须先完成设计、规格和实施计划，并等待用户确认」，上述 R1–R4 已获用户确认，持续实施。用户已授权的基线整合、现有能力的验收入口、构建和 CI 继续执行。
