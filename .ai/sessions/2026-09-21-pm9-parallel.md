# PM9 S3 结构化并行

日期：2026-09-21。状态：confirmed。来源：已批准 S1–S5 计划、实际断言与本机真实 worker。

复用共享 WorkflowRuntime，分支变量/循环/调度状态独立，显式输出在全部成功后合并；冻结 fork/branch/join 和存活父 visit 约束能力。人工排队等待在途工作清空，逐项创建检查点，继续先交接，终结/停止取消队列。未声明并行控制继续拒绝。

发现并修复：直接取消 scheduler 泄漏 operation_task；外层循环执行 fork 时父 scheduler 错把 branch predecessor 当成未完成，导致 join 延迟。留下失败清理、外层循环+局部 break+子调用、两种能力拒绝、准入安全形状和人工排队断言。

验证：154 定向；1103 共享 Runtime/Studio 差分/预算回归；5 个真实 HTTP+worker+browser 并行场景（最终 join 修正后重跑）；ruff、mypy 400 文件通过。真实场景加入三平台 CI。coverage 251 项状态不提升；206 有断言/45 未定位，188 partial/63 planned/0 verified。

后续：S4 Windows 原生边界、S5 多 Run，以及最终完整回归、独立复审、当前 SHA 三平台打包验证。releaseAccepted=false。既有外部授权/签名/实机条件仍单列。
