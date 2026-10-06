# M4 S8：perIdentity v1 保留"实例"，不保留浏览器

- 日期：2026-10-06；状态：confirmed（用户 2026-10-05 授权实施方决策；依据为 6 个子系统的代码阅读，见"验证方式"）
- 取代：`docs/superpowers/plans/2026-10-05-remediation-m4-s8-per-identity-design.md` 第 2–4 条（保留浏览器与 worker、回收时保存）
- 规格：M4 R4-12、AC4-07、R4-06

## 决定

1. v1 只保留环境实例（工作副本目录 + 身份独占），不保留浏览器。每个任务结束仍由 worker 关闭浏览器，
   End 用现有 quiesce 规则确认静止后把实例置为 `identity_held`；同批次同身份的下一行重新附着该实例（不重新恢复）。
2. 保存时机由调度器侧、数据库驱动的释放扫描触发：空闲 120 秒、批次终态、`closing` 重试；释放 = 保存一次再清理（环境版本只 +1）。
3. 失败/取消且 worker 已确认清理的运行把副本还给身份（保留此前成功任务尚未保存的登录变化）；超时、中断、撤权、崩溃、清理失败
   一律丢弃、不保存，保留上一次保存的版本。
4. perIdentity 的 End 不再做记录关联（`recordTargets` 被忽略，身份靠 `IdentityRow.environment_id` 带登录）；v1 不支持 `project_manual` 节点。
5. 同批次内才复用，跨批次的同身份行等待释放；任一次 End 要求保存，则释放时保存。
6. 身份独占独立于 perIdentity：同一身份任何时刻只有一个未释放实例（含还没有保存环境的身份），领取侧据此让行等待（temporarilyBusy），
   不再让 `ENVIRONMENT_BUSY` 在调度器里无人捕获。
7. AC4-07 第 1 条的"复用同一 worker"改为"复用同一实例"，推迟的 worker/浏览器保活为 S8b，仅当 v1 基准证明每任务启动浏览器是主要成本才做。

## 理由（读代码得到的硬伤，均已核对）

- 保存要求浏览器已关闭：worker 在发 end 前先 `context.close()`，父侧 `end.py:89`、`worker_capabilities.py:166` 硬要求 `browserClosed=True`。
- worker 回收无法区分干净关闭与被杀：子进程 `finally` 的 `pool.close()` 被 suppress，`_retire` 对 3 秒超时直接强杀，
  Windows 上服务一死 Job 即硬杀 Chromium；此时保存会把撕裂的登录状态发布成新版本。
- 池容量只有 2，`_take_any_idle` 会驱逐任意空闲 key，且没有指向环境服务的回调；池化加代理时每次启动带随机 relay 端口，复用键失效。
- 身份独占今天只对已有保存环境的身份成立（占用表主键是 environment_id），首次登录恰好没有环境；领取侧完全不看占用，
  被占身份的行会走到 `scheduler.py` 的 reserve 抛无人捕获的 `ENVIRONMENT_BUSY`，批次队首被反复卡住（perTask + inputIdentity 同样受影响）。

## 影响与风险

- 每任务仍启动一次浏览器；收益是省掉每任务的 restore + stage + publish + rmtree 与 N-1 次保存。基准：`bench_identity_session`、`bench_first_node_latency`。
- 服务关闭时不额外保存：保留副本在持久化意义上静止，下次启动的释放扫描保存。已知上限。
- 进程在 End 受理后、hold 之前崩溃：实例仍 active，被未决 retain 操作保护、身份保持占用，需人工处理（与现有中断 End 同语义）。
- 切片：S8-1 独占与领取门禁 → S8-2 持有与重新附着 → S8-3 释放保存 → S8-4 End 改持有 → S8-5 释放扫描 → S8-6 配置与校验（后端）→ S8-7 前端与真实浏览器验收。S8-8/S8-9 门控。

## 验证方式

读码（6 路并行阅读 + 汇总）：environments.py、service.py、retention.py、end.py、worker_capabilities.py、project_claims.py、scheduler.py、
project_workflow_worker.py、pooled_browser.py、dispatcher.py、rules.py 等；实现时逐切片以测试验证。
