# 2026-09-30 安卓原型合入 baseline 与分支收敛

状态：confirmed，合并、推送与分支收敛完成；来源：用户明确要求合并到baseline并删除其余所有分支。

- baseline为codex/architecture-baseline，合并前本地53b87b59、远端2cc06c63；Android来源1f015f9f。
- 在既有隔离工作区构建合并树，HEAD暂时detached；没有代码冲突，保留baseline已完成的Laya移除。完整前端454文件/5972项（925.38s）、类型/lint/OpenAPI/build均通过。
- 用户授权涵盖本地及远端其余分支。先完整bundle备份（已verify通过），再合并、原子推送及分支删除；不是把所有历史checkpoint重新合入运行代码。
- 所有既有worktree及未提交内容保留，分支删除后仍可从本地bundle恢复。

[验证结果、分支清单和恢复路径](../../docs/qa/android-management/2026-09-30-baseline-consolidation/README.md)。

完成：合并06fb4978已推送，删除18个其他远端分支及1个本地分支；两端仅保留codex/architecture-baseline。原有未跟踪文件缺失0项。主工作区build exit0，产物已刷新。分支可从已验证bundle恢复；源代码之外的最终提交仅归档审计记录。
