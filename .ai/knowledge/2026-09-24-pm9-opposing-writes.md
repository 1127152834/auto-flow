# PM9 反向写入与人工错误分支

日期：2026-09-24。状态：confirmed（本机真实双worker子范围）。来源：DATA-WRITE-12、原始数据规则§7.3、opposing-writes-follow-through.json及其中哈希日志。生产仍51e8991e。

执行切片：复用Sheets真实worker测试夹具 → 公开保存两份文档/自动化 → fixedRecord分别领取A/B并先完成自己写入 → 两个人工屏障保证两份lease同时存在 → 显式query/update对方记录 → 错误边进入两个新的人工等待 → 比较记录、lease、游标、原输入、同步意图 → 公开停止并核验释放。只替换Google transport/凭据，不注入Task/Run/lease或第二执行器。

首次场景输入计划用未声明code字段筛选，公开校验422正确拒绝。测试改用原有固定记录输入表达所需前提，未放宽校验。首次通过后补强原输入值/版本1和A/B各版本2意图的精确断言，最终1 passed/2 warnings/12.89s：各一条反向写明确LEASE_BUSY，人工等待期间双方仍持有各自lease，避免提前结束释放造成假通过；先前值、版本2、原输入、两条pending推送意图不变。stop后两batch stopped、无waiting/held/reconciling、worker不busy，fixture网页请求恰好2、Google写0。

边界：一条失败命令直接走错误边；不证明配置自动重试、有限多记录组原子提交、打包/原生三平台或Google实网。DATA-WRITE-12仍partially_verified。CI选择纳入real_opposing_writes，当前35895754111不包含新增测试；待新候选一次验证。源码51e8991e串行完整3487/79skip已通过，新增测试单独执行，不冒充该次完整收集的一部分。releaseAccepted=false。

CI命令按实际工作流提取并collect-only确认32/43选择、11排除；不是32项执行通过。新增测试的语法/Ruff、251引用和4项映射检查通过。

最新原生验证：本机候选与测试补证稳定后，单次发起35902129697，实际headSha=a317e1f87c9b775940a8faa45713c884007ce6ad，生产仍51e8991e，三平台in_progress。此前等待旧矩阵全部结束的安排被这次不同源码的一次必要验证取代；旧35895754111继续，ARM job已success，Windows/Intel仍在跑，不取消或重跑旧job。旧ARM日志需整run结束才能读取，不据job状态编造测试计数。
