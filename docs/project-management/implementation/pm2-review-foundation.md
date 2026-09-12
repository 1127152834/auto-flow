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
