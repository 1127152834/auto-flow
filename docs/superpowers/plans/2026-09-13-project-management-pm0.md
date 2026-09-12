# PM0 项目管理契约与实施基线执行计划

> **面向 AI 代理的工作者：** 使用 subagent-driven-development 逐任务执行；规格符合性审查之后进行工程质量审查，交付前使用 verification-before-completion。writing-plans 用于本执行卡。用户已确认此计划并明确要求实施，无需重复询问执行方式。

**目标：** 将已确认的项目业务设计转成前后端共用的契约、责任、可复用验收样例及可追溯交付清单。

**架构：** 单 FastAPI/SQLite；Studio 唯一执行器；项目通过应用端口协调业务数据、批次及环境，平台操作在适配器。PM0 仅交付实施依据。

**技术栈：** 现有 Python/FastAPI/SQLAlchemy/Alembic、Electron/React/TypeScript、shadcn/Radix/Tailwind。静态核验使用 Python 标准库，不引入依赖。

**规格：** [完整设计](../../project-management/design/README.md)、[里程碑](2026-09-13-project-management-milestones.md)、[确认记录](../../../.ai/decisions/2026-09-13-project-management-pm0-authorized.md)。历史设计基线 906deda；总计划基线 349c4be。

- 日期：2026-09-13；状态：PM0实施完成、静态核验通过；用户阶段验收pending，PM1未开始。
- 工作区：autoflow-project-management-design，分支 codex/project-management-design；其他工作区只读。
- 验收点：本阶段交付后等待用户 PM0 验收；不自动进入 PM1。

## 文件与职责

以下路径相对 `docs/project-management/implementation/`，非现成业务实现。

| 文件 | 操作 | 单一职责 / 修改负责人 |
|---|---|---|
| current-baseline.md | 更新 | 实際提交/WIP/迁移/UI来源；主协调 |
| contracts.md | 新增 | 对象及18张执行契约；数据契约智能体，主协调定稿 |
| api-contracts.md | 新增 | 路由、错误、事件、IPC和集成；接口智能体，主协调定稿 |
| fixtures.json | 新增 | FX-01–07及跨里程碑合成场景；主协调 |
| execution-ledger.md | 新增 | 交付包、文件/角色、依赖和验收事实；主协调 |
| coverage.md / coverage.json | 更新 | 48功能、178场景、18契约、7门槛；主协调 |
| plan-verification.json | 更新 | 本次实际核验与未运行边界；主协调 |
| verify-pm0.py | 新增 | 可重复运行的文档/编号/样例核验，非业务测试；主协调 |

同时更新本执行卡、总计划当前状态、`docs/PROJECT_STRUCTURE.md` 和 `.ai/` 索引。保留历史设计快照，不修改 apps、packages、运行数据、后端接口或其他任务文件。

## 固定业务规则

- 每表单值 statusId 或 null，目录初始为空；只有人工或明确节点修改。
- 再次使用只看当前条件，活动 lease 防同时冲突；不建立消费类型或批内历史过滤。
- Task、原始输入、lease、环境预约和 queued CoreRun 同一短事务提交；浏览器/文件/网络在事务外。
- RecordRef 包含完整身份与类型；内容、状态、关联、结构修订分别维护；原输入不可变。
- 查询只读，写入显式非阻塞取权并CAS；已确认的本任务写入推进自身版本，其他写入不会被静默覆盖。
- End 保留包含上下文保存与约定关联；部分成功保留修复证据，不改历史Run或自动重跑网页。

## 任务1：实际基线与职责

- [x] 记录设计、主项目、UI、旧项目 HEAD、工作树状态及读取时刻。
- [x] 标记已有、其他分支已有、WIP、设计目标；登记 source SHA/文件指纹。
- [x] 核对迁移图、Studio入口和已完成控件来源，列出能力门槛及文件所有者。
- [x] 审查基线中的证据路径及“已实现/已验收”措辞；旧结论标 superseded。

交付：current-baseline.md、execution-ledger.md 基线部分。检查：Git只读状态、迁移脚本AST、现有源码，不启动其他任务的应用或导入其数据库。

## 任务2：领域与18项契约

- [x] 建立共享对象及字段定义；向接口任务提供同一命名来源。
- [x] XE-C01–C18逐张填写调用方/提供方、输入输出、幂等、前提、错误、事务、查询恢复。
- [x] 明确领取、写入、停止、人工及End状态转换；列提交前/后/丢响应事实。
- [x] 逐条对照设计编号，审查全输入事务、独立版本、End修复和不可变证据。

交付：contracts.md。检查：18张卡完整、类型有定义、状态和已确认设计一致，不声称接口已编码。

## 任务3：前后端传输与集成

- [x] 枚举项目各子资源路由，标记包、请求/响应、项目归属及错误。
- [x] 统一已有camelCase/错误封装/Idempotency-Key惯例，明确202接受和按原身份找回结果。
- [x] 明确核心Run唯一权威、共享UoW和事件序号/补读；核对Studio WIP差异。
- [x] 固定受控文件IPC、迁移先后/单一集成人及真实handler生成DTO的流程。
- [x] 对照contracts.md检查类型/归属/状态，审查路由与错误是否重复或缺失。

交付：api-contracts.md。检查：路由method/path唯一、每个持久命令可查询、未实现接口有明确阶段而非空handler。

## 任务4：业务样例

- [x] 写入FX-01–07固定初始身份/内容/版本，初始null与显式状态初始化分开。
- [x] 提供步骤、预期变化/运行事实、不变证据、阶段与验收ID。
- [x] 提供参数、多表显式写入、环境二次使用三条流程；版本竞争、响应丢失、停止/恢复纳入分支样例。
- [x] 检查样例外键、类型、固定值及引用，全部为合成数据和描述性流程，不冒充可执行Studio IR。

交付：fixtures.json。检查：7套基线完整，三条代表流程有步骤和具体断言，运行证据保持空。

## 任务5：覆盖、审查、交付

- [x] 每个功能/场景/契约/门槛指定交付包、负责人、测试目标、验收方式与依赖。
- [x] 区分开始和完整退出依赖，核对各包形成有向无环图。
- [x] 完成独立规格审查，修正后完成独立工程质量审查；修复并复核问题。
- [x] 运行以下静态检查，读取退出码和报告；更新AI索引及阶段验收状态。
- [x] 仅暂存本阶段文件，形成独立PM0提交；检查提交范围及工作树。

```bash
python3 docs/project-management/implementation/verify-pm0.py
python3 -m json.tool docs/project-management/implementation/fixtures.json > /dev/null
python3 -m json.tool docs/project-management/implementation/coverage.json > /dev/null
git diff --check
```

预期：脚本退出0，集合精确为48/178/18/7，样例7、代表流程3；本次业务证据为空，文档链接/引用/依赖正确。核验脚本只读取文件并输出报告；plan-verification.json由主协调记录实际输出、源码快照、审查和未运行项。

## 并行及验收

用户指定的独立文件并行优先于技能中避免并行修改的默认指导：数据与接口分别独占一份文档，根代理负责其他文件；公共签名、迁移和生成类型只由集成者定稿。普通文档任务使用gpt-5.6-sol，独立审查按规格和工程质量先后进行。

交付只证明PM0契约与静态基线完成。pytest/Vitest业务测试、应用交互、CloakBrowser流程、Sheets实网与Windows/macOS平台验收均未执行，留在对应里程碑。下一阶段需用户验收PM0后进入PM1。
