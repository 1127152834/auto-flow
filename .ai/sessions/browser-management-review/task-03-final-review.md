# 任务 3 P1 修复定向复审

- 日期：2026-09-12
- 复审范围：提交 `a807583` 相对 `fdda052` 的 profiles task3 文件，以及原计划、`task-3-review.md` 和 `task-3-rereview.diff`
- 范围限制：只审查 profiles task3 的应用服务、领域端口、文件系统数据处理、bootstrap 装配和对应测试；不审查当前工作区的前端/自动化文档改动
- 置信度：高
- 结论：**PASS**

## Findings

未发现 P0/P1/P2 阻断项，也未发现本次修复引入的安全回归。

## 原 P1 修复核对

### 崩溃恢复不会误 purge 数据库仍引用的数据

`FilesystemProfileDataStore.retry_pending()` 从 trash token 取得 profile id，并在任何清理动作前通过只读仓储事务查询数据库：

- 数据库行仍存在、目标目录缺失：恢复 staged 目录；对应 stage 后、DB commit 前崩溃。
- 数据库行不存在：只清理已提交删除遗留的 staged 目录；对应 DB commit 后、purge 前崩溃或 purge 失败。
- 数据库行存在且目标与 staged 同时存在：两份都保留并记录冲突，不猜测哪份可删。
- 恢复 rename 失败：staged 目录保留，后续启动仍可重试。
- 数据库行不存在但 staged 目录带 Chromium 活动标记：保留目录并记录阻塞，不强制清理。

这组状态以数据库提交结果作为删除事务的持久判据，修复了原实现“启动时按 token 外形无条件清空 trash”的数据丢失窗口。真实 SQLite 恢复测试覆盖 commit 前崩溃、commit 后清理失败和 restore 失败；文件系统测试覆盖恢复冲突与带标记 orphan。

### OS 锁与 Chromium 标记均在 stage 前保守拒绝

`ProfileService.remove()` 在事务开始及 `stage()` 之前取得 `ProfileUsageGuard`，并持有到数据库提交和提交后 purge 完成。锁争用抛出 `ProfileDirectoryBusy`，不会移动目录或删除数据库行。

默认实现使用标准库跨进程文件锁：Windows 为 `msvcrt.locking(..., LK_NBLCK, 1)`，macOS/POSIX 为 `fcntl.flock(..., LOCK_EX | LOCK_NB)`。锁文件固定在受管 profiles 根目录下的 `.locks/<profile-id>.lock`，profile id 先经过规范 UUID 校验；锁路径 symlink 会被拒绝。

取得 OS 锁后，`SingletonLock`、`SingletonSocket`、`SingletonCookie`、`DevToolsActivePort` 任一存在即拒绝删除；dangling symlink 也通过 `is_symlink()` 被视为活动标记。启动清理对已提交删除的 staged 目录采用同样的标记保守策略。契约测试确认该拒绝映射为 409 `PROFILE_DIRECTORY_BUSY` 且数据库行和原目录保持不变。

已明确的边界保持成立：无共享锁协议、无 Chromium 标记的任意外部进程仅打开普通文件，无法在 Windows/macOS 上用统一且可靠的方式检测。本次修复没有声称覆盖该情形，也没有为 task3 引入完整 profile 运行管理。

### 删除事务边界正确

删除顺序为：取得使用锁 → 在数据库事务内确认 profile → stage 原目录 → 删除数据库行并提交 → purge staged 目录。

- stage 或数据库提交抛出异常：数据库事务回滚；若已 stage，则尝试 restore，再传播失败。
- 数据库提交成功后 purge 失败：profile 保持已删除，API 不误报删除失败；staged 数据留待启动重试。
- 使用锁在整个边界外层持有，避免参与同一锁协议的 profile 使用者在删除期间进入。

该边界没有出现“提交后错误恢复数据库已删除条目”或“提交前异常继续 purge”的分支。

## 安全与复杂度复核

- 原有 UUID、受管根目录、profile/trash symlink、嵌套 symlink 检查仍保留；客户端不能指定删除路径。
- 恢复冲突、未知 trash 项和活动标记均选择保留，不以推测换取自动清理。
- 新增 `ProfileUsageGuard` 是删除用例所需的最小端口；实现仅使用 Python 标准库，没有新增依赖或完整运行管理抽象。

## 验证

```text
task3 聚焦测试：27 passed, 2 warnings
后端全量测试：73 passed, 2 warnings
Ruff（task3 变更文件）：All checks passed
mypy src：Success: no issues found in 34 source files
git diff --check fdda052..a807583（task3 范围）：通过
macOS 额外探针：同进程独立 guard 锁争用被拒绝；四种 Chromium 标记逐一被拒绝
```

两条 warning 来自 FastAPI/Starlette 测试依赖的弃用提示，与本次修复无关。Windows 分支本机未执行；其实现经静态审查且跨进程测试使用平台分支运行，最终 Windows CI/打包验证仍属于计划后续平台验收。
