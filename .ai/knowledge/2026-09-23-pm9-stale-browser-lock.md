# PM9 浏览器退出后的遗留锁

日期：2026-09-23。状态：confirmed（本机复现与修复；最终三平台选定真实 worker 已通过）。

来源/验证：`docs/project-management/implementation/pm9/response-loss-lock-follow-through.json`；旧候选 CI 35816693045 的 macOS ARM `data-response-loss` 失败，本机同例 RED 后 GREEN。失败现场的 Chromium `SingletonLock` 所属 PID 已不存在，但 `SingletonSocket` 指向的 socket 路径仍存在；仅用路径存在判断会使终态实例长期占用，批次中的后续任务排队。

修复位于 `EnvironmentStore.runtime_lock_present`：macOS 仅在本机锁 PID 有效、系统确认其已退出且锁目标未变化时忽略遗留 runtime 标记；活进程、复用 PID、外机/畸形/缺失锁与竞争变化仍按占用处理。受控边界单元 15 项、真实响应丢失场景 1 项、相邻所有权/持久环境/恢复 46 项通过；Ruff/mypy407 通过。Actions 35822065171 的三平台全量、选定真实 worker 和打包链成功；物理/Google/签名及其他发行条件仍开放，`releaseAccepted=false`。
