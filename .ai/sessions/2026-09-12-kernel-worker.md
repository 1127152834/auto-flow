# 内核安装工作进程与事件流交接

- 日期：2026-09-12
- 状态：confirmed
- 来源：`docs/superpowers/plans/2026-09-12-browser-management.md` 任务 5、离线 pytest worker/entrypoint 测试、Ruff 与 mypy 验证。

## 已完成

- 内核安装 operation 使用现有 `kernel_operations` 表持久化完整快照，并按 queued/downloading/verifying/extracting/cancelling/terminal 状态机更新；启动恢复把未完成 operation 标记为 failed 并清理对应 staging。
- sidecar 通过同一冻结可执行文件的 `--kernel-worker` 分支或开发态 `python -m autoflow --kernel-worker` 启动一个受监管子进程。取消先 terminate，默认等待 3 秒，仍未退出才 kill，并在真实退出后清理 staging。
- worker 只接受 catalog/license/download JSON 命令。每个命令在首次导入 CloakBrowser wrapper 前设置任务 cache；License 只经 stdin 传入，不进入 argv、operation 数据、协议输出或 wrapper 日志。
- 下载先落入 `<kernels>/.staging/<operation-id>`。父进程校验版本、相对可执行路径、安装目录、越界符号链接和可执行文件后原子发布；已有有效目标只复用，不覆盖。
- `/api/v1/kernels/events` 已接入实例 token 认证；连接首帧和后续事件均为完整 operation snapshot，慢消费者只保留最新 snapshot，15 秒空闲 heartbeat。
- app shutdown 会沿同一取消路径停止所有 worker；worker 也监视 sidecar 父进程，避免宿主异常退出后长期成为孤儿。

## 验证边界

- 自动测试 worker 只写临时文件，不访问网络；catalog/license/download 入口使用临时 fake wrapper 验证 import/cache 和敏感信息边界。
- 本任务没有实现任务 6 的 kernel HTTP 下载、取消、License 和 catalog API；并发 manager 启动以 `KERNEL_BUSY` 领域错误拒绝，HTTP 409 映射留给任务 6 路由。
- 未执行真实 CloakBrowser 下载，也未声称 Windows/macOS 打包验证；该验证属于计划任务 10。
