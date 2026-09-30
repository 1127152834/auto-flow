# PM9 字段结果引用实施切片

日期：2026-09-23。状态：proposed，等待冻结授权扩展契约确认；已批准业务目标的缺失事实由打包反例证实。规格：`docs/superpowers/specs/2026-09-23-pm9-created-field-results.md`。实施仅在既有 pm9-runtime worktree，按 FR1→FR2→FR3；每片保留未完成上下文条件，不将单片当完整能力。

## FR1 显式来源与最小生产写链（30–90 分钟增量）

落点：`domain/project_data/capabilities.py`、`application/project_runs/coordinator.py` / `worker_capabilities.py`、`providers/browser/project_graph.py`、`renderer/domains/workflows/components/config-panels/ProjectDataConfig.tsx`，复用现有冻结工作流和运行证据，不增加新表。

- [ ] 补最小有界计划测试：冻结 fieldResultSources、拒绝缺来源/非 add/ensure/错误表代次/模糊变量；保留原静态字段必须存在的校验。
- [ ] 写真实 RPC→SQLite 的失败后成功测试：只有已提交来源访问及原 ProjectOperation 能授予具体返回字段，原始输入/静态 scope 不变。复用 project_command_id，拒绝伪造字段与旧代次。
- [ ] 项目数据适配器仅解析 create/update 字段值映射的动态键，碰撞及非 UUID 拒绝；共享 Studio 解析语义不变。
- [ ] 组件先接声明来源选择与往返测试，再接现有节点配置。若类型来自现有 OpenAPI，则同步生成并检查；无公共 API 变化不手工改生成文件。
- [ ] 顶层顺序的真实 worker 创建→返回字段写入→同定义复用后写入通过；同 Task 并非全字段通行证。提交实现、测试、契约、范围台账和 `.ai`。

## FR2 调用、循环、并行及恢复（30–90 分钟一个子片）

落点：上述 worker 入口、既有 CanvasSubflowGraph/执行上下文解析、`test_project_capability_rpc.py`、`test_project_batch_real_cloakbrowser.py` 及原子流程/并行测试。

- [ ] 证明同调用/同迭代前序访问可消费；相同 nodeId 的另一次调用、兄弟分支、旧迭代不得误取。不能只按最新全局节点结果授权。
- [ ] 按现有明确输入/输出和合并声明传播来源事实；缺显式传播拒绝。为每个支持路径补正反例，未支持路径独立记录，不能通过扩大静态白名单闭合。
- [ ] 证明其他 Task、人工新列、替换代次、撤权/取消、字段删除后重建拒绝。已有记录 lease、CAS、来源同步围栏仍生效。
- [ ] 写成功响应丢失按原命令恢复，既有 add/ensure 不重复；后续失败保留已提交的值与版本。各子片分别提交，不等整批才留证。

## FR3 组合与打包验收

- [ ] 扩展已有 `smoke-project-business-combinations.mjs`：T2 持旧契约等待，T1 创建/复用返回字段并写回；异型同键明确冲突，T2 最后仍按旧字段运行。把本轮两条失败补丁替换为相同原目标的通过证据，不缩小期望。
- [ ] 相关 RPC、能力/字段影响、变量、组件与脚本检查；候选稳定后完整后端/前端/类型/lint/OpenAPI/构建和一次三平台 CI。
- [ ] 保存当前打包 HTTP/worker/浏览器报告，真实 Google 和其他实机条件继续独立。只提升具体已有证据的范围，完整条件未齐不标 verified，releaseAccepted=false。
- [ ] 在原分支提交推送并更新草稿 PR，不合并或发布。

## Review focus

最关键的是生成权限与消费权限的关系：成功 add/ensure 是来源事实，消费者仍必须有冻结的来源声明和原数据操作权限。任何实现若只是给整个 Task 扩字段集合，都不满足规格。第二关键是字段结果与具体 nodeVisit/call/branch/loop 的归属，不能因字符串模板成功解析就视为授权。两项在实现前均有明确反例，在提交前均须实测。
