> 当前状态：接入已完成（2026-09-13）。以下保留原交接清单；本轮已接管并按此落实，最新验收见 [PM2核验](pm2-verification.json)。

# PM2 编辑任务提交后的接入清单

- 日期：2026-09-13；状态：confirmed / awaitingOwnerCommit。
- 来源：用户确认原编辑任务仍在进行；当前代码只读核对。此清单不代表页面已接入或通过验收。
- 前置：原任务独立提交并通过规格、工程审查；不得代为提交它的 DataTableDetailPage、use-data-table-editing 和 smoke-project-data 文件。

## 1. 已准备的组件与调用约定

路径均在 `apps/desktop/src/renderer/domains/project-data/`。

| 入口 | 复用实现 | 页面需要提供的事实 |
|---|---|---|
| 记录表批量选择 | `use-record-selection.ts`、`components/DataRecordsTable.tsx` 的可选 selection/onBulkStatus | workspaceKey、projectId、tableId、datasetGeneration；实际记录页。不提供 selection 时保留旧行为。 |
| 批量状态 | `components/RecordStatusBatchDialog.tsx`、`status-batch-api.ts` | 直接传 selection.targets，包含选择时固定的 RecordRef/statusRevision；不能从最新页重建版本。 |
| 重新导入 | `components/ExcelImportWizard.tsx` 的 replace 模式、`excel-api.ts` | 当前 table、existingFields，真实 files.chooseInput；不按显示名自动匹配字段。 |
| 导出 | `components/ExcelExportWorkflow.tsx` | 当前 table/fields/statuses，已应用的 filter/orderBy 编码，真实 files.chooseOutput；不使用未提交筛选草稿。 |
| 来源事实 | `components/DataTableSourcePanel.tsx` | table.source；缺历史来源证据时明确缺失，不回退编造文件名或路径。 |

`createProjectFileClient(client, window.autoflow, projectId, current)` 复用目录页做法；current 检查当前工作区、项目、服务实例、client 与服务可用性。`createExcelApi` 的新文件命令走 proof 通道，查询和 reconcile 不重新兑换文件令牌。

## 2. 接入时必须保留的边界

1. scopeKey/storageScopeKey 包含工作区、项目、表；contextKey 在此基础上含服务实例；sessionKey 只在明确开始新表单会话时变化。不能在后台刷新时重置草稿。
2. 编辑、单状态、删除、批状态、导入/导出使用页面同一个活动弹窗协调点。将 onDirtyChange/onBusyChange 接入现有唯一 registerLeaveGuard，避免注册器互相覆盖。
3. 未知请求保留原身份并先查询；已接受的进度关闭只离开视图。批状态“停止后续处理”才是明确取消，已提交块不回滚。
4. 导入成功刷新表、字段、记录和来源；replace 新代次清空旧选择，并按新字段目录移除失效筛选/列。不得把旧 RecordRef 改写为新代次。
5. 批状态接 `onSettled(operation)` 刷新记录/目录事实，包含部分提交后 failed；此回调在每个 scope/context/session 内按操作去重，新服务实例重新查回终态时会再次通知，以刷新新查询键。只在 `onCompleted` 显示完整成功，不能从 `onSettled` 直接发成功或失败 Toast。保留冲突和未执行结果供查看。
6. 导出允许归档只读项目；disabled 用于服务切换或不可访问。归档仍不能导入或改状态。导出只生成新文件，不修改表。
7. 对外文案使用业务状态、来源文件、数据已更新；内部修订、代次、字段 ID 只用于请求与冲突判定。

## 3. 仍需执行的验收

- 原编辑任务的页面/API全链操作，以及其当前 `DataTableDetailPage.test.tsx:18` 未使用参数 lint 问题，由原任务提交处理后复核。
- 本页真实批量设置/清空、跨页选择、冲突块、停止和重启恢复。
- 真实替换向导、确认后人工修改冲突、新代次和旧记录隔离。
- 真实导出对话框，当前筛选/选列、文件冲突、核验及只读导出；系统文件面板人工交互。
- 两个真实工作区切换、同工作区服务恢复、200% 缩放下编辑/替换/导出弹窗、长字段值和大表界面响应。
- 本轮仅目录新表导入已有 Electron 证据；未挂载的组件测试不能充当上述页面验收。

PM2 完整退出检查使用 `node scripts/verify-pm2-delivery.mjs --require-complete`；当前应拒绝完整通过。完成并记录上述事实前，不进入 PM3。
