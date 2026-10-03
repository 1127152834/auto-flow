# 整改计划索引

日期：2026-09-30；修订：r2。状态：confirmed（方向和本轮文档修订），M0 退出验收接近完成（缺同提交 ARM+Windows 全绿确认；Intel 已不再支持），M1 代码已并入默认分支、待同环境证据与 G2 失败原因占比追查，M2–M6 未开始（用户决定后续在 Claude Code 中继续）。正式正文在 docs/superpowers；旧“已原型验证、M0 可直接执行”标记 superseded。M2–M6 在前置接口和测量完成后细化、审查，不预先展开整套实现。

| 里程碑 | 规格 | 计划 | 粒度与依赖 |
| --- | --- | --- | --- |
| M0 基准与守门 | [规格](../../docs/superpowers/specs/2026-09-30-remediation-m0-baseline-guardrails.md) | [计划](../../docs/superpowers/plans/2026-09-30-remediation-m0-baseline-guardrails.md) | 步骤级；Task1–9本地实现与独立评审完成；101行黄金通过，全量本地回归通过，远端CI仍待验收 |
| M1 止血 | [规格](../../docs/superpowers/specs/2026-09-30-remediation-m1-stop-silent-failures.md) | [计划](../../docs/superpowers/plans/2026-09-30-remediation-m1-stop-silent-failures.md) | 步骤级；代码已并入默认分支（2026-10-02），golden 30 行已跑（G2 failure_reason_ratio 0.0，2026-10-02 查明为父进程丢弃节点原因并已修复，待重跑 golden 确认）；待 Mac 基准（AC1-09/10/13）后才能标 done |
| M2A/B/C 可靠性、数据契约、扩展 | [规格](../../docs/superpowers/specs/2026-09-30-remediation-m2-business-model-reliability.md) | [计划](../../docs/superpowers/plans/2026-09-30-remediation-m2-business-model-reliability.md) | 任务级；分切片细化审查。2026-10-02 M2A Task 1 已细化（[步骤级](../../docs/superpowers/plans/2026-10-02-remediation-m2a-task1-ledger.md)）并本机实现：台账规则/表/仓储、主处理输入与启动门禁（未推送、未经 CI）；2026-10-03 Task 2a（副作用与失败分类）、Task 3（终态投影与人工核实）本机完成；Task 4（领取模式）、2b（出错策略）、5、6 未开始 |
| M3 吞吐与性能 | [规格](../../docs/superpowers/specs/2026-09-30-remediation-m3-throughput.md) | [计划](../../docs/superpowers/plans/2026-09-30-remediation-m3-throughput.md) | 任务级；M2A/B 与原生基准后 |
| M4 身份模型 | [规格](../../docs/superpowers/specs/2026-09-30-remediation-m4-identity.md) | [计划](../../docs/superpowers/plans/2026-09-30-remediation-m4-identity.md) | 任务级；M3 资源接口稳定后 |
| M5A/B/C/D 体验 | [规格](../../docs/superpowers/specs/2026-09-30-remediation-m5-experience.md) | [计划](../../docs/superpowers/plans/2026-09-30-remediation-m5-experience.md) | 任务级；分别依赖 M1、M2A/B、M4 |
| M6 收敛与清理 | [规格](../../docs/superpowers/specs/2026-09-30-remediation-m6-convergence.md) | [计划](../../docs/superpowers/plans/2026-09-30-remediation-m6-convergence.md) | 任务级；兼容与迁移门禁通过后 |

来源与验证：[总纲](../../docs/superpowers/specs/2026-09-30-remediation-roadmap.md)、[修订记录](../sessions/2026-09-30-remediation-plan-revision.md)。M2C 独立交付不阻塞 M3；M5D 视觉完善不阻塞 M5B 业务闭环。历史 QA 清理独立于 M0。原 13 周估算已 superseded，M0/M1 退出后重估。

后续计划（独立于整改、依赖其成果，状态 proposed）：执行环境扩展 E1–E6 与 iOS 决定——规格 docs/superpowers/specs/2026-09-30-execution-environments-design.md，计划 docs/superpowers/plans/2026-09-30-execution-environments-milestones.md，决定 .ai/decisions/2026-09-30-execution-environments.md。E1 在 M1 后、E2 在 M4 后、E3–E5 在 M6 后细化。

接手入口：[M0–M6 交接文档](../sessions/2026-09-30-remediation-handoff.md)。当前验收状态、远端运行编号、已知缺口及接手命令以交接快照和实时 Git/CI 为准。
