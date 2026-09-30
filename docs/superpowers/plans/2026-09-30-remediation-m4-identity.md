# M4 身份模型 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **本计划为任务级。** M3 通过退出评审后细化为步骤级并完成审查后执行。Task 1 是调研任务，其结论决定 Task 2 的种子范围方案。

**Goal:** 每个账号独立身份（新种子唯一/旧重复保留 + 粘性代理 + 冻结登录身份包），整体分配、恢复、校验；黄金场景 G1 达标。

**Architecture:** 新领域 `domain/identities`（纯规则）、应用 `application/identities`、持久化 `rm4_identities`；领取时带出身份并按身份恢复；代理粘性分配复用代理池能力；浏览器配置降级为模板。

**Tech Stack:** Python 3.11、SQLAlchemy + Alembic、CloakBrowser 0.5.9、现有代理管理模块；React。

**Spec:** [docs/superpowers/specs/2026-09-30-remediation-m4-identity.md](../specs/2026-09-30-remediation-m4-identity.md)

## Global Constraints

- 迁移默认保留原种子；共用种子的环境只进入报告，由用户决定是否重新生成；迁移前自动备份。
- seed_registry.seed_value唯一；新分配只插入新登记，旧身份可以迁移引用同一legacyShared登记；公开创建不可申请共享豁免，不在identities.seed值上设置拒绝旧重复的UNIQUE。
- 代理失效默认sameRegion，成员粘性不等于出口不变；检测实际出口变化并按策略核实，禁止静默跨地区。
- 同一身份同一时刻只有一个活动浏览器。
- 迁移文件前缀 `rm4_`。

## Review Focus

1. **两个批次同时为同一账号行创建身份**：唯一约束 + 幂等创建，只产生一个身份（Task 3 并发测试）。
2. **代理池成员被删除**：粘性绑定按策略替换或进入人工待办，不启动错误地区的浏览器（Task 5 测试）。
3. **地理位置服务不可用**：按策略"警告继续 / 拒绝"，结果可解释（Task 6 测试）。
4. **记录被删除但身份仍在**：身份保留，关联列表去掉该记录，不级联删除环境（Task 3 测试）。
5. **重新生成种子后旧环境**：旧环境代次保留可回退一次（Task 8 测试）。

---

### Task 1: 调研 CloakBrowser 种子范围

- 阅读 cloakbrowser 0.5.9 源码与文档，确认 `fingerprint_seed` 可接受的范围与分布；写入 `.ai/knowledge/2026-xx-cloakbrowser-seed-range.md`（含验证脚本与结论）。
- 产出：Task 2 使用的 `SEED_MIN`、`SEED_MAX` 与"可用种子低于 10% 提醒"是否需要。

### Task 2: 身份表与种子登记

- Files: `rm4_identities.py`、`domain/identities/models.py`、`domain/identities/seeds.py`、`infrastructure/database/identities.py`。
- Interfaces：seed_registry(seed_value UNIQUE)、identities.seed_id FK、迁移专属legacyShared关联；新分配不重用旧登记，不能合并不同账号身份。Tests：1000新身份/并发无重复；两个旧重复身份迁移成功并保留；公开API不能创建legacyShared；临时身份不宣称全局唯一。

### Task 3: 身份服务与接口

- Files: `application/identities/service.py`（CRUD、从模板批量创建、重新生成种子、健康重置）、`adapters/http/identities.py`、OpenAPI。
- Tests: 契约测试；按数据表行批量创建幂等；记录删除后身份保留。

### Task 4: 领取与运行按身份恢复

- Files: 领取路径（带出 identity_id）、`application/workflows/browser_resources.py`（按身份解析种子 / 代理 / 环境 / 地区）、End 保存登录状态写回身份的环境。
- Tests: 同一账号实际冻结身份包不受Profile后改影响，稳定代理夹具多次一致；出口变化另测策略；身份独占。

### Task 5: 粘性代理与失效替换

- Files: 代理解析新增"按身份解析"、成员失效策略、代理正在换 IP 时有限等待。
- Tests: 首次分配成员固定；成员删除和相同成员出口变化按三种策略；只有执行未开始的等待超时为可重排infrastructure，执行中按M2副作用门禁。

### Task 6: 启动前校验与代理健康预检

- Files: 出口 IP 地理位置检测（缓存 10 分钟）、地区一致性判断（`domain/identities/region.py`）、健康预检失败分类。
- Tests: 不一致按策略拒绝 / 警告；服务不可用的处理；预检失败不消耗行预算。

### Task 7: 身份健康参与领取

- Files: 领取过滤 banned / 连续失败身份；新节点"标记身份状态"；End 业务失败累计。
- Tests: 被封身份的行跳过并进入待处理；重置后恢复。

### Task 8: 迁移

- Files: `application/identities/migration.py`（环境 → 身份、记录"当前环境" → 身份、共用种子报告）、`rm4_record_identity.py`。
- Tests: 夹具工作区与两个重复种子环境都迁移成功，不合并账号；原身份包完整保留，报告legacyShared；重新生成后旧代次回退引用被M3清理守卫保留。

### Task 9: 身份模板与界面（与 M5 5C 协作）

- 浏览器配置页改为"身份模板"（不再显示种子）；项目内身份列表页（指纹摘要、出口 IP 与地区、环境大小、最后使用、关联记录、健康）。
- Tests: 组件与页面测试。

### Task 9a: perIdentity 会话（从M3移入）

- Files: `domain/project_automations/rules.py`、`application/workflows/browser_resources.py`、worker租借/归还及运行设置界面。
- Interfaces: 以identity_id为唯一租借身份，依赖Task2–5真实接口，不临时造另一种身份键；空闲/人工期间仍独占，任务级上下文隔离。
- Tests: AC4-07；撤权/未知结果不得归还，原命令核实后才解锁；临时身份种子与pool不兼容时明确perTask。

### Task 10: 黄金场景 G1 与验收

- 新增 G1 站点（登录、资料页、2% 密码错误）与本地 SOCKS 代理夹具（可注入 5 分钟断开）；`tests/golden/test_g1_accounts.py`。
- AC4-01 至 AC4-07 逐条勾选；更新 `.ai`（把"种子属于浏览器配置"的决定标记 superseded）；独立退出评审。
