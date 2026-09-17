# 有效分支归并决定

- 日期：2026-09-17
- 状态：confirmed
- 来源：用户要求分析并合并其余未合并分支，随后确认“所有有效能力”与能力整合加树不变归并策略
- 验证方式：逐分支差异审计、能力矩阵、聚焦测试、全量发布验证及 Git 祖先关系检查

## 决定

目标分支为 `codex/architecture-baseline`。归并使用两层策略：需要的新能力以普通提交或真实 merge 接入；已被当前更新代码覆盖的历史分支使用 `git merge -s ours --no-ff` 记录语义归并。树不变归并前后必须比较 tree object，不能用它掩盖未经审计的能力缺口。

纳入的源分支及审计时 tip：

| 分支 | Tip | 处理 |
| --- | --- | --- |
| `codex/project-management-pm3` | `2bac1b14` | PM4 的祖先，经真实 PM4 merge 纳入 |
| `codex/project-management-pm4` | `fbda6f17` | `a5c5ed98` 真实 merge，冲突按当前 Studio 与命名空间隔离处理 |
| `codex/project-management-pm5` | `fbda6f17` | 与 PM4 同 tip，无额外代码 |
| `codex/android-workflow-handoff` | `f573a44d` | `f4c76bb4` 移植有效设备能力，`18711f3f` 树不变归并 |
| `codex/ui-controls-plan` | `1fb58e18` | `5ea7880c` 移植缺失控件，`0c2df10f` 树不变归并 |
| `codex/global-table-system` | `2a29ac0d` | 修复当前表格回归后由 `a0d9c135` 树不变归并 |
| `codex/proxy-management` | `0ad2fd2a` | 当前代码已覆盖且更完整，由 `1d44b137` 树不变归并 |

`codex/proxy-live@17e08705` 和 `codex/proxy-remote-controls@dc49d882` 在归并前已是目标历史的一部分，无需新增 reconciliation merge。

## 冲突与排除规则

- 当前 Studio 运行时是权威实现。项目管理运行表改用 `project_workflow_*`，通过 `0013_merge_project_runtime.py` 汇合迁移图，避免覆盖 Studio 表和模型。
- Android 设备管理与手动控制有效；源分支的工作流 worker、自动分配和接管绑定已退役运行时，保持明确的 typed unavailable 响应，等待独立适配当前执行契约。
- UI 保留当前 option-based 控件 API。无生产调用且依赖已移除 `react-aria-components` 的 Combobox 不接入；旧 child/manual API 测试不接入。
- 当前代理实现包含原管理分支和后续远程控制；不以旧文件覆盖新契约和迁移。
- `codex/m6-unfinished-checkpoint-20260913@59ae8d44` 是未完成历史检查点；`codex/studio-before-removal-20260913@4eda2074` 是退役前快照。两者必须保持非祖先，避免恢复被替代的 Studio 代码。

能力证据与最终命令结果见 `docs/migration/branch-integration/README.md` 及同目录各矩阵、`verification.md`。
