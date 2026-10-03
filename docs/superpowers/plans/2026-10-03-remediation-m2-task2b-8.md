# M2 Task 2b（统一出错策略）与 Task 8（自动版本写回）步骤级记录

- 日期：2026-10-03；状态：执行中。上位：[M2 规格](../specs/2026-09-30-remediation-m2-business-model-reliability.md) R2-08/R2-09/R2-10/R2-12（2b），R2-24（8）。

## Task 2b 统一出错策略

- 新格式 `errorPolicy = {version: 2, onError: stop|continue|retry|goto, maxRetries(0–10), backoff{kind fixed|exponential, initialSeconds, maxSeconds, jitter}, retryOn any|timeout, gotoNodeId, onExhausted stop|continue}`（`domain/workflows/error_policy.py`）。只有 version 2 生效；不合法的新策略被忽略（按失败即停），不猜测。
- 旧设置（errorPolicy.mode、retryCount/retryDelay/retryBackoff/retryExhaustedAction、timeoutAction=skip）只换算为"候选"，界面提示"尚未生效"并提供"启用这项设置"（启用时清掉旧键）。前后端换算共用 `apps/backend/tests/fixtures/error_policy_candidates.json` 互测。
- 运行时（`application/workflows/runtime.py::_apply_error_policy`，Studio 与项目共用）：
  - retry：只对副作用为"无"的节点自动重试（R2-10）；可能有副作用的节点不重试并记录原因，按用尽后处理。
  - goto：跳回前检查目标到当前节点区间内已执行节点的副作用，有可能对外影响的拒绝跳转；跳转次数受 maxRetries 与全局调度上限约束；每次重跑都是新的节点尝试事件（R2-09）。
  - continue / 用尽后继续：记警告并视为已处理，继续后续节点。
- 界面：配置面板"出错处理"统一控件（NodeErrorPolicyEditor）；模块条徽标与画布红色回流线显示新策略；旧控件仍在 M1 开关后隐藏（M6 清理）。
- 循环节点 onTimeout、节点级 timeoutAction=retry 仍按 M1 提示未生效，未转换（无安全语义可映射）。

## Task 8 自动版本写回

- `UpdateProjectRecordCommand.expectedContentRevision` 可省略（None）。省略时以"本任务对该行的认知"做字段级冲突：本任务最近一次写入后的值，否则领取时冻结的值，否则任务读取证据中的值；只比较本次要写的字段，其他人改的其他字段保留；同字段被改则 `FIELD_CONFLICT`（409，列出字段、当前值与拟写值）。
- 显式版本保持原整行严格检查；同命令重放返回原结果；租约与来源身份校验不变。
- 新建"更新记录"节点默认不带版本号；已保存节点不变。
- 敏感遮蔽：项目字段目前没有敏感定义，冲突值原样返回；签名驱动的敏感标记随 Task 7（R2-21）接入。
- 未做：R2-23 运行时移除表结构操作（会破坏现有工作流），留待 Task 7 迁移报告一起处理。
