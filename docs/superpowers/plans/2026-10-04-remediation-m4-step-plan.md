# M4 身份模型：步骤级实施计划

- 日期：2026-10-04；状态：confirmed（用户授权由实施方决策；按切片实施，每片自带测试）
- 规格：[M4 规格](../specs/2026-09-30-remediation-m4-identity.md)；任务级计划：[M4 计划](2026-09-30-remediation-m4-identity.md)
- 前置：M3 退出（33efbcb3）；Task 1 种子范围调研完成（[结论](../../../.ai/knowledge/2026-10-04-cloakbrowser-seed-range.md)）

## 关键决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 种子范围 | 10000..2³¹−1，新分配随机抽取，靠 `seed_registry.seed_value` 唯一约束冲突重试 | Task 1 实测内核接受且确定；旧值都在范围内，迁移不改值 |
| 身份与环境 | 身份 1:1 持有登录环境（`identities.environment_id`）；环境仍是保存/恢复的载体 | 复用 M3 环境存储与清理守卫，不复制第二套 |
| 记录关联 | 新增 `current_identity_id`；保留 `current_environment_id` 作兼容读，迁移后由身份推导 | 避免一次性改写全部读路径；M6 删除旧列 |
| 种子来源 | 运行时种子来自身份；浏览器配置不再生成种子（降级为模板），旧配置的种子只供迁移 | R4-11 |
| 出口地理 | 用 CloakBrowser 自带的 `geoip` 本地库（`cloakbrowser[geoip]` 已安装）解析出口 IP 的国家/时区，结果缓存 10 分钟 | 不引入外部服务；无库时按策略"警告继续/拒绝" |
| 粘性代理 | 身份首次用代理池时提交 `proxy_binding(pool_id, member_id)`；之后固定；失效按 sameRegion/confirm/never | R4-04；复用 `GroupService` 的候选列表 |
| perIdentity | 以 `identity_id` 为池键的长驻 worker 持有该身份的持久上下文；每个任务清空权限与注入的凭据；撤权/结果未知不归还 | 复用 M3 worker 池；持久上下文无法新开隔离上下文，所以只做"同身份串行" |
| 临时身份 | `sessionMode=pool` + 无登录：每任务一次性种子会改变进程级指纹参数 → 每任务重启浏览器，等价 perTask；明确记录"不支持任务级种子的池复用" | R4-08：不静默沿用上一任务种子 |

## 切片（每片：后端契约/实现 + 前端 + 测试一起完成）

### S1 身份与种子登记（Task 2）

- 迁移 `rm4_identities`：`seed_registry(id, seed_value UNIQUE, legacy_shared bool, created_at)`、
  `identities(id, project_id, name, template_profile_id, seed_id FK, timezone, locale, geolocation JSON, proxy_binding JSON,
  environment_id FK NULL UNIQUE, health JSON, created_at, updated_at)`、`identity_name_key` 项目内唯一。
- 领域 `domain/identities/`：`models.py`、`seeds.py`（`SEED_MIN/MAX`、`allocate(random) -> int`）、`region.py`（纯比较）。
- 仓储 `infrastructure/database/identities.py`：`allocate_seed()` 插入新登记（冲突重试 ≤ 8 次）；`attach_legacy_seed(value)` 仅迁移可用。
- `browser_launch_options` 放宽种子上限到 2³¹−1。
- 测试：1000 新身份种子两两不同、并发 8 线程分配无重复；公开创建不能指定种子或 legacyShared；旧值迁移可共享同一登记。

### S2 身份服务与接口（Task 3）

- `application/identities/service.py`：创建、从模板按数据表行批量创建（幂等键：表 + 记录键）、改名、重新生成种子（需 `confirmRegenerate`）、健康重置、删除（有活动实例拒绝）。
- HTTP `adapters/http/identities.py` + OpenAPI；前端 `domains/identities`：列表页（指纹摘要、地区、代理绑定、环境大小、最后使用、健康）与创建/批量创建抽屉。
- 测试：契约；批量创建幂等；记录删除后身份保留；重新生成种子后旧环境版本被 M3 清理守卫保留一次。

### S3 迁移（Task 8，提前到运行接入之前，保证老数据先有身份）

- `rm4_record_identity` + `application/identities/migration.py`：每个已保存环境 → 一个身份，种子/UA/语言/时区/内核取自环境冻结身份包；
  同种子多环境 → 同一 legacyShared 登记 + 迁移报告；记录 `current_environment_id` → `current_identity_id`。迁移前备份工作区数据库。
- 测试：AC4-05、AC4-06 的迁移部分；可重入；报告内容。

### S4 运行按身份恢复（Task 4）

- 领取带出 `currentIdentityId`；新环境来源 `inputIdentity`（替代 `inputEnvironment`，旧值迁移时自动改写）。
- `browser_resources.acquire` 按身份组装载荷：种子、地区、代理绑定、环境工作副本；身份独占沿用环境占用表（键改为身份）。
- End 保存登录状态写回身份的环境。
- 测试：同身份 3 次运行载荷一致（种子/UA/语言/时区/代理）；浏览器配置事后修改不影响已冻结身份；身份独占跨批次。

### S5 粘性代理（Task 5）

- `ResolveProxyForIdentity`：有绑定 → 校验成员可用 → 用；无绑定 → 从池选成员并提交绑定（与身份行同事务 CAS）；
  成员失效：sameRegion 选同地区成员并改绑；confirm 生成人工待办、任务记 infrastructure；never 身份不可用。
- 测试：首次固定；成员删除/禁用三种策略；并发两个任务同身份只绑定一次。

### S6 启动前地理校验与健康预检（Task 6）

- `domain/identities/region.py` 比较身份地区与出口解析；出口经代理测得（复用代理健康探针），10 分钟缓存；
  策略 reject/warn；探针或地理库不可用按策略；失败归 infrastructure 且不消耗行预算。
- 测试：AC4-04；服务不可用两种策略；预检失败不计尝试。

### S7 身份健康参与领取（Task 7）

- 领取过滤 banned / 连续登录失败 ≥ 3 的身份所关联的行，进入待处理列表；新节点"标记身份状态"（业务场景：多账号运营）；End 业务失败累计。
- 测试：AC4-02；重置后恢复领取。

### S8 perIdentity 会话（Task 9a）

- `sessionMode=perIdentity`：池键 = identity_id；worker 持有持久上下文；任务结束清权限、关闭多余页面、清会话存储；凭据/变量按运行重建；
  人工等待与空闲期间身份仍独占；撤权/未知结果不归还。
- 测试：AC4-07。

### S9 身份模板界面（Task 9，与 M5 5C 协作）

- 浏览器配置页改称"身份模板"，去掉种子展示；运行设置提供 perIdentity 选项（仅身份来源可选）。

### S10 黄金场景 G1 与验收（Task 10）

- G1 站点（登录、资料页、2% 密码错误）、本地 SOCKS 代理夹具（可注入断开与出口变化）；`tests/golden/test_g1_accounts.py`；AC4-01..07。

## 测量与环境

- 涉及批量执行的切片（S4、S5、S8）附 native-batch-v1 前后对比；测量前确认机器空闲并记录负载。
- macOS：逻辑审查 + CI macos-15；用户最终手动验证。
