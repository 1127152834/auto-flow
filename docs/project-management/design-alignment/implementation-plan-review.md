# 对齐实施计划自审

- 日期：2026-09-13。
- 状态：计划静态审查完成；18项实施任务均未开始。
- 方法：按writing-plans要求由主协调自审，不派子智能体代替计划自审；执行阶段仍按用户既有要求进行分包和独立规格/工程审查。

## 已修正的计划问题

| 问题 | 最终处理 |
|---|---|
| 假定已存在Popover或独立Drawer文件 | 实际只有Modal支持drawer placement；只补Radix Popover，复用overlay-host和原Select宽度保护 |
| 将impactRevision理解为数据变更版本 | 它是DataImpactRow身份；R3新增内部schema_guard_revision及当前代次记录事务触发器，结合tableRevision和预览摘要验证 |
| 原始计划alembic命令没给配置路径 | 改为 `alembic -c src/autoflow/infrastructure/database/alembic.ini heads`，已只读运行确认pm02_excel_exports |
| 误写scripts/lib驱动目录 | 实际复用scripts/electron-cdp.mjs；明确临时user-data与真实页面操作 |
| 最近项目取自当前搜索页会失真 | 独立固定最近查询；输入搜索转全部模式；未访问项不充当最近访问 |
| UUID记录恢复校验遗漏 | 代码validTarget仅text/integer；R2加入UUID恢复反例和规范校验，不放宽后端身份 |
| 空表合法fields=[]与空请求混淆 | 缺candidate必填属性422；空表的完整空字段候选合法，无变化提交不推进修订 |
| 文件责任短名有歧义 | Files行统一为完整路径；核对既有路径，新增文件标Create或依赖前包Create；根package-lock位置明确 |
| 参数权威已经批准却仍列作用户阻塞 | 新批准ADR覆盖旧成稿状态，G1只保留工程合同/能力前置，不再重复问用户 |

## 覆盖与限制

B0覆盖图稿基准；R1覆盖公共外壳/卡片/查询工具/反馈；R2覆盖记录路由/表单/详情/外链/恢复；R3覆盖聚合结构/迁移/事务/HTTP/状态引用/页面/全模块验收。G1标明参数合同、真实核心依赖和迁移汇合，后续PM3–PM9继续原里程碑，不宣称有新业务实现。

机器索引见[implementation-plan-index.json](implementation-plan-index.json)，校验结果见[implementation-plan-verification.json](implementation-plan-verification.json)。它检查18任务、文件责任、无环依赖、112来源ID与计划/排除/未来阶段的映射，不验证网页动作、事务故障或跨平台行为。原图核验及PM0/PM1/PM2报告原样保留。

参数/字段设计已确认，不代表尚未生成的5组本轮画板已确认。B0对真实图稿的review是具体视觉验收；没有图就不能勾图稿完成。
