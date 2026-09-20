# PM9 剩余工作复核

日期：2026-09-21；状态：confirmed（缺口与证据核对），PM9 仍 in_progress。来源：当前代码 d59607f3、同提交三平台 Actions 35531206432、总体规格与覆盖台账。核对置信度：高；未逐项复核的实现状态：未知。

**结论：R1–R4 的有界工程交付和三平台 CI 已完成，完整 PM9 尚未完成。** PM9-A 要求全部功能/场景/契约逐项对应真实证据，现有两条代表性生产链不能代替这一要求。PM9-B 的万行、固定每分钟千条合成输入已有三平台结果；PM9-C 的三种安装包已生成且包内流程通过，实机安装和原生专项仍待补证。

## 1. 真正尚未支持的能力

| 优先顺序 | 尚缺能力与规格 | 当前实现证据 | 完成条件 |
| --- | --- | --- | --- |
| 1 | 项目子流程，含固定子流程内容、参数/输出、父任务撤权传播；FLOW-08、FLOW-A11、XE-C02/XE-A20 | [项目节点目录](../../../../apps/backend/src/autoflow/domain/workflows/catalog.py) 仅 14 种节点，没有子流程；[准备校验](../../../../apps/backend/src/autoflow/domain/workflows/run_validation.py) 拒绝目录外节点 | 复用共享执行器接通项目端口；验证编辑后仍执行冻结内容、变量隔离、父任务取消后禁止子流程写入。不能只扩白名单。 |
| 2 | 人工处理的合法继续位置和具名输入；XE-C12、XE-A15、XE-G05 | [manual_runtime.py](../../../../apps/backend/src/autoflow/application/project_runs/manual_runtime.py) 的 command 明确拒绝 targetNodeId 和非空 inputs | 声明输入契约、枚举并校验可达位置/调用栈/循环上下文/变量前置，前后端接通并验证竞争。当前从原节点继续已通过。 |
| 3 | 含循环或人工节点的并行图 | [run_validation.py](../../../../apps/backend/src/autoflow/domain/workflows/run_validation.py) 的 _validate_lifecycle_graph 明确拒绝并行根/同路由扇出；R4 Ruling 已记录共享状态限制 | 共享 Runtime 隔离分支控制状态后再开放；核对分支变量、循环与副作用次数、唯一 End 汇合。不能删除准入检查冒充实现。 |
| 4 | Windows 任意路径工作流文件输出，以及缺少原生所有权证据的孤儿进程清理 | [workflow_artifacts.py](../../../../apps/backend/src/autoflow/infrastructure/filesystem/workflow_artifacts.py) 的 _open_output_parent 等分支返回 ARTIFACT_PLATFORM_UNSUPPORTED / 501；[原生进程边界](../../../../apps/backend/src/autoflow/infrastructure/process/browser_processes.py) 保守保留未知归属 | 实现原生安全路径/句柄和所有权验证后，在 Windows CI 验证取消、原子提交、重启与危险路径拒绝。项目 XLSX 导出和受控运行产物已支持，不能混为一项。 |

这几项包含共享运行时或原生安全边界改动；应先把具体设计、规格与实施切片补齐，再实施。既有安全拒绝保持有效。跨进程人工恢复是当前明确不支持的范围，不因本表而擅自扩大成新的必做功能；原同 Run/存活现场继续与重启中断规则已有证据。

规格依据：[数据流与契约 FLOW-08](../../design/data-flow-and-contracts.md)、[执行与环境 §6、XE-C12/XE-A15](../../design/execution-and-environment.md)、[PM9 总计划](../../../superpowers/plans/2026-09-13-project-management-milestones.md)。当前 14 种项目节点也不等于全部 Studio 节点均可用于项目；其他节点应按已确认业务场景逐个接入，不以目录数量确定完成范围。

## 2. 覆盖台账与真实场景仍未闭合

本轮已把 DATA-LINK-05、FLOW-A16、XE-C12、XE-C18、XE-G04、XE-G05 六项直接匹配的三平台成功链补入台账，状态从 planned 改为 partially_verified；没有将一部分断言升级为整项 verified。

| 类别 | 总数 | verified | partially_verified | planned |
| --- | ---: | ---: | ---: | ---: |
| 功能 | 48 | 4 | 44 | 0 |
| DATA/FLOW/XE 场景 | 178 | 17 | 91 | 70 |
| 执行契约与门禁 | 25 | 1 | 18 | 6 |
| 合计 | 251 | 22 | 153 | 76 |

以上是**证据台账状态，不是功能完成百分比**。229 项尚未完整闭合，不等于 229 项没写代码。特别是多数历史阶段使用隔离执行器，只有直接覆盖的场景才能换成生产证据。

73 条登记指向 5 个不存在的预定文件：test_project_excel.py、test_project_environment_retention.py、test_project_claims.py、test_project_full_scenarios.py、test_project_manual_actions.py。已有测试分散在 Excel services/exports、environment persist/restore/real browser、project input groups/data scheduler、project batch real browser 等文件；必须逐条核对断言，不能仅凭近似文件名自动改为通过。

应优先补的真实场景：

1. DATA-E2E-01/03/06：多输入与显式状态连续任务；人工版本冲突；运行中新增字段、第二表记录和并发旧结构任务。
2. FLOW-A03/04/06/07/13：任务自身版本推进、人工新值保护、写成功响应丢失、后续节点失败仍保留已写效果、同记录释放后可再次领取。
3. XE-A10/12/14/23/24/25：旧环境候选发布冲突、saved_unlinked 仅修复关联、人工继续/到期竞争、混合初始输入与新建记录的 End 关联、禁止替换其他身份、新增字段后关联新记录。
4. DATA-E2E-04/05 与 DATA-SH/SYNC/LIFE：跨项目远端字段写入、发送未知/重启核验、重新授权/绑定和归档时未决操作。

这里列的是需要补齐或核对的**生产端到端证据**，没有断言相关单元/集成测试不存在。完整逐项列表见 [coverage-audit.json](coverage-audit.json)，原文与已有报告见 [coverage.json](../coverage.json)。下一包应先完成这 73 条路径映射和上述非外部依赖场景的断言核对，再按实际缺口补测试或修复。

## 3. 外部与发行证据

- **Sheets 不是从未实网验证。** [PM6 报告](../pm6/verification.json) 已记录 2026-09-19 服务账号、真实 Google REST、真实系统凭据库、拉取/推送确认和解绑删除；已检查对应 live-result.json 的 passed 结果。缺少本次 PM9 代码与打包应用的完整项目→运行→Sheets 推送核验，以及 OAuth 桌面客户端路径。历史验收使用的原生配置文件选择框被测试入口替代，不能证明原生面板。该次结束已删除本机凭据，当前资源授权是否可复用尚未确认；本轮未读取或复用秘密、未触碰远端表。
- **三平台实机安装与原生专项。** CI 已构建 EXE/Intel DMG/ARM DMG 并运行包内应用，但安装向导、系统阻拦提示、原生文件选择/保存、凭据创建/读取/删除和卸载残留没有三平台完整手工证据。按用户要求明确保留待验收。
- **签名/公证。** 当前构建不等于带签名发行。需对应签名身份和公证条件，以及正式产物核验；现有证据不支持宣称完成。
- **用户验收与合并。** PM9 PR #1 仍为草稿，当前工作位于 codex/project-management-pm9-runtime；尚未将 PM9 改动合回 baseline。此前要求的“先合并历史有效代码，再从 baseline 创建 PM9 分支”已完成。这是最终交付收口，不是测试缺陷。

## 4. 性能数据不另造阻塞

Windows 五路万条准备 725733 ms，真实 worker 537 日志/分钟；两个 Mac 对应 104904/85377 ms 和 1642/1539 日志/分钟。各平台固定每分钟 1000 条**合成输入**均读回通过。PM9 原始规格要求的是这一合成负载，并未给 worker 吞吐或万条创建耗时 SLO，因此 Windows 性能是已量化的优化项，不能虚构成“未达到原规定千条 worker 吞吐”的失败。

本轮只修正文档和直接证据对应，不改变已通过 CI 的生产代码，不重跑整套三平台流水线。完成证据闭合与实际功能缺口前，releaseAccepted 继续为 false。
