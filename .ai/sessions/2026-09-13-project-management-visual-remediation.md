# 项目管理视觉整改规格与实施启动

2026-09-13；confirmed（执行事实），用户本轮要求先写规格/详细计划，然后开始实施。

规格和计划分别位于docs/superpowers/specs/2026-09-13-project-management-visual-remediation.md、plans同名文件。要求真实Electron+后端端到端，原图并排和应用回归双层视觉验证；E1用户路径与API/桥/合成故障证据分开。

VR0独立审查修复四项后通过759b815。VR1目录组件3bc17f1和长名修复7b22b25已实施。定向28测试、typecheck/build通过；真实目录有界E2E最终run-8BvVYs。系统窗口高度限制使自动视觉使用明确记录CDP viewport；曾200%重复缩放的run-3tG4Kd不作合格证据，最终校验inner720×512/DPR2。

完整R1仍未完成：VR2数据层级、VR3查询、VR4通知、VR5完整E2E/电脑工具与原生视口验收待做；用户验收pending，不自动R2。原型/实图评分不是像素计算。主项目/旧项目及原无关QA未改。
