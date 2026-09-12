# PM2 基础包审查记录

日期：2026-09-13。状态：inProgress。范围：身份/标量、迁移/ORM、Excel解析；不是完整PM2。

## 迁移规格审查

- P1 当前代次缺完整作用域FK：已通过延迟复合FK修复，新增失败→通过测试，禁止不存在或其他项目/表代次。
- P2 change.project_id与operation_id可分别指向不同项目：已加复合FK及父表唯一索引，本次迁移维护，不改PM1历史。
- 独立规格复核通过；13项迁移测试通过，包括重启impact身份不复用、downgrade/upgrade和PM1数据保留。工程质量审查发现并修复 SQLite legacy 模式半迁移：显式 BEGIN IMMEDIATE 使 DDL 与 alembic_version 同事务；base/pm01 中途失败后无残留可重跑。独立工程复核通过，连同PM1仓储和HTTP共31项通过。

## 领域规则规格审查

- P1 日期offset重复编码与PM0契约相反：已修复并通过规格复核；value必须不带offset，offset独立保存。
- P1 隔开量词仍可导致不可控回溯：已修复并通过规格复核；增加成熟regex引擎timeout，不依赖手写子集声称线性。依据[regex官方超时说明](https://pypi.org/project/regex/#timeout)，timeout覆盖整个匹配操作。
- P2 巨大整数、非法offset、畸形精度和巨大重复计数泄漏异常：已修复并通过规格复核，统一领域422。

- 工程复核：总量词展开≤10000、禁用用户pattern隐式全局缓存、统一UPPER_SNAKE错误码；63项测试通过，独立工程复核通过。

## Excel规格审查

- P1 全部行驻留内存，公式来源丢失，表头公式注入和读取路径竞态：修复中。
- P2 日期导出损精度/offset拒绝，operation时间预算未覆盖整个workbook：修复中。
- 16项初始测试通过不等于规格验收。修复后重新做定向测试、独立复审，再工程质量审查。

真实Electron、IPC、HTTP、Google实网、Windows及其他架构：本包未执行。

Excel原七项规格问题复核通过，工程审查新发现字符串32768截断、ContentTypes无界解压、未关闭worksheet生成器、writer临时文件残留和坏数字解析异常；修复中，尚未验收。

## Excel B1 最终复核

原七项规格问题、五项工程问题全部闭合；最后修复公共迭代边界的数值解析异常（表头和数据），避免仅流读取处理而inspect泄漏。定向30测试、Ruff/mypy通过，独立工程复核通过。接口read_sheet返回可关闭的ExcelRowStream/ExcelRow，inspection保留有限sample及全量公式来源统计。这里只是文件适配，文件IPC、持久inspection、原子发布和实际导入页面尚未交付。

## A2a 表资料与目录 API 最终复核

规格闭合：原始UUID先验证后转换；name/description孤立surrogate、q控制字符统一422；Unicode casefold搜索维护持久search_text（本阶段未发布pm02结构同步补齐）。工程闭合：CAS冲突在回滚前捕获currentRevision，避免释放锁后ORM刷新混入另一次写入。35项仓储/HTTP测试、17项命令恢复测试通过，独立工程复核通过。

四个真实HTTP操作为表目录GET/POST和详情GET/PATCH；项目Operation查询扩展真实createTable/updateTable结果。数据记录、字段、状态和文件IPC仍未交付，因此没有启用数据页能力或冒充完整PM2。

前端纯组件规格问题（session、父级关闭、busy确认、fixture）及工程问题（render阶段ref副作用）全部闭合。session/epoch变更改在useLayoutEffect提交生命周期；startTransition + Suspense回归证明被丢弃的B渲染不污染已提交A的请求。独立工程复审通过，13项组件测试、TypeScript和ESLint通过；稳定代码全量前端461项通过。组件尚未装配正式数据页，不能作为PM2页面验收。

## A2c 字段修改影响确认基础

完整FieldRef/RecordRef、规范change、table/fieldRevision和全量当前记录事实绑定持久确认，10分钟有效；预检不创建Operation。最初实现把逐值规则验证放在数据库事务内，真实并发写反例复现SQLite锁失败后，改为只读快照提取单值投影到2MiB spool，释放读事务后运行规则。最终写入前由调用方同一短事务重新计算事实摘要；旧确认必须412。18项集成测试、Ruff/mypy通过，独立规格与工程审查均通过。

当前只有预检/复验适配器，字段PATCH尚未接入。后续必须在同一BEGIN IMMEDIATE中复验后立即修改并提交操作事实；没有该真实调用链时不能标记字段编辑交付。

## A2b 字段与状态目录审查（进行中）

原P1状态更新幂等摘要遗漏statusId、P1字段/记录变更缺数据代次、P2修订超出JSON安全整数均已修复，规格复核通过。43项目录/原表回归通过，包含默认回填中途失败整体回滚。工程发现无默认值的可选字段仍加载全表记录，正在改为按需查询和有界回填；未经最终复核不提交本包。

### A2b 最终闭合

工程复核通过：无默认值时不读取整表；真实回填按200条流式读取/flush并释放ORM实例，仍一次最终commit。独立451条有效记录+3条删除记录验证无遗漏/重复，452条证据；第403条证据失败时此前flush的所有批次完整回滚。44项仓储/原表回归通过。

HTTP独立复审发现可省略状态PATCH字段在OpenAPI中错误声明可null；已用非nullable字段与default_factory、exclude_unset组合修复，显式null422、仅name更新保留color/order。8项HTTP测试、生成类型检查、TypeScript、Ruff/mypy通过，规格与工程最终复核通过。字段GET/POST、状态GET/POST/PATCH及统一操作查询均为真实接口；字段编辑和记录操作不在本次HTTP交付范围。

## A2d 记录命令最终闭合（2026-09-13）

记录 create/get/update/set_status 的独立规格审查发现标量摘要先于校验导致非法数值/Unicode泄漏，以及 keyType 未完整校验；均已修复。原始值保持类型、不trim，字段规则在幂等结果查询后校验，历史重放不受后来字段变化影响。规格和工程复核通过；14项记录测试及独立非法/合法标量探针通过。最后补齐应用、领域、仓储类型边界，畸形identity.fieldId统一422且无持久残留，独立复核再次通过。记录/字段和HTTP合计33项定向回归通过，Ruff全量通过，mypy 163源文件通过。

本包只有显式创建、单条读取、内容修改和业务状态设置。状态清空推进statusRevision，内容和关联修订分别维护；未实现记录列表、删除、执行占用或完整PM2页面。
