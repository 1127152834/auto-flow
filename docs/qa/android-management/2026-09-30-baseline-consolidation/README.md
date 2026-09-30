# 2026-09-30 baseline 合并与分支收敛

状态：confirmed，合并、原子推送、分支删除及实地引用核验均已完成。来源：用户明确要求“合并到 baseline 分支，并且删除其余所有分支”。

- 目标：`codex/architecture-baseline`（本地起点53b87b59，远端起点2cc06c63）。
- 合入：`codex/android-prototype-fidelity@1f015f9f`。在隔离工作区构建合并树，无冲突；Laya移除保留。
- 合并前：2个本地分支，19个远端分支；origin/HEAD指向baseline。
- 已执行顺序：验证合并树→本地主工作区fast-forward→原子推送baseline及删除其余18个远端分支→删除1个本地来源分支。每个远端变更均使用预期SHA栅栏，避免删除并发新提交。
- 工作区保留detached及已有未提交内容；不清理用户文件。
- 完整历史备份：`/Users/zhangtiancheng/Documents/projects/autoflow/.git/branch-backups/20260930-135450/all-branches.bundle`，786829143字节，`git bundle verify`通过；引用清单见branch-inventory-before.json。旧M6及旧Studio checkpoint各1个不在原baseline的提交也已备份，不额外复活这些退役实现。

## 验证

| 命令 | 实际结果 | 日志 |
|---|---|---|
| `npm --workspace @autoflow/desktop test -- --maxWorkers=2` | 454文件、5972项通过；925.38s，exit0 | frontend.log |
| `npm run typecheck` | exit0，无诊断 | typecheck.log |
| `npm run lint` | exit0，无诊断 | lint.log |
| `npm run openapi:check` | exit0，生成类型一致 | openapi.log |
| `npm run build` | exit0，renderer 4m10s；既有依赖PURE注释警告 | build.log |

相较原型分支455文件/5977项，少的1文件/5项来自已合入baseline的Laya实验室移除；没有跳过测试。日志仅规范化行尾空白。本次为Git整合，不修改业务契约和数据库。原安卓在线实例控制因Lima停止/ADB无设备的验收状态不改变。

## 最终 Git 结果

- 代码合并提交：06fb4978ebcbeb2f92f45953c44d7fe0f6314bf4（parents:53b87b59、1f015f9f）；本地主工作区以fast-forward更新。
- 原子推送exit0：远端baseline由2cc06c63推进到06fb4978，同时删除18个其他远端分支；实际输出见remote-atomic-push.log。
- `git branch -d codex/android-prototype-fidelity` exit0，删除唯一其他本地分支。
- `git fetch origin --prune`、`git branch -avv`、`git ls-remote --heads origin`核验：本地和远端均仅有codex/architecture-baseline；origin/HEAD为其符号引用，不是额外分支。
- branch-inventory-after.txt记录分支收敛后、最终审计文档提交前的引用快照；随后的提交只归档本报告，代码不变。
- 原有未跟踪文件清单缺失0项；全部旧worktree保留，来源worktree处于detached HEAD，没有强删目录。
- 主工作区另执行 `npm run build` exit0（renderer 1m12s），当前主工作区out产物已刷新，见build-main.log。没有重启用户应用。
- 当前Git收敛无阻塞；此前安卓在线控制等设备验收限制仍保留，不因Git合并自动通过。

## 恢复方法

可先 `git bundle list-heads <上述bundle路径>` 查看原引用，再 `git fetch <bundle路径> <原引用>:refs/heads/<恢复分支名>` 恢复指定分支。备份保存在本机.git下，不推送到远端。
