# M3 Task 8：环境存储瘦身与代次清理

- 日期：2026-10-04；状态：confirmed（本机 Windows 测量）
- 规格：[M3 规格](../specs/2026-09-30-remediation-m3-throughput.md) R3-09、R3-10；AC3-06

## 测量

新增 `bench_environment_roundtrip`：约 45 MB / 2,100 个文件的 Chromium 环境夹具（登录存储、IndexedDB、
Service Worker 脚本缓存，外加占大头的网页 / 脚本 / 显卡缓存），测"恢复到工作副本 + 保存为下一版本"，5 次中位数。

| 路径 | 往返耗时 | 每个版本大小 |
|---|---|---|
| 保留缓存（改前唯一路径） | 11,156 ms | 43.9 MB |
| 默认排除缓存 | 948 ms | 3.8 MB |

AC3-06 恢复 + 保存 < 2 秒：达标；CI 增加 `bench_environment_roundtrip --budget-ms 2000`。

## 设计

- 排除清单集中在 `environment_store.BROWSER_CACHE_NAMES`（Cache、Code Cache、GPUCache、各类着色器缓存、Crashpad 等），
  保存时不复制。Service Worker 目录不在清单里（网站会用它保持登录）。
- 按环境覆盖：环境新增 `keepBrowserCache`（迁移 `rm3_environment_cache`），环境详情页"保存时保留浏览器缓存"开关；
  更新保存读取该环境的设置，另存为新环境用默认清单。
- 摘要不变：仍对保存后的全部内容做完整摘要（版本 2），只是内容里不再有缓存。
- 版本清理（`retention.prune_generations`），每次"更新保存"成功后执行：
  - 保留：当前版本、未关闭实例的来源版本、未结束运行冻结的版本、未结束批次冻结的版本、已写盘但库里尚未切换的版本，
    再加最近 3 个无人引用的历史版本。
  - 顺序：持数据库写锁 → 重新查引用 → 把待删版本整目录改名进回收区（之后任何新引用都只会指向当前版本）→ 释放锁 → 删除回收区。
  - 移动失败（Windows 文件被占用）保留该版本并写日志，下次保存再试；清理失败不影响保存结果。
  - 不按目录年龄判断孤儿。
- 占用指标：`GET /environments/{id}/storage` 返回每个版本大小与保留原因，汇总为"仍在使用"和"可回收历史"；
  环境详情页"存储空间"区展示。

## 证据

- `test_environment_generations.py`：缓存被排除且 Service Worker 保留、开关后缓存随保存保留；连续 100 次保存只留
  当前 + 3 个历史版本且总占用 ≤ 单版本 × 4；被冻结任务引用的第 1 版在 100 次保存后仍在并可恢复（原因"instance"）；
  冻结请求任意位置的版本引用都能识别；无法移动的版本保留到下一次保存再清。
- 前端：环境详情页新用例（占用文案、开关提交 `keepBrowserCache`）；environments 38 项通过；tsc / eslint 通过。

## 未做 / 偏离

- clonefile / 块克隆：规格要求经原生平台验证后才启用；本机 Windows 未验证，继续用普通复制（精简后已达标）。
- 不使用硬链接，不可变版本不会链接进可写工作目录。
- 占用展示放在环境详情页而不是设置页：占用和保留原因按环境计算，放在环境自己的页面更直接；项目级汇总留到 Task 9 评审再定。
- 真实浏览器的 Service Worker 登录样例：本任务用文件级测试证明 Service Worker 目录被保留；真实站点登录保持在 M4 G1 验证。
