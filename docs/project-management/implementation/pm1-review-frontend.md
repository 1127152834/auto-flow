# PM1 前端独立复审

- 日期：2026-09-13
- 范围：`apps/desktop/src/renderer/domains/projects/**` 及项目接入相关的 `renderer/app` 代码
- 方式：只读规格复核、反例检查、工程质量审查和定向自动化验证；未执行真实 Electron QA
- 结论：规格通过，工程质量通过。置信度：高。

## 规格复核

本轮先复核此前发现的六类问题，再检查生命周期只读边界。审查期间发现归档等非活动项目的详情头部仍可开启编辑器；该问题随后增加反例并修复。最终实现与 PM1 执行卡一致：

1. 明确的 4xx（408 除外）会结束旧 pending；网络、超时、响应解析或核对失败保持结果未知。核对仅在精确的 `OPERATION_NOT_FOUND` 后用原 key 和原 body 重发，其他 404 不触发重发。证据：`apps/desktop/src/renderer/domains/projects/api.ts:15-21,29-47,51-76`，`api.test.ts:19-86`。
2. 创建和编辑的 pending 保存原始请求体与幂等键。实例变化时保留同一工作区的表单草稿，撤销旧请求对 UI 的写权限，并把表单切到只读核对状态；恢复提交继续核对原操作。证据：`apps/desktop/src/renderer/domains/projects/pages/ProjectsWorkspace.tsx:49-71,87-90,112-147`，`components/ProjectFormDialog.tsx:19-34,49-105`。
3. 工作区、实例、编辑会话和组件卸载均参与迟到回调隔离；打开项目另有 ticket，项目路由变化和卸载会撤销旧回调。旧成功、旧冲突和旧关闭判定均不能关闭新表单、导航或发 toast。证据：`ProjectsWorkspace.tsx:66-71,91-104,115-117,128-146,149-162`，`ProjectFormDialog.tsx:21-28,34,49-54,59-90`。
4. 表单在进入异步校验前取得同步提交锁；保存中和结果未知时输入只读，保存中不能通过 Escape、遮罩、取消或重复触发关闭和二次提交。结果未知的离开确认禁止放弃，只允许继续编辑或核对原结果。证据：`ProjectFormDialog.tsx:23-28,49-61,85-105`，`ProjectsWorkspace.tsx:93-110,176-177`。
5. 目录筛选和排序归第一页；恢复页码超过最新结果范围时归到最近有效页并清零滚动。列表使用有实际最大高度的 `ScrollArea`，恢复 viewport 的滚动位置；行内编辑按钮的 Enter 不再冒泡触发行打开。刷新错误保留已载入内容并明确标为旧内容。证据：`ProjectsWorkspace.tsx:28-46,55-86`，`components/ProjectDirectory.tsx:36-59`。
6. 项目详情与概览错误相互独立：概览失败显示错误和重试，同时保留真实项目资料；六个页签中只有概览显示已实现资料，其余页签统一显示未开放状态，没有假数据或假动作。证据：`ProjectsWorkspace.tsx:165-174`，`pages/ProjectOverviewPage.tsx:5-9`，`components/ProjectCapabilityState.tsx:1-5`。
7. 编辑入口、编辑器开启回调和最终提交均要求项目为 `active`。`closing`、`archived`、`deleting` 的详情保持只读，避免依赖后端错误才阻止编辑。证据：`components/ProjectHeader.tsx:5-9`，`ProjectsWorkspace.tsx:112-114,172`，`ProjectsWorkspace.test.tsx:176-184`。

未发现仍会违反 PM1 固定规则的前端规格缺口。

## 工程质量审查

规格通过后检查了项目域的 API 封装、query key、表单状态、目录组件、路由接入和测试。未发现需要阻止 PM1 合入的工程质量问题。

- 查询键包含 workspace、instance、project 和目录条件，读取请求传递 AbortSignal；项目域没有生产 mock。
- 页面使用生成的 OpenAPI schema 类型；`ProjectSummary` 是 `ProjectView` 的结构超集，目录编辑处的显式转换没有丢字段，但后续可作为非阻断清理移除。
- 恢复、冲突、重连和离开状态集中在工作区与表单两层，没有新增跨领域共享抽象或重复实现共享控件。
- 测试包含关键反例，而非只验证成功路径：明确失败与未知结果、原 key 恢复、旧实例成功、卸载迟到打开、无效页码、概览失败、同步重复提交、旧冲突刷新、旧关闭判定和非活动生命周期只读。

## 验证证据

在最终工作树执行：

```text
npm test --workspace @autoflow/desktop -- src/renderer/domains/projects src/renderer/app/App.projects.test.tsx src/renderer/app/navigation.test.tsx
Test Files  8 passed (8)
Tests       51 passed (51)

npm run typecheck --workspace @autoflow/desktop
tsc --noEmit
exit 0
```

真实 Electron 的创建、编辑、分页、冲突和重连验收由主协调执行，本报告不以 Vitest 代替该证据。
