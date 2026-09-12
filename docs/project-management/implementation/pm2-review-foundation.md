# PM2 基础包审查记录

日期：2026-09-13。状态：inProgress。范围：身份/标量、迁移/ORM、Excel解析；不是完整PM2。

## 迁移规格审查

- P1 当前代次缺完整作用域FK：已通过延迟复合FK修复，新增失败→通过测试，禁止不存在或其他项目/表代次。
- P2 change.project_id与operation_id可分别指向不同项目：已加复合FK及父表唯一索引，本次迁移维护，不改PM1历史。
- 独立规格复核通过；13项迁移测试通过，包括重启impact身份不复用、downgrade/upgrade和PM1数据保留。工程质量审查发现并修复 SQLite legacy 模式半迁移：显式 BEGIN IMMEDIATE 使 DDL 与 alembic_version 同事务；base/pm01 中途失败后无残留可重跑。独立工程复核通过，连同PM1仓储和HTTP共31项通过。

## 领域规则规格审查

- P1 日期offset重复编码与PM0契约相反：修复中；value必须不带offset，offset独立保存。
- P1 隔开量词仍可导致不可控回溯：修复中；增加成熟regex引擎timeout，不依赖手写子集声称线性。依据[regex官方超时说明](https://pypi.org/project/regex/#timeout)，timeout覆盖整个匹配操作。
- P2 巨大整数、非法offset、畸形精度和巨大重复计数泄漏异常：修复中，统一领域422。

## Excel规格审查

- P1 全部行驻留内存，公式来源丢失，表头公式注入和读取路径竞态：修复中。
- P2 日期导出损精度/offset拒绝，operation时间预算未覆盖整个workbook：修复中。
- 16项初始测试通过不等于规格验收。修复后重新做定向测试、独立复审，再工程质量审查。

真实Electron、IPC、HTTP、Google实网、Windows及其他架构：本包未执行。
