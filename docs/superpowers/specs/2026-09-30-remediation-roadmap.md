# AutoFlow 整改里程碑总纲

- 日期：2026-09-30
- 状态：proposed，待用户审批。本文件及各里程碑规格属于架构级改动，按 `AGENTS.md` 须经用户确认后才进入实现。
- 上位方案：[AutoFlow 整改方案](2026-09-30-autoflow-remediation-proposal.md)
- 评审依据：[系统设计评审](../../qa/2026-09-30-remediation-reviews/system-design-review.md)、[前端交互评审](../../qa/2026-09-30-remediation-reviews/frontend-interaction-review.md)
- 基线提交：`ea2cc5b`（分支 `codex/architecture-baseline`）

## 1. 结论

整改拆成 7 个里程碑（M0–M6），每个里程碑都能独立交付、独立验收，并让系统比上一个里程碑更可用。里程碑按"先能测量 → 先消除静默失效 → 再补业务模型 → 再提吞吐 → 再做身份 → 最后收敛"的顺序推进；前端体验重构（M5）从 M1 之后开始与后端并行。

计划采用滚动式细化：**M0、M1 的实施计划已细化到步骤级**，可以直接执行；M2–M6 的实施计划目前是任务级（文件、接口、测试清单、验收），在上一个里程碑通过退出评审后，再按 `superpowers:writing-plans` 细化为步骤级。这样后面的计划能吸收前面里程碑的实测数据，避免提前写死错误细节。

## 2. 里程碑一览

| 里程碑 | 目标 | 规格 | 实施计划 | 计划粒度 | 估算 |
| --- | --- | --- | --- | --- | --- |
| M0 基准与守门 | 先能测量，防止问题继续增加 | [规格](2026-09-30-remediation-m0-baseline-guardrails.md) | [计划](../plans/2026-09-30-remediation-m0-baseline-guardrails.md) | 步骤级 | 第 1 周 |
| M1 止血 | 消除静默失效：不生效的选项、被吞掉的错误、已处理失败仍算失败、写死的并发、录制不能运行 | [规格](2026-09-30-remediation-m1-stop-silent-failures.md) | [计划](../plans/2026-09-30-remediation-m1-stop-silent-failures.md) | 步骤级 | 第 2–3 周 |
| M2 业务模型与可靠性 | 每一行数据的处理结果可预期：处理台账、失败分类、批次熔断、流程签名、定时触发 | [规格](2026-09-30-remediation-m2-business-model-reliability.md) | [计划](../plans/2026-09-30-remediation-m2-business-model-reliability.md) | 任务级 | 第 4–6 周 |
| M3 吞吐与性能 | 万级任务稳定：SQL 下推领取、事件分级、进程池、会话复用、环境瘦身 | [规格](2026-09-30-remediation-m3-throughput.md) | [计划](../plans/2026-09-30-remediation-m3-throughput.md) | 任务级 | 第 6–8 周 |
| M4 身份模型 | 每个账号独立且一致：唯一种子、粘性代理、地区一致性校验 | [规格](2026-09-30-remediation-m4-identity.md) | [计划](../plans/2026-09-30-remediation-m4-identity.md) | 任务级 | 第 8–10 周 |
| M5 体验重构 | 按业务语言操作：数据标签、写回表单、导航、批次监控、Studio 布局、设计系统 | [规格](2026-09-30-remediation-m5-experience.md) | [计划](../plans/2026-09-30-remediation-m5-experience.md) | 任务级 | 第 3–11 周（并行） |
| M6 收敛与清理 | 只留一套实现：合并执行栈、节点契约、节点目录精简、删除旧路径 | [规格](2026-09-30-remediation-m6-convergence.md) | [计划](../plans/2026-09-30-remediation-m6-convergence.md) | 任务级 | 第 11–13 周 |

估算按后端 1 人、前端 1 人；以退出标准为准，不达标不进入下一里程碑。

## 3. 依赖关系

```mermaid
flowchart LR
  M0[M0 基准与守门] --> M1[M1 止血]
  M1 --> M2[M2 业务模型与可靠性]
  M2 --> M3[M3 吞吐与性能]
  M3 --> M4[M4 身份模型]
  M1 --> M5[M5 体验重构]
  M2 -. 流程签名 / 台账接口 .-> M5
  M4 -. 身份对象 .-> M5
  M4 --> M6[M6 收敛与清理]
  M5 --> M6
```

- M5 中的"数据绑定体验"（字段标签、写回表单、End 勾选）依赖 M2 的流程签名接口；"批次监控"依赖 M2 的台账；"身份列表"依赖 M4。M5 内部按这些依赖排序（见 M5 规格）。
- M3 的 SQL 下推领取依赖 M2 的台账表结构（台账字段参与筛选）。

## 4. 每个里程碑的通用完成定义

1. 规格中的每条验收标准（AC）都有对应的自动化测试或基准数据证明。
2. M0 建立的黄金场景基准在该里程碑结束时重跑，指标不回退；该里程碑承诺改善的指标达到目标值。
3. M0 建立的守门检查（ratchet）在 CI 通过，且存量数字只减不增。
4. 按 `AGENTS.md` 更新 `docs/PROJECT_STRUCTURE.md`、`.ai/decisions`、`.ai/plans`，并运行与范围匹配的 lint、类型检查、测试、构建。
5. 退出评审：由一个未参与实现的评审者（新会话或子代理）对照规格检查整个里程碑分支，给出通过/不通过。

## 5. 本方案将替代的既有决定（审批后生效）

| 既有决定 | 位置 | 替代为 | 所在里程碑 |
| --- | --- | --- | --- |
| 全局运行容量只允许 1 或 2，"不提高 core 的两个槽上限" | `application/workflows/dispatcher.py:133`；`docs/superpowers/plans/2026-09-26-parameter-batch-concurrency.md` 全局约束 | 容量按机器配置，执行名额与存活浏览器分开计数 | M1 |
| 人工等待占用执行名额 | `tests/integration/test_workflow_dispatch.py:871` 断言 | 人工等待只占存活浏览器名额 | M1 |
| 错误分支接住的失败仍使运行失败（沿用 WebRPA） | `application/workflows/runtime.py:333`；`test_b3_control_flow_runtime_contract.py` | 已处理失败不决定运行结果；导入的 WebRPA 文档可开启兼容模式 | M1 |
| 没有批内已消费集合，失败历史不加入排除条件 | `docs/project-management/design/execution-and-environment.md` §4.1、XE-A21/A22；`.ai/decisions/2026-09-12-project-data-workflow-semantics.md` | 新增处理台账，默认"未成功处理"模式；原语义保留为"循环复用"模式 | M2 |
| 运行时可增删改字段 | `domain/project_data/capabilities.py` 的 addField/modifyField/deleteField | 表结构只在设计期修改 | M2 |
| 指纹种子属于浏览器配置 | `application/profiles/service.py:30` | 种子属于身份，全局唯一 | M4 |

## 6. 需要用户确认的决定

1. 是否批准以上替代关系（第 5 节）。
2. M0 中是否清理 git 历史里的约 3,200 张 QA 截图（会改写历史，需要所有协作者重新克隆）；默认只阻止新增，不改写历史。
3. M4 身份迁移时，多个环境共用同一种子的情况是否默认保留原种子（推荐保留，由用户逐个决定是否重新生成）。
4. 冻结范围（Android/iOS 模拟器管理、桌面触发器、Google Sheets 双向同步扩展）是否同意。

## 7. 分支与交付约定

- 每个里程碑一个分支：`remediation/m<N>-<slug>`，从上一个里程碑合并后的主线切出；每个任务一次提交，提交信息说明行为变化。
- 功能开关：台账领取模式、新错误语义、身份模型、会话复用、新 Studio 布局、标签输入框。每个开关在黄金场景连续 7 天达标后默认开启，一个版本后删除旧路径（M6）。
- 数据库迁移沿用 Alembic，文件名前缀 `rm<N>_`，只做向前兼容的增量迁移；破坏性清理放在 M6。
