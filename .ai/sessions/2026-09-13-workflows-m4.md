# M4 条件、循环与变量处理实施

日期：2026-09-13；任务：用户明确批准并要求实现完整 M4。

实现继续落在正式 workflows 领域：v2 兼容旧文档，成对控制节点、结构化编译/变量分析、三种循环、只读局部变量、变量操作、只读网页条件、逐执行日志，以及增量产物索引/分页。没有新增运行时依赖，没有改写 M1/M2 迁移，没有接入 WebRPA 运行时。

工程与实际证据集中在 docs/migration/automation-studio-m4-validation.md 和 automation-studio-m4-qa。验收发现的 stdout 堵塞退出延迟、React Flow 尺寸/连接点丢失、重复节点终态标记、v2 普通流程未完成诊断回归均在本任务修复并测试。

后续保持：子流程、错误处理/重试、Debug、录制、双视图/分组和剩余核心能力仍未完成；Windows/macOS Intel 实机验收仍待进行。旧里程碑编号已在正式核心计划顶部标记 superseded。

本任务提交仅包含 M4 代码/文档/证据。其他任务的模型管理记录、通用 project-context、旧 automation 原型及调研材料保持原状。
