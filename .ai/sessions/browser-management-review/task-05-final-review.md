# 任务 5 CancelledError 修复最终定向复审报告

- 日期：2026-09-12
- 复审范围：仅提交 `ecfa3b2` 相对父提交 `a2921d2` 的任务 5 修复，并读取 `task-5-rereview.md`、`task-5-rereview2.diff` 与紧邻 worker/锁/状态机上下文
- 范围限制：不审查任务 6 HTTP API，不扩展公共 proxy 或当前工作区其他并发改动
- 置信度：高
- 结论：**PASS**

## Findings

无阻断或非阻断 finding。前次复审唯一 P1 已关闭。

## 定向核对

### 1. spawn 前后取消不会丢失进程句柄 — PASS

`start()` 在进入 `create_subprocess_exec()` 前先把 spawn 包装为独立 task，并以 `asyncio.shield()` 等待。调用方在 spawn 尚未返回时被取消，内层 spawn 不会随调用方一起取消；异常路径用 `_wait_uninterruptibly()` 等到 spawn 完成并取回 `Process`，再进入统一补偿。因此“系统已经创建子进程、调用方却在赋值前收到取消”的窗口仍能得到句柄。

spawn 已返回后，`process` 在下一个可取消点 `stdin.drain()` 前完成赋值；此后取消直接把已赋值句柄传给 `_compensate_start()`。setup 成功后的 monitor 创建与 `_running` 登记之间没有 await，不存在另一个可注入 `CancelledError` 且丢失监管的窗口。

### 2. 重复取消不会中断补偿 — PASS

补偿在单独的 cleanup task 中运行，外层仅通过 shield 等待。`_wait_uninterruptibly()` 会吞掉等待方收到的后续 `CancelledError`，持续等待到 cleanup task 终止，再由 `start()` 重新抛出原取消。重复取消不会直接取消 cleanup task，也不会提前退出清理路径。

新增真实子进程测试在 `stdin.drain()` 人为阻塞后连续两次取消，并使用忽略 SIGTERM 的 worker 强制走 terminate 超时、kill、wait 路径；测试确认子进程已有 returncode，而不是只发出停止信号。

### 3. 补偿收敛终态并释放资源 — PASS

`_compensate_start()` 的顺序为关闭 stdin、对存活进程执行 terminate/超时 kill 并 wait、删除任务 staging、把原 queued operation 持久化为 `failed`、发布快照，最后在 `finally` 中释放 ownership。取消路径保存的错误为 `Kernel worker start was cancelled`。

这满足本次核对的三个可观察结果：实际进程已回收、持久任务进入终态、任务 staging 被移除。ownership 即使补偿主体抛错也会释放，不会遗留当前 manager 持有的 OS 文件锁。

### 4. 第二个 manager 可以重试 — PASS

两个新增取消测试都在第一个 `start()` 完成补偿并重新抛出 `CancelledError` 后，新建共享同一 kernels 目录和 repository 的第二个 manager，并成功完成另一个版本的安装。该路径实际经过同一 `<kernels>/.install.lock` 的 `ExclusiveFileLock`，证明取消补偿后锁已释放，而不只是清空内存状态。

## 验证结果

```text
四个核心回归：4 passed
Task 5 worker/entrypoint/profile-lock/event/provider/operation 聚焦回归：85 passed, 2 warnings
Ruff（变更源码与测试，使用 backend 配置）：All checks passed
mypy src：Success: no issues found in 58 source files
git diff --check ecfa3b2^..ecfa3b2：通过
```

两条 warning 来自现有 FastAPI/Starlette 测试依赖的弃用提示，与 `ecfa3b2` 无关。
