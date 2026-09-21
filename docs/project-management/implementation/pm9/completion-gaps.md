# PM9 剩余工作复核

日期：2026-09-21；状态：confirmed（缺口与证据核对），PM9 仍 in_progress。来源：当前候选 52936b6a、本机后续验证、运行中的 Actions 35560163432、历史 d59607f3/Actions 35531206432、总体规格与覆盖台账。核对置信度：高；未逐项复核的实现状态：未知。

**结论：历史 d59607f3 的 R1–R4 有界交付和三平台 CI 已完成；本轮 52936b6a 的三平台验收仍在收口，完整 PM9 尚未完成。** PM9-A 要求全部功能/场景/契约逐项对应真实证据，现有两条代表性生产链不能代替这一要求。PM9-B 的万行、固定每分钟千条合成输入已有三平台结果；PM9-C 的三种安装包已生成且包内流程通过，实机安装和原生专项仍待补证。

## 1. 真正尚未支持的能力

| 优先顺序 | 尚缺能力与规格 | 当前实现证据 | 完成条件 |
| --- | --- | --- | --- |
| 1 | 项目子流程，含固定子流程内容、参数/输出、父任务撤权传播；FLOW-08、FLOW-A11、XE-C02/XE-A20 | [项目节点目录](../../../../apps/backend/src/autoflow/domain/workflows/catalog.py) 仅 14 种节点，没有子流程；[准备校验](../../../../apps/backend/src/autoflow/domain/workflows/run_validation.py) 拒绝目录外节点 | 复用共享执行器接通项目端口；验证编辑后仍执行冻结内容、变量隔离、父任务取消后禁止子流程写入。不能只扩白名单。 |
| 2 | 人工处理的合法继续位置和具名输入；XE-C12、XE-A15、XE-G05 | [manual_runtime.py](../../../../apps/backend/src/autoflow/application/project_runs/manual_runtime.py) 的 command 明确拒绝 targetNodeId 和非空 inputs | 声明输入契约、枚举并校验可达位置/调用栈/循环上下文/变量前置，前后端接通并验证竞争。当前从原节点继续已通过。 |
| 3 | 含循环或人工节点的并行图 | [run_validation.py](../../../../apps/backend/src/autoflow/domain/workflows/run_validation.py) 的 _validate_lifecycle_graph 明确拒绝并行根/同路由扇出；R4 Ruling 已记录共享状态限制 | 共享 Runtime 隔离分支控制状态后再开放；核对分支变量、循环与副作用次数、唯一 End 汇合。不能删除准入检查冒充实现。 |
| 4 | Windows 任意路径工作流文件输出，以及缺少原生所有权证据的孤儿进程清理 | [workflow_artifacts.py](../../../../apps/backend/src/autoflow/infrastructure/filesystem/workflow_artifacts.py) 的 _open_output_parent 等分支返回 ARTIFACT_PLATFORM_UNSUPPORTED / 501；[原生进程边界](../../../../apps/backend/src/autoflow/infrastructure/process/browser_processes.py) 保守保留未知归属 | 实现原生安全路径/句柄和所有权验证后，在 Windows CI 验证取消、原子提交、重启与危险路径拒绝。项目 XLSX 导出和受控运行产物已支持，不能混为一项。 |

这几项包含共享运行时或原生安全边界改动；具体设计、契约与实施切片已在 [新增能力方案](../../../superpowers/specs/2026-09-21-pm9-runtime-capability-completion.md) 补齐，新增架构确认前不开放能力。既有安全拒绝保持有效。跨进程人工恢复是当前明确不支持的范围，不因本表而擅自扩大成新的必做功能；原同 Run/存活现场继续与重启中断规则已有证据。

规格依据：[数据流与契约 FLOW-08](../../design/data-flow-and-contracts.md)、[执行与环境 §6、XE-C12/XE-A15](../../design/execution-and-environment.md)、[PM9 总计划](../../../superpowers/plans/2026-09-13-project-management-milestones.md)。当前 14 种项目节点也不等于全部 Studio 节点均可用于项目；其他节点应按已确认业务场景逐个接入，不以目录数量确定完成范围。

## 2. 覆盖台账与真实场景仍未闭合

后续复核：251 条已补 `testMapping`，200 条有实际断言引用，51 条明确未定位直接场景测试；73 条失效预定路径全部补了映射或缺口。原 22 条 verified 发现未闭合子条件，已逐项退回 partial，并保留 statusBeforeReview。补入本轮真实场景后，当前合计为 0 verified / 188 partially_verified / 63 planned（204 条有断言，47 条仍未定位直接场景）。详情见 [test-mapping-review.md](test-mapping-review.md)。以下表格是复核前快照，已被本段当前统计取代。

此前 d59607f3 验收已把 DATA-LINK-05、FLOW-A16、XE-C12、XE-C18、XE-G04、XE-G05 六项直接匹配的三平台成功链补入台账，状态从 planned 改为 partially_verified；没有将一部分断言升级为整项 verified。

| 类别 | 总数 | verified | partially_verified | planned |
| --- | ---: | ---: | ---: | ---: |
| 功能 | 48 | 4 | 44 | 0 |
| DATA/FLOW/XE 场景 | 178 | 17 | 91 | 70 |
| 执行契约与门禁 | 25 | 1 | 18 | 6 |
| 合计 | 251 | 22 | 153 | 76 |

以上是**旧证据台账快照，不是功能完成百分比**。旧快照 229 项未闭合；本轮逐项复核后全部 251 项仍各有未闭合子条件，不等于 251 项没写代码。特别是多数历史阶段使用隔离执行器，只有直接覆盖的场景才能换成生产证据。

73 条登记指向 5 个不存在的预定文件：test_project_excel.py、test_project_environment_retention.py、test_project_claims.py、test_project_full_scenarios.py、test_project_manual_actions.py。已有测试分散在 Excel services/exports、environment persist/restore/real browser、project input groups/data scheduler、project batch real browser 等文件；必须逐条核对断言，不能仅凭近似文件名自动改为通过。

应优先补的真实场景：

1. DATA-E2E-01/03/06：多输入与显式状态连续任务；人工版本冲突；运行中新增字段、第二表记录和并发旧结构任务。
2. FLOW-A03/04/06/07/13：任务自身版本推进、人工新值保护、写成功响应丢失、后续节点失败仍保留已写效果、同记录释放后可再次领取。
3. XE-A10/12/14/23/24/25：旧环境候选发布冲突、saved_unlinked 仅修复关联、人工继续/到期竞争、混合初始输入与新建记录的 End 关联、禁止替换其他身份、新增字段后关联新记录。
4. DATA-E2E-04/05 与 DATA-SH/SYNC/LIFE：跨项目远端字段写入、发送未知/重启核验、重新授权/绑定和归档时未决操作。

其中 DATA-E2E-06 并发部分已确认是**实现缺失**（见下），其余条目按 coverage 中分类核对生产端到端证据，没有断言相关单元/集成测试不存在。完整逐项列表见 [coverage-audit.json](coverage-audit.json)，原文与已有报告见 [coverage.json](../coverage.json)。本轮 73 条路径映射已完成；剩余完整业务组合、UI 与外部专项按实际缺口继续补证。

## 3. 外部与发行证据

- **Sheets 不是从未实网验证。** [PM6 报告](../pm6/verification.json) 已记录 2026-09-19 服务账号、真实 Google REST、真实系统凭据库、拉取/推送确认和解绑删除；已检查对应 live-result.json 的 passed 结果。缺少本次 PM9 代码与打包应用的完整项目→运行→Sheets 推送核验，以及 OAuth 桌面客户端路径。历史验收使用的原生配置文件选择框被测试入口替代，不能证明原生面板。该次结束已删除本机凭据，当前资源授权是否可复用尚未确认；本轮未读取或复用秘密、未触碰远端表。
- **三平台实机安装与原生专项。** CI 已构建 EXE/Intel DMG/ARM DMG 并运行包内应用，但安装向导、系统阻拦提示、原生文件选择/保存、凭据创建/读取/删除和卸载残留没有三平台完整手工证据。按用户要求明确保留待验收。
- **签名/公证。** 当前构建不等于带签名发行。需对应签名身份和公证条件，以及正式产物核验；现有证据不支持宣称完成。
- **用户验收与合并。** PM9 PR #1 仍为草稿，当前工作位于 codex/project-management-pm9-runtime；尚未将 PM9 改动合回 baseline。此前要求的“先合并历史有效代码，再从 baseline 创建 PM9 分支”已完成。这是最终交付收口，不是测试缺陷。

## 4. 性能数据不另造阻塞

历史 d59607f3 中，Windows 五路万条准备 725733 ms，真实 worker 537 日志/分钟；两个 Mac 对应 104904/85377 ms 和 1642/1539 日志/分钟。各平台固定每分钟 1000 条**合成输入**均读回通过。PM9 原始规格要求的是这一合成负载，并未给 worker 吞吐或万条创建耗时 SLO，因此 Windows 性能是已量化的优化项，不能虚构成“未达到原规定千条 worker 吞吐”的失败。

后续工作已开始修改生产代码：人工到期与已接受继续命令的竞争已复现并修复，扩展真实场景见 follow-through 计划。d59607f3 报告仅保留为历史基线，新候选需要重新验证。完成证据闭合与实际功能缺口前，releaseAccepted 继续为 false。

## 5. 本轮新增完成项

- 251 条规格已逐条给出实际断言范围或明确缺口；引用校验通过。
- 人工继续/到期两种交错均有真实 worker 失败复现，修复采用同一状态版本 CAS，本机当前共 18 个真实浏览器场景通过，包含实际 HTTP 在途继续与 TTL 先胜竞争；最后占用修正另复测旧候选真实链。
- 生产环境操作造成通用操作列表 500 已修复；列表、ID、项目原键返回既有环境 DTO，生成客户端同步，workspace 作用域不扩大。
- 生产 HTTP 双输入、任务连续写、人工新值保护、失败保留提交、混合关联、禁止替换、关联修复和基础旧代次拒绝均通过。关联提交边界另有实际 worker linkRevision 竞争及全组回滚断言。
- 本轮具体运行与故障注入边界见 [follow-through.json](follow-through.json)。候选 52936b6a 的 ARM 全量/源码/打包 CI 已通过；Windows 全量/源码/打包 CI 亦已通过；Intel 前端首次元素等待失败，保留记录，原 SHA 仅 Intel 重跑已接受（attempt 2），不沿用旧报告。

XE-A10 已增加真实 worker 关闭/候选暂存后在发布边界注入 ENOSPC、T2 发布 g2、旧 T1 冲突与另存；修复 retained_unsaved 的状态、现场额度和原子重获占用。发布结果不明仍保留占用，原生 UI/物理磁盘故障仍未证明。

XE-A23 的消耗邮箱筛选与共享人员/新账号后继已在下述新本机链完成；当前仍缺 DATA-E2E-06 的并发旧契约。运行中兼容字段/新建记录/修改/状态的串行真实链已补，但并发缺少生产多 Run 能力。上述基础机制有测试不代表这些整组已验收；UI 反馈亦逐项保留 gap。四项新增架构已出具体方案，等待确认。

候选校正（confirmed）：f25b3867 的三平台 CI 均在类型检查失败，未运行生产链。此前 typecheck passed 记录有误，cleanupResidue 未接纳环境操作 DTO；已修复并通过新本机类型检查，后续候选重新验证。

本机安装包补证（confirmed）：已下载 52936b6a 的 ARM DMG，完成镜像校验、只读挂载、隔离复制、真实应用启动、认证 sidecar 健康和父进程退出清理；镜像已卸载。见 [install-follow-through-darwin-arm64.json](install-follow-through-darwin-arm64.json)。随后通过真实 macOS open-panel/save-panel 完成 Excel 导入与导出，读回保留文本 001/中文，源工作簿 hash 不变；未使用 QA 面板替代。这只关闭 ARM 安装包挂载/复制/启动及该 Excel 原生路径子条件，不证明 Gatekeeper、其他原生专项、凭据、签名或完整卸载验收。

新增并发边界（confirmed）：52936b6a ARM 包的第二参数批次 blocked、Task queued，旧人工任务占据唯一执行槽。串行加列/新建/修改/状态成功见 [补测报告](business-combinations-darwin-arm64.json)，不能作为并发旧契约成功。FLOW-A02 与 DATA-E2E-06 新增 implementation_missing；多 Run owner/资源集合租约与单 Run 分支隔离是不同工作，详见 [独立补充方案与切片](../../../superpowers/specs/2026-09-21-pm9-multi-run-capacity.md)，尚未获批。

当前 Windows 候选实测（52936b6a）：五路万条写入 1007788 ms、2 次明确 busy 重试；合成 60 秒发出/读回 1000 条，最大批次延迟 188 ms。原始指标见 ci-follow-through-win32-x64.json；不据这些数据虚构 worker 吞吐 SLO。

最新候选更新（confirmed）：XE-A23 完整补测发现 inputEnvironment 在开始批次时错误要求无关默认 Profile，且 atTaskStart 未由调度器消费。已修复为领取事务重验输入后冻结所选环境 Profile；无关默认配置不参与检查，解析失败无 Task/lease。54 定向及独立复审通过，新 frozen backend 的完整人员/邮箱/账号恢复链通过，包括人员原本已有关联且未被替换；详见 input-environment-follow-through.json。该生产修改需要新三平台矩阵，52936b6a 的 Intel 重跑已因候选变更取消，旧 Windows/ARM 成功只留历史。当前 188 partial/63 planned/0 verified，新候选结果以 verification.json 为准。
