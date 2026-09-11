# 任务 10 Round 2 定向复审

- 日期：2026-09-12
- 复审范围：`c84037f..2a8dfd5`；只核对 `task-10-rereview.md` 唯一未解决 P1、Round 2 修复新增测试，以及该修复 diff 是否造成新的重要相关破坏
- 文件范围：`apps/desktop/src/renderer/domains/kernels/hooks.ts`、`hooks.test.tsx`、`components/KernelManagerDialog.test.tsx`
- 排除范围：旧代码全域审计、其他 Task 10 已关闭 finding、Task 11/12、当前工作区无关未提交内容
- 置信度：高
- 原 P1 结论：**ADDRESSED**
- 最终结论：**PASS**

## 原 P1 核对

### `[P1] 晚到 SSE snapshot 删除 POST 新 ID` — **ADDRESSED**

`hooks.ts:58-65` 新增 `mergeKernelOperationSnapshot()`：

1. 先逐项输出 incoming snapshot，并对同 id 调用既有 `mergeKernelOperation()`；因此后端历史顺序原样保留，同 id 状态仍按 Round 1 规则单调合并，不会由 terminal/cancelling 倒退。
2. 再按当前 cache 顺序追加 snapshot 未包含的 cached-only operation；因此 POST 刚创建并写入 cache 的新 id 不会被较旧 snapshot 删除。

这一顺序与后端协议吻合：`SqlAlchemyKernelOperationRepository.list()` 按 `created_at, id` 升序返回完整 operation 历史，`KernelWorkerManager.snapshot()` 直接返回该列表，SSE 发布完整 snapshot。当前没有删除 operation 的协议语义。因此 incoming 中已有历史在前、cached-only 新任务在后的合并结果是正确的保守顺序。

同 release 的 UI 状态也保持正确。`KernelReleaseList` 按 operations 数组顺序写入 `operationByRelease`，最后一条同 release operation 胜出。对于回归顺序 `[operation-old/failed, operation-new/queued]`：

- 展示的是 `operation-new/queued` 的“准备下载”，旧任务的“网络中断”不会覆盖它；
- 新任务仍显示可用的“取消下载”，按钮回调绑定当前展示 operation 的 `operation-new` id；
- `KernelManagerDialog` 对整个 operation 数组执行 `some(operationIsActive)`，所以 cached-only 新任务继续维持全局 busy；
- 另一 release 的“下载安装”保持 disabled，点击不会产生第二个 download 请求。

新增的 helper 测试直接断言较旧 snapshot 与 cached-only 新任务合并为 `[old, new]`。新增的 manager 集成测试真实执行“POST 返回 `operation-new/queued` → SSE 仅含 `operation-old/failed`”，随后断言新任务仍是所示最新状态、取消按钮可用、旧错误不显示、第二个下载按钮禁用，且 `/api/v1/kernels/download` 总调用数仍为 1。

## 修复 diff 新破坏检查

未发现新的重要相关破坏。改动只引入一个纯列表合并 helper，并把 SSE snapshot 写 cache 的位置切换到该 helper；未改动 release identity、请求 payload、cancel mutation、busy 判定或组件生产代码。三个文件的精确 git diff 与 `task-10-rereview2.diff` 一致，`git diff --check c84037f..2a8dfd5` 通过。

`ponytail` 复杂度检查未发现不必要依赖、抽象或重复状态系统；单个纯 helper 是覆盖三条合并约束的最小修复面。

## 验证

```text
npm test -- --run src/renderer/domains/kernels
  6 files / 24 tests passed

npm --workspace @autoflow/desktop run typecheck
  passed (tsc --noEmit, exit 0)

npx eslint src/renderer/domains/kernels/hooks.ts \
  src/renderer/domains/kernels/hooks.test.tsx \
  src/renderer/domains/kernels/components/KernelManagerDialog.test.tsx \
  --max-warnings=0
  passed (exit 0)

git diff --check c84037f..2a8dfd5
  passed
```

本轮唯一未解决 P1 已关闭，Task 10 Round 2 定向复审为 **PASS**。
