# M6 收敛与清理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **本计划为任务级。** M4、M5 合并且各功能开关在黄金场景连续 7 天达标后，细化为步骤级并完成审查后执行。本里程碑包含破坏性数据库清理，执行前必须再次获得用户明确同意。

**Goal:** 完成剩余执行入口与历史迁移，再按数据门禁删除旧路径；不是“只做减法”。

**Architecture:** 扩展M1共用错误转换为完整事件转换，再把 Studio 运行入口切到派发器，最后迁移历史并删除旧栈；M2B输出契约已供M5使用，本阶段补全覆盖并迁移旧变量别名；删除按"开关旧分支 → 旧组件 → 旧数据列"的顺序进行，应用旧路径可在兼容窗口回切；破坏性数据清理后的回退依赖已验证备份和停止写入窗口，不能无损回退升级后新写入。

**Tech Stack:** 同前；Alembic 破坏性迁移 `rm6_*`（先备份、在副本上重放验证）。

**Spec:** [docs/superpowers/specs/2026-09-30-remediation-m6-convergence.md](../specs/2026-09-30-remediation-m6-convergence.md)

## Global Constraints

- 旧栈在新栈通过全部 Studio 调试用例前不删除。
- 隐藏的节点保留执行器，旧文档可打开、可运行。
- 破坏性迁移前自动备份，并在备份副本上完整重放成功后才在真实工作区执行；需用户明确同意。
- 删除功能开关后全部测试、构建、打包冒烟通过。

## Review Focus

1. **Studio 调试断点 / 单步在新引擎上的时序**：与旧栈对照测试逐事件比较（Task 2）。
2. **旧文档引用了被隐藏节点的输出变量名**：输出契约迁移为"节点名.输出名"时保留别名直到未迁移数据清零及旧导入转换通过，不能只按经过一个版本删除（Task3/6）。
3. **表达式与旧计算节点结果不同**（数值精度、日期时区）：一键转换前后对照测试（Task 4）。
4. **历史运行迁移中断**：迁移可重入，按批次提交（Task 2）。
5. **删除旧列后回退**：回退路径是恢复备份，文档写明（Task 6）。

---

### Task 1: 补全共用事件转换（复用M1）
- Files: `application/workflows/event_translation.py`（扩展M1已抽取错误转换，先盘点独立Studio与项目内试跑实际入口）、两条路径改用它。
- Tests: 同流程、相同executionMode/冻结输入/运行选项下两入口标准化节点事件一致；另测previewWrites与realWrites的预期差异、End保存拒绝和无真实写入事实。

### Task 2: Studio 运行切到统一派发器
- Files: Studio 运行入口 → `WorkflowRunDispatcher`（调试标志；仅独立且无项目绑定的调试可无批次，项目数据试跑保留单任务批次/Task能力边界）；断点 / 单步 / 变量查看作为运行选项；历史Studio运行迁移（元数据+日志/产物索引+runId/artifactId及路径/事件关联，可重入）。先识别run-project-once.ts已走项目批次的路径，复用而非复制新实现。
- Tests: 全部Studio调试用例在新引擎通过；断点/单步/取消/人工等待/凭据隔离对照；历史截图、文件、trace及变量诊断在迁移后真实查询下载；中断恢复与重复迁移不产生重复索引。

### Task 3: 节点输出契约
- Files: 执行器声明 `outputs`；`project_graph.py` 删除配置键猜测；编辑器按全部有效路径必然定义区分必有/条件输出（含分支汇合、零次循环、错误边）；预检报告未生成输出；稳定nodeId/outputKey来自M2B，显示名可改；旧别名保留到兼容门禁通过。
- Tests: 每个执行器声明/预检与M2B契约一致；分支汇合、零次循环、错误边、改名、旧别名迁移；不能以“可达上游”充当“一定产生”。

### Task 4: 表达式与纯计算节点转换
- Files: `{= ...}` 表达式（基于 `safe_expr`）与函数库；"一键转换为表达式"。
- Tests: 函数库单元测试；转换前后结果对照。

### Task 5: 节点目录精简与冻结范围
- Files: 模块目录只显示核心约 50 个；桌面触发器、系统操作、局域网共享、模拟器管理移入"实验功能"并在批量运行中禁用；Sheets 双向同步停止扩展（界面标注）。
- Tests: 目录清单测试（更新"213 + 扩展"清单为新的核心清单）；批量运行拒绝实验节点。

### Task 6: 删除旧路径与开关
- Files: 旧执行栈、`workflows/components/controls`、`webrpa.css`、phosphor、`PROJECT_INPUTS[...]` 解析、各功能开关旧分支；`rm6_drop_legacy.py`（旧 Studio 运行表、记录"当前环境"列）。
- 删除前门禁：扫描所有持久文档、仍需执行的冻结内容与迁移未决项；无未迁移引用且旧文件导入/跳版本升级可转换；历史产物可访问。未通过时保留最小解析器或只读表，不关闭对应AC。Tests：全量/构建/原生打包、迁移中断重入、备份恢复、无写入清理窗口；恢复备份的写入损失边界明确。

### Task 7: 文档收敛与最终验收
- 按整改方案 N2 改写仍有效的设计文档；过时设计与计划标记 superseded；守门项转为 lint 或删除。
- AC6-01 至 AC6-06；黄金场景 G1–G4 连续 7 天达标；独立退出评审。
