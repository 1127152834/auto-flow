# 任务 1 修复定向复审报告（轮 2）

- 日期：2026-09-12
- 复审范围：原审查 `task-1-review.md`、简报 `task-1-brief.md`、实现报告 `task-1-report.md`；修复 diff `d69ddfb..03ec55a`。
- 复审方式：只读检查修复代码、测试、样式与提交 diff；运行 `npm test -- --run src/renderer/shared/components`、`npm run typecheck`、`npm run lint`，并执行 `git diff --check`。
- 范围说明：复审仅针对任务 1 的共享 Dialog/Toaster 修复。并发的 ProxyPanel/automation 工作区内容不纳入本轮判断。

## 逐条结论

### 发现 1：busy 弹窗关闭路径 — ADDRESSED

本轮 diff 未回退上一轮修复。`Dialog` 根部仍在 `busy && !nextOpen` 时拦截 `onOpenChange(false)`，`DialogClose` 仍通过 `preventDefault()` 阻止关闭，`DialogContent` 仍拦截 Escape 与 outside pointer dismissal。已有关闭按钮测试继续通过，未发现新的 busy 关闭路径回归。

### 发现 2：嵌套弹窗关闭顺序与焦点 — ADDRESSED

`ui/dialog.test.tsx` 现在通过真实的 Trigger 点击打开默认关闭的内层弹窗；测试等待内层按钮获得焦点，明确证明 `document.activeElement` 位于内层。随后发送 Escape，断言内层消失、外层仍存在，并等待焦点恢复到“打开内层”触发器。该测试覆盖了“顶层焦点 → Escape 只关顶层 → 外层保留/焦点恢复”的要求。当前实现继续使用 Radix 的焦点管理，测试通过。

### 发现 3：ProxyPanel 内容混入任务 1 — ADDRESSED（按范围排除）

`d69ddfb..03ec55a` 仅增加任务 1 的报告、Dialog/Toaster 测试与实现、样式；没有新增 ProxyPanel 文件。原先并发提交链中的 ProxyPanel 内容仍不归责于本轮任务 1 修复。

### 发现 4：Toast 150ms 淡入/淡出与 2600ms 生命周期 — ADDRESSED

`Toaster` 在 2600ms 计时点将 toast 标记为 `toast-exit`，继续保留在 DOM 150ms，随后移除。测试覆盖 2599ms 仍存在、2600ms 进入 `toast-exit`、退出阶段 149ms 仍存在以及再过 1ms 移除。样式新增 `toast-exit` keyframes，含 150ms opacity/位移淡出；已有 `toast-enter` 仍提供 150ms 淡入，reduced-motion 规则仍可压缩动画时长。

## 新破坏检查

- `npm test -- --run src/renderer/shared/components`：3 个文件、8 个测试通过。
- `npm run typecheck`：通过。
- `npm run lint`：通过。
- `git diff --check`：通过。
- 嵌套 Dialog 的顶层焦点、Escape 顺序、外层保留和焦点恢复均有可执行断言；未发现该修复引入的 Dialog 回归。
- Toast 的手动关闭/卸载后定时器清理风险仍存在，但这是上一轮已记录的生命周期问题，本轮 diff 没有新增该行为；未发现新的可复现破坏。

## 复审结论

**PASS（原四项发现均已处理）**。busy 全路径禁关保持修复；嵌套弹窗测试补齐了内层焦点与 top-dialog Escape 顺序；任务外 ProxyPanel 内容未进入本轮修复 diff；Toast 已具备 2600ms 展示、150ms 退出阶段及淡入/淡出 CSS。置信度：高。
