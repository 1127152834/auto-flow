# PM4-A 完整输入选择核验

> 状态：实现完成，待 PM4 最终跨包端到端复验
> 日期：2026-09-15
> 基线：`11e44be`

## 用户可操作行为

- 自动化输入支持独立选择、固定记录、同一记录、字段相等和记录槽关联。
- 同一数据表可以配置多个独立角色；选择器会回溯寻找互不冲突的完整输入组。
- 可选输入没有记录或暂时被占用时可以留空；配置错误、关联歧义和必要输入缺失会准确阻止启动。
- 启动弹窗逐项显示可用、未匹配、暂占、歧义、配置错误、扫描范围过大和尚未确定。
- 被必要下游依赖的可选输入会明确显示为本次实际必需。

## 已验证事实

- 启动时重新读取当前数据，不复用预检旧事实。
- Task、不可变输入快照、全部 lease、写游标及 queued CoreRun 在同一事务提交；领取中途故障全部回滚。
- 两个不同操作并发领取同一组记录时只有一个 Task 成功创建。
- 只有显式 `sameRecord` 别名允许共享来源 lease；其他关联或独立角色不能隐式共用记录。
- 固定记录仍须满足当前筛选和状态条件；失效代次属于配置错误。
- 字段相等使用同类型精确比较；空值不关联，多条匹配返回关联值和 typed record references 供修复。
- 单次记录物化及组合评估均有 10,000 上限；预算耗尽不冒充数据耗尽。

本包完成了选择器、真实 SQLite 领取、真实启动协调器、HTTP DTO、生成客户端类型以及管理组件的分层验证。文本 `"1"` 与整数 `1` 的身份隔离为分层证据；最终 PM4 集成链仍需再次覆盖真实数据库领取和页面展示。

## A/C 责任边界

PM4-A 在单次扫描超过上限时准确阻断，不创建半个 Task。候选游标、继续查找及由调度器恢复扫描属于 PM4-C，当前硬阻断不能作为 PM4 最终实现交付。

## 验证命令

```bash
uv run --directory apps/backend pytest \
  tests/unit/test_project_input_selection.py \
  tests/unit/test_project_automation_rules.py \
  tests/integration/test_project_input_groups.py \
  tests/integration/test_project_run_data_start.py \
  tests/contract/test_project_runs.py \
  tests/integration/test_project_run_start.py \
  tests/integration/test_project_run_dispatch.py -q
uv run --directory apps/backend ruff check <PM4-A changed Python files>
uv run --directory apps/backend mypy src
npm --workspace @autoflow/desktop test -- --run \
  src/renderer/domains/project-automations/components/InputPlanEditor.test.tsx \
  src/renderer/domains/project-runs/components/DataInputPreview.test.tsx \
  src/renderer/domains/project-runs/components/BatchLauncher.test.tsx \
  src/renderer/domains/project-runs/components/TaskEvidence.test.tsx
npm run typecheck
npm run openapi:check
git diff --check
```

结果：后端相关回归、Ruff、mypy、前端相关回归、TypeScript、OpenAPI 和 diff 检查均通过。真实执行核心、Studio、真实浏览器、Windows、其他架构、打包应用和用户手测未执行。

## 执行边界

**管理侧通过，真实执行核心接入待验收。** PM4 继续使用隔离测试执行器；该结论不表示生产工作流执行器可用。
