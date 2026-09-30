# 最近代码合入 architecture baseline

日期：2026-09-30。状态：confirmed。来源：用户本轮要求“先整理、分析后，把最近修改的所有代码合并到 baseline”；本地分支祖先关系、三方差异、代码与测试验证。

## 范围与取舍

- 目标分支：`codex/architecture-baseline`，合并前 `3550cd738414f931e4af8469c412d574bc44d6c9`。
- 主集成分支：`codex/project-management-pm9`，合并前 `270053df9af088a280ec16eaa943c3361afcf948`。当前工作区先完成 baseline -> PM9 的真实 merge，验证后再把 baseline 工作区快进到最终集成提交，以保留双方历史。
- 第二阶段有效增量：`codex/remove-project-legacy-executor@a32ad2e2`。仅保留退役临时项目浏览器执行器、统一 production registry 的架构意图；不得覆盖 2026-09-28 以后已修复的 End、project data、trace、敏感输出、停止清理和输入追加语义。
- 明确排除：`codex/m6-unfinished-checkpoint-20260913`、`codex/studio-before-removal-20260913`，以及本机 `.aoci/`、`.codegraph/`、`.codex/`、临时 QA evidence、备份文件和无关未跟踪会话记录。
- 不推送远端，不发布，不删除上述未跟踪数据。

## 合并提交

- 第一阶段真实 merge：`f670145fd872ced1b603e72ab7b7b31b77b0b511`，父提交为 PM9 `270053df9af088a280ec16eaa943c3361afcf948` 与 architecture baseline `3550cd738414f931e4af8469c412d574bc44d6c9`。
- 第二阶段真实 merge：合入 `codex/remove-project-legacy-executor@a32ad2e2c3731da6046138d7dd8c414c2a44e9c6`；最终 merge 提交同时承载本记录，提交哈希由 Git 在提交完成后确定，并作为 `codex/architecture-baseline` 的最终本地指针核验。

## 合并后的 canonical 约束

- `project_data` 唯一协议为 `operation + tableGrant + bindingProjectId/currentInputId + variableName`；删除并拒绝并行的 `action + binding + resultVariable` 方言。授权按 frozen node/visit 二次收窄，写回执不泄露 values，依赖工作流中的 project data 明确拒绝。
- Project End 走 frozen `project_end` 节点、`recordTargets`、`endOperationId` 与 durable accept/finalize/recover。活动任务不能直调 EnvironmentService 绕过 worker；accept 后必须进入确定终态，发布安全栅栏失败也不得留下悬空操作。
- 数据库迁移保持单 head：`0025_merge_studio_credential_environment`。
- 平台差异仍位于适配器；Android/Windows 类型修复与 worker 停止修复不向业务层增加平台判断。

## 最终验证

- 第二阶段删除 `workflow_executor.py`、`WorkflowExecutor`、`_LegacyBrowserNode` 和 legacy registry 分支，Project Graph 统一使用 production registry；源码引用扫描结果为 0。保留当前 End、project data、trace、敏感输出、停止清理和输入追加语义，未接受旧分支中已过时的测试断言。
- 第二阶段定向回归：`446 passed, 7 skipped, 1 warning`，覆盖 worker、Project Graph、Project End、project data、浏览器会话/协议、trace、恢复与变量差异一致性。
- 后端最终全量：`5267 passed, 137 skipped, 2 warnings`。第一阶段首次运行发现 20 个合并回归；按 6 个共同根因修复，第二阶段真实 merge 后再次全量通过。
- 后端静态门禁：Ruff 通过；普通 mypy `550 source files` 通过；strict gate `debt=893, baseline=893, new=0`。本次只从 reviewed baseline 删除 148 条已经解决的旧诊断，没有新增豁免。
- 后端构建：第二阶段完成后再次运行 `npm run backend:build` 成功；PyInstaller 产物生成到 `apps/backend/dist`。第三方可选 GPU、Windows/Linux 与转换器 hook 仅产生 warning。
- 数据库：Alembic metadata 无待生成操作；heads 为 `0025_merge_studio_credential_environment (head)`。
- 前端：`5970/5970` tests、lint、typecheck、build 通过。构建只有既有动态导入/注解 warning。
- 仓库门禁：OpenAPI check、根脚本 `111/111`、结构测试 `4/4` 通过；project protocol 定向套件 `235 passed`。
- PM9 覆盖映射检查：`251 mappings valid`；这是覆盖引用完整性检查，不冒充发布验收。
- 当前机器未设置 `AUTOFLOW_TEST_CLOAKBROWSER`，真实 CloakBrowser/外部环境用例按条件 skip；不能把这些 skip 表述为真实浏览器验收通过。CI 使用 Node 22，本机为较新的 Node 版本，前端本机构建通过但仍以 CI 为最终平台证据。
