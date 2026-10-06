# M4 里程碑验收：身份模型与 perIdentity

- 日期：2026-10-06；状态：confirmed（本机 Windows 范围）——AC4-01 至 AC4-07 均有可复现证据；已知限制与遗留见文末；macOS 由用户手动验证
- 规格：[M4 规格](../specs/2026-09-30-remediation-m4-identity.md)；分支 codex/architecture-baseline
- 环境：Windows 11、32 逻辑核、CloakBrowser chromium-146.0.7680.177.5（真实浏览器用例）
- 决定：[模板种子与 perIdentity](../../../.ai/decisions/2026-10-05-m4-template-seed-and-per-identity.md)、
  [perIdentity v1：保留实例、不保留浏览器](../../../.ai/decisions/2026-10-06-m4-s8-per-identity-v1-keep-instance.md)

## 验收清单

| 条目 | 要求 | 结果 | 证据 |
|---|---|---|---|
| AC4-01 | G1 新建 200 身份种子两两不同；每身份 3 次运行种子/UA/语言/时区/出口一致；同一代理成员出口变化被检测并按策略处理，不以成员 ID 相同冒充出口未变 | 达标：G1 200 行 55 分 47 秒通过（200 身份种子两两不同；196 个正确账号 3 次运行的 UA/时区/Cookie/canvas 指纹一致且互不相同；4 个错误密码账号各登录 1 次）；出口变化在 G3 阶段 D 中以真实浏览器验证（G1 每个循环用一个不限次数批次，因为任务数上限最大为 100） | `tests/golden/test_g1_accounts.py`（`AUTOFLOW_G1_ROWS=200`）、`test_g3_identity_proxy.py` |
| AC4-02 | 2% 密码错误的账号记为业务失败，批次不停，身份健康计数增加 | 达标：错误账号只登录 1 次、健康计数 1，批次不暂停 | G1 |
| AC4-03 | 代理不可用期间：失败归 infrastructure，不消耗行预算；连续失败达阈值时批次暂停并指出代理；恢复后继续 | 达标：G3 阶段 E——全池不可达，所有行在浏览器启动前以 `PROXY_UNAVAILABLE` 失败，批次暂停且原因码为 `PROXY_UNAVAILABLE`，行尝试次数不变；恢复后继续运行未领取的行，被占用任务名额的行在下一批次重新处理 | G3 阶段 E、`test_identity_exit_region.py` |
| AC4-04 | 出口地区与身份 region 不一致时按策略拒绝启动，错误说明两边的地区 | 达标：G3 阶段 D——成员 ID 不变、出口变为柏林，上海账号全部以 `IDENTITY_REGION_MISMATCH` 拒绝，消息同时含两边地区；批次暂停；"警告继续"策略见单元测试 | G3 阶段 D、`test_identity_exit_region.py`、`test_identity_region.py` |
| AC4-05 | 迁移：夹具工作区中的环境全部生成身份；共用种子的环境出现在报告中且种子未被改变 | 达标 | `test_identity_migration.py` |
| AC4-06 | 1000 身份及并发分配无重复；两个历史同种子环境迁成两个独立身份、同一登记且 legacyShared 报告完整；公开 API 不可创建共享豁免 | 达标 | `test_identity_seeds.py`、`test_identity_migration.py` |
| AC4-07 | perIdentity 连续多行复用、Task 注入凭据清理、登录状态保留、跨批次独占、撤权/未知结果不归还；不支持的组合明确回退 | 达标（v1：复用同一**实例**，非同一 worker）：见下 | `test_identity_exclusivity/hold/release/end/sweep.py`、G2 |

## AC4-07 证据细目（S8-1 至 S8-7）

| 子项 | 证据 |
|---|---|
| 同身份连续多行复用同一实例，登录 Cookie 保留 | G2：同账号后续行带着 Cookie 进入；每账号 1 个实例，使用代次 = 行数；`prepare_instance` = 账号数、`restore_generation` = 0（3×3 与 5×4 均通过）；`test_identity_hold.py` |
| 后一任务看不到前一任务的凭据、变量、授予的权限 | 每个任务新建 worker 与浏览器进程，变量与凭据按运行重建（v1 设计结果）；登录 Cookie/存储属于登录状态，按设计保留 |
| 登录状态保留且只保存一次 | G2：批次结束后每账号 1 个新环境（版本 1），批次 2 版本 2；`test_identity_release.py`（3 任务 → 1 次保存，已有环境版本只 +1）；基准 k=10：环境文件工作 16.3 s → 2.8 s |
| 跨批次身份独占 | `test_identity_exclusivity.py`（数据库唯一索引、预约拒绝、领取等待）、`test_identity_hold.py`（其他批次等待）；G2 并发 = 账号数下无死锁 |
| 撤权/超时/中断/崩溃不保存、不归还 | `test_identity_end.py`：`timed_out`/`interrupted` 丢弃且不保存；`failed`/`cancelled`（worker 已确认清理）交还副本；`quiesce` 不过则原状等待 |
| 重启后保留实例先核实、不当空闲复用 | `test_identity_hold.py`（运行锁存在则拒绝附着）、`test_identity_sweep.py`（重启后锁消失前既不保存也不复用，之后释放并保存） |
| 释放中断/保存失败的恢复 | `test_identity_release.py`：保存后清理前中断 → 重放同一操作，不产生第二个环境；保存失败 → `retained_unsaved`、身份解锁、原因写日志 |
| 配置面 | 保存/启动/冻结校验与前端三选一（`test_project_automation_rules` 等 7 个新增用例；前端 `RunPolicyEditor`/`BatchLauncher`/`form-schema` 测试） |
| 临时种子与池隔离不支持时明确回退 | pool + 任务级新种子是 CloakBrowser 进程级参数，回退 perTask（M3 已如此，见 2026-10-05 决定） |

## 验证摘要（本机 Windows）

| 项 | 结果 |
|---|---|
| 全量后端回归（HEAD 43931bf0 之后） | 4973 passed；834 失败与 S8 之前的失败集合逐条相同（符号链接权限、缺 WebRPA 冻结源、OCR/人脸库、PyInstaller 等本机环境问题） |
| 真实浏览器套件（工作流、批次、Sheets） | 72 passed / 1 skipped（S8 之前一轮；G2/G3 另行通过） |
| G2 共用账号 | 3 账号×3 行 109 秒；5 账号×4 行 150 秒 |
| G3 代理夹具 | 12 账号、本地 SOCKS5 成员，5 个阶段 271 秒 |
| 前端 | 项目自动化/批次/环境相关 333 个通过；类型检查、lint、棘轮检查通过；全量 6 个失败均为已知本机问题 |
| 基准（规则 4） | native-batch-v1（池化、200 行、并发 2、5 样本，同机同时段 A/B）：S8 之前提交 3ea4d314 中位 180 行/分钟（146–205）；S8 之后 190（154–193，另一轮 170，其中样本 1 因我刚删除 worktree 的磁盘负载出现 1 次重试，已弃用并在静置状态重跑）；循环延迟 p99 25.8–29.3 ms，两侧相同。claims-10000 与领取循环延迟噪声内；`bench_identity_session` k=10 环境文件工作 16.3 s → 2.8 s。机器基线当天在 180–212 之间波动（后台负载 4–79%），不据单轮判定 |

## 已知限制与遗留（诚实披露）

1. **首次绑定代理成员不看身份地区**：`choose_member` 首次绑定取第一个可用成员；成员的地区标签是面板给的自由文本，身份地区是时区，
   两者没有可靠映射。混合地区的池里，上海身份可能被绑到柏林成员，之后每次运行被 `IDENTITY_REGION_MISMATCH` 拒绝，
   而粘性绑定不会自行更换，也没有"重新绑定"入口。G3 因此让池一开始只含同地区成员。可靠做法需要首次绑定时对候选成员逐个做出口探测，
   或增加重新绑定入口；留待用户决定（见下一步）。
2. **G3 不覆盖浏览器已启动后的代理中途断开**：断开发生在启动前（成员不可用/地区不符）。中途断开的页面类失败沿用 M2 的分类。
3. **v1 每个任务仍启动一次浏览器**：perIdentity 省掉的是每任务的环境恢复与保存，不是浏览器启动；是否做 S8b（浏览器保活）取决于基准。
4. **服务关闭时不额外保存**：保留副本在持久化意义上静止，下次启动的释放扫描保存；End 受理后、hold 前崩溃的实例需人工处理。
5. **`project_manual` 节点与节点自带浏览器环境**不能与 perIdentity 同用（校验阻断）。
6. **S9 界面改名（"身份模板"）与"标记身份状态"节点**随 M5 5C，未做；End 的业务结果引用变量目前没有配置界面入口。
7. **AOCI 条目未维护**：本会话 aoci MCP 不可用；macOS 与 Windows 之外的平台由用户手动验证。
8. CI：三平台后端全量回归通过；Windows/macOS Intel 上的桌面打包冒烟与时序用例的偶发失败见 [S10 记录](2026-10-04-remediation-m4-step-plan.md)。
