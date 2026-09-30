# M6 收敛与清理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **本计划为任务级。** M4、M5 合并且各功能开关在黄金场景连续 7 天达标后，细化为步骤级并经用户确认再执行。本里程碑包含破坏性数据库清理，执行前必须再次获得用户明确同意。

**Goal:** 只留一套实现：统一执行引擎、节点输出契约、精简节点目录、删除旧路径与功能开关。

**Architecture:** 先让 Studio 与批量共用事件转换，再把 Studio 运行入口切到派发器，最后迁移历史并删除旧栈；节点输出契约由执行器声明驱动编辑器提示与预检；删除按"开关旧分支 → 旧组件 → 旧数据列"的顺序进行，每一步都可回退到上一个发布。

**Tech Stack:** 同前；Alembic 破坏性迁移 `rm6_*`（先备份、在副本上重放验证）。

**Spec:** [docs/superpowers/specs/2026-09-30-remediation-m6-convergence.md](../specs/2026-09-30-remediation-m6-convergence.md)

## Global Constraints

- 旧栈在新栈通过全部 Studio 调试用例前不删除。
- 隐藏的节点保留执行器，旧文档可打开、可运行。
- 破坏性迁移前自动备份，并在备份副本上完整重放成功后才在真实工作区执行；需用户明确同意。
- 删除功能开关后全部测试、构建、打包冒烟通过。

## Review Focus

1. **Studio 调试断点 / 单步在新引擎上的时序**：与旧栈对照测试逐事件比较（Task 2）。
2. **旧文档引用了被隐藏节点的输出变量名**：输出契约迁移为"节点名.输出名"时保留别名一个版本（Task 3）。
3. **表达式与旧计算节点结果不同**（数值精度、日期时区）：一键转换前后对照测试（Task 4）。
4. **历史运行迁移中断**：迁移可重入，按批次提交（Task 2）。
5. **删除旧列后回退**：回退路径是恢复备份，文档写明（Task 6）。

---

### Task 1: 共用事件转换
- Files: `application/workflows/event_translation.py`（从 `project_graph.py` 与 `workflow_worker.py` 抽出）、两条路径改用它。
- Tests: 同一流程两条路径事件序列一致（对照测试）。

### Task 2: Studio 运行切到统一派发器
- Files: Studio 运行入口 → `WorkflowRunDispatcher`（调试标志、无批次）；断点 / 单步 / 变量查看作为运行选项；历史 Studio 运行迁移（元数据 + 日志索引，可重入）。
- Tests: 全部 Studio 调试用例在新引擎通过；迁移重入测试。

### Task 3: 节点输出契约
- Files: 执行器声明 `outputs`；`project_graph.py` 删除配置键猜测；编辑器变量提示按可达上游过滤；预检报告未生成输出；旧变量名别名一个版本。
- Tests: 每个执行器有输出声明；预检发现引用未生成输出；编辑器提示测试。

### Task 4: 表达式与纯计算节点转换
- Files: `{= ...}` 表达式（基于 `safe_expr`）与函数库；"一键转换为表达式"。
- Tests: 函数库单元测试；转换前后结果对照。

### Task 5: 节点目录精简与冻结范围
- Files: 模块目录只显示核心约 50 个；桌面触发器、系统操作、局域网共享、模拟器管理移入"实验功能"并在批量运行中禁用；Sheets 双向同步停止扩展（界面标注）。
- Tests: 目录清单测试（更新"213 + 扩展"清单为新的核心清单）；批量运行拒绝实验节点。

### Task 6: 删除旧路径与开关
- Files: 旧执行栈、`workflows/components/controls`、`webrpa.css`、phosphor、`PROJECT_INPUTS[...]` 解析、各功能开关旧分支；`rm6_drop_legacy.py`（旧 Studio 运行表、记录"当前环境"列）。
- Tests: 全量测试、构建、打包冒烟；迁移在备份副本上重放。

### Task 7: 文档收敛与最终验收
- 按整改方案 N2 改写仍有效的设计文档；过时设计与计划标记 superseded；守门项转为 lint 或删除。
- AC6-01 至 AC6-06；黄金场景 G1–G4 连续 7 天达标；独立退出评审。
