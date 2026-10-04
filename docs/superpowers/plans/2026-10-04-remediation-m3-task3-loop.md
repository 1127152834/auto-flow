# M3 测量与 Task 3 决定：主循环阻塞点与写线程

- 日期：2026-10-04；状态：confirmed（本机 Windows）
- 规格：R3-03、AC3-02、整改规则 3

## 方法

native-batch-v1（20 行、真实浏览器、并发 2）运行期间，用采样探针（事件循环心跳停滞 > 50 ms 时记录所有线程
的 autoflow 调用链）定位阻塞事件循环的代码，而不是凭猜测引入写线程。asyncio 调试模式未报告单个 > 100 ms 的回调，
说明延迟来自循环线程上的同步阻塞调用与锁等待。

## 发现与修正

| 阻塞点（循环线程） | 原因 | 处理 |
|---|---|---|
| `browser_resources._kernel → catalog.installed()` | 每个任务解析内核时递归计算整个内核目录大小（秒级） | 运行时只做"是否存在"扫描（`installed_without_size`）；设置页仍显示大小 |
| `worker_capabilities.handle → update_record → commit` | 记录读写在循环线程上同步执行，并可能等待线程中事件提交的写锁 | 数据能力的执行移入线程 |
| worker 冷启动导入 SQLAlchemy/Alembic | `runtime` 模块急切再导出数据库服务 | 惰性再导出（worker 导入 2.1 s → 约 1.3 s） |

曾尝试惰性导入 openpyxl：worker 已有多线程后再加载 numpy 的 C 扩展会在 Windows 上卡死（转储确认），已撤回。

## 结果

| 指标（20 行样本） | 改前 | 改后 |
|---|---|---|
| 运行期间主循环延迟 p99 | 124–146 ms | 12 ms |
| 领取 → 首节点开始 | 2.0 s | 1.0 s |

## Task 3 决定

剩余停顿样本约 0.24 s/20 任务（终态状态转换等短事务），p99 已远低于 50 ms 预算。按 R3-03，不引入单一
`DatabaseWriter`，保留既有短事务；若 Task 9 的大规模样本重新出现锁等待，再按同一探针方法取证。
