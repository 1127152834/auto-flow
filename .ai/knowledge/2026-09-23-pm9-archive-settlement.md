# PM9 归档中的真实任务、保存和未知同步

日期：2026-09-23。状态：confirmed（直接断言覆盖的本机范围）。来源：`docs/project-management/implementation/pm9/archive-settlement-follow-through.json` 与 `docs/superpowers/plans/2026-09-23-pm9-archive-settlement.md`。

- XE-A17 联合测试先揭示 task updateRecord 没入 Sheets 意图队列、End 同步阻塞事件循环；改用现有同事务 enqueue_intent 与标准线程池。worker 必须等待已受理 callback 结算，才能确认清理和释放容量。
- 未知值发送在归档 blocker 中必须保留；closing 允许原结果核验、不允许新写。未结算保存以 ProjectOperation 状态阻塞，不能仅看实例状态。
- End 的项目/实例/运行代次检查进入受理事务。仅摘要一致的重放和固定父 End 子保存允许继续；用户对 retained_unsaved 的终态旧候选仍可显式更新（保留 generation conflict）或另存，不能用 Run 终态一概拒绝。
- Run 终态后，批次调度调用现有环境服务确认 native 所有权再清理实例，随后释放记录占用和结算批次。未确认清理会保留批次；retained_unsaved/unknown 不自动删除。
- 本机真实 Sheets worker 五项通过；Google 传输/凭据仍是受控 fixture。不能替代当前授权 Google、打包 UI、签名或三平台实机验收。原 PM6 服务账号实网证据保留。

测试包装器遇到两个兼容问题已修正：Windows fake worker 补 capability 字段；人工 TTL 竞争 wrapper 转发新内部受理参数。它们不作为产品缺陷统计。当前生产缺陷与断言映射、各次验证和后续 CI hash 以报告为准，releaseAccepted=false。
