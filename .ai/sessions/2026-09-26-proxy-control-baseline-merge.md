# 代理控制合入 architecture-baseline

日期：2026-09-26。状态：confirmed（代码合并与本地检查）；来源：用户明确要求合并到 baseline 并启动。

目标工作树：`/Users/zhangtiancheng/.codex/worktrees/pm9-baseline-merge/autoflow`，目标分支 `codex/architecture-baseline`，合并前 `2cc06c63`；来源 `codex/project-management-pm9@33ae3aa4`。不改写 PM9 工作区原有未提交内容，不推送。

## 冲突处理与衔接

- 保留 baseline 节点级延迟浏览器初始化、共享配置校验、结构化并行分支、项目能力、Windows 进程归属和双 worker 容量；同时保留代理控制、出口验证及取消互斥。
- 项目代理 broker 放在每个 `_Worker` 内，按所属 run/generation/node visit 收发和清理，不能复用单 worker 时代的 manager 全局 broker。
- 代理执行器在执行时读取已初始化浏览器的 probe；项目延迟浏览器 session 持有对应 relay。新增回归先观察缺失 probe 失败，再修复。
- 浏览器资源租约、代理登记和环境目录查询统一使用实际 `run_id`；保留 `run_request_id` 作为启动幂等身份。节点初始化测试先观察两者不一致失败；更新 dispatcher 和环境目录 repository 的同一调用链及相关断言。
- 迁移保持 baseline 的唯一头 `0024_environment_identity`；PM9 补回的六个旧迁移与 baseline 相同，不降级、不 stamp。
- 同步保留来源分支已提交的模型反馈自动消失修复；不纳入 PM9 的未提交清单或验收文件修改。

## 验证

- 最终后端定向组：108 passed / 4 skipped / 1 既有 Starlette 警告，36.07 秒。覆盖 dispatcher、两条真实 worker 管道、两个并发项目 worker 的代理请求/结果隔离、延迟浏览器、代理执行器、环境目录、项目启动和原 worker 单测。
- 合并初次范围组 197 passed / 4 failed / 4 skipped；4 个失败为资源 ownership 测试仍按旧 request ID 查租约，已随实际 run ID 契约更新，包含在最终通过组。未把重复测试数量相加。
- 原代理 worker 成功路径测试人为配置 0.5 秒退出预算，复现两次正常进程收尾超时；该测试验证 RPC 而非亚秒退出，改用生产默认 3 秒，未改变生产超时。最终真实 worker 测试通过。
- 前端目录、字段、保存回读、面板、代理配置与倒计时：1277 passed（5 文件）。typecheck、lint、build（32.48 秒）、openapi:check、结构 4 项、改动 Python Ruff 均通过。
- mypy 当前环境报告 65 个诊断（11 文件）。将合并前 HEAD 源码提取到独立临时目录，以同一虚拟环境检查也得到同样 65 个；去除路径前缀和行号后逐项完全一致。未声称全后端 mypy 全绿，也未顺手改 Android 既有问题。
- 停止 PM9 开发版后，保存当前工作区 SQLite 备份 `data/backups/pre-proxy-baseline-20260926.sqlite3`。在副本执行 baseline 迁移至 0024，81 张已有表的全部原列值摘要保持不变，integrity_check=ok。原库由正常 baseline 启动执行已验证迁移。
- 四项跳过是未提供真实浏览器环境的用例；真实供应商切换、Windows、打包仍未验收。

本机日志：`/tmp/autoflow-baseline-merge-final-backend.txt`、`/tmp/autoflow-baseline-merge-frontend.txt`、`/tmp/autoflow-baseline-before-mypy.txt`、`/tmp/autoflow-baseline-merge-mypy.txt`。运行 UI 结果将在启动后追加。
