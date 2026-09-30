# 整改计划索引

日期：2026-09-30；修订：r2。状态：confirmed（方向和本轮文档修订），M0 实施中，其余未开始。正式正文在 docs/superpowers；旧“已原型验证、M0 可直接执行”标记 superseded。M2–M6 在前置接口和测量完成后细化、审查，不预先展开整套实现。

| 里程碑 | 规格 | 计划 | 粒度与依赖 |
| --- | --- | --- | --- |
| M0 基准与守门 | [规格](../../docs/superpowers/specs/2026-09-30-remediation-m0-baseline-guardrails.md) | [计划](../../docs/superpowers/plans/2026-09-30-remediation-m0-baseline-guardrails.md) | 步骤级；Task1已实现，阶段验收未完成 |
| M1 止血 | [规格](../../docs/superpowers/specs/2026-09-30-remediation-m1-stop-silent-failures.md) | [计划](../../docs/superpowers/plans/2026-09-30-remediation-m1-stop-silent-failures.md) | 步骤级；M0 退出后 |
| M2A/B/C 可靠性、数据契约、扩展 | [规格](../../docs/superpowers/specs/2026-09-30-remediation-m2-business-model-reliability.md) | [计划](../../docs/superpowers/plans/2026-09-30-remediation-m2-business-model-reliability.md) | 任务级；分切片细化审查 |
| M3 吞吐与性能 | [规格](../../docs/superpowers/specs/2026-09-30-remediation-m3-throughput.md) | [计划](../../docs/superpowers/plans/2026-09-30-remediation-m3-throughput.md) | 任务级；M2A/B 与原生基准后 |
| M4 身份模型 | [规格](../../docs/superpowers/specs/2026-09-30-remediation-m4-identity.md) | [计划](../../docs/superpowers/plans/2026-09-30-remediation-m4-identity.md) | 任务级；M3 资源接口稳定后 |
| M5A/B/C/D 体验 | [规格](../../docs/superpowers/specs/2026-09-30-remediation-m5-experience.md) | [计划](../../docs/superpowers/plans/2026-09-30-remediation-m5-experience.md) | 任务级；分别依赖 M1、M2A/B、M4 |
| M6 收敛与清理 | [规格](../../docs/superpowers/specs/2026-09-30-remediation-m6-convergence.md) | [计划](../../docs/superpowers/plans/2026-09-30-remediation-m6-convergence.md) | 任务级；兼容与迁移门禁通过后 |

来源与验证：[总纲](../../docs/superpowers/specs/2026-09-30-remediation-roadmap.md)、[修订记录](../sessions/2026-09-30-remediation-plan-revision.md)。M2C 独立交付不阻塞 M3；M5D 视觉完善不阻塞 M5B 业务闭环。历史 QA 清理独立于 M0。原 13 周估算已 superseded，M0/M1 退出后重估。
