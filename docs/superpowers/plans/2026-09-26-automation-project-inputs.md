# 自动化与项目输入一体化实施计划

日期：2026-09-26。状态：approved；来源：用户完整贴回修订版并要求 IMPLEMENT。

## 约束
项目→多个自动化→每个唯一工作流。自动创建空白工作流，不提供重新绑定。Studio 项目数据为对象属性面板，输入定义/调试输入/本次任务三个视图；候选单选、分页搜索、默认首个完整组。选择不占用、不改配置。真实单任务调试精确领取指定组，重新验证版本/条件/关系/权限/占用，不自动替换。显式写入、原始快照不变、任务写游标推进、失败保留已提交修改。多输入原子领取，可选空值明确。保持历史和独立工作流兼容，不增加执行器、代理策略或跨自动化编排；releaseAccepted=false。

## Task 1: 自动化专属工作流
原子幂等创建与 HTTP 契约；删除选择下拉；Studio automationId 上下文和归属校验。RED→GREEN：创建/重试/冲突回滚、旧请求拒绝、更新替换拒绝，界面创建与打开契约。

## Task 2: 项目输入上下文与面板
复用稳定 inputId/inputFieldId/parameterId，独立只读表达式上下文；节点字段选择和当前对象写入；输入定义/调试输入/本次任务组件。RED→GREEN：类型/缺失/改名/隔离、对象展示、历史不变。

## Task 3: 指定候选单任务调试
候选查询、组预览、分页/搜索/占用和关系；批次 debugSelection 精确领取、版本保护、幂等；Studio 保存并运行一次，事件/任务绑定。RED→GREEN：第三条、失效/忙/关联/可选空、只一个任务、真实注册状态推进后常规取下一条。

## 验证
针对性 pytest/vitest 后进行 typecheck、lint、OpenAPI 和 build，以及相关后端回归；真实 HTTP/worker/桌面验收复用已有设施。最后独立整分支审查；只提交本功能分支，不合并发布。

## 实施结果
三个切片已实现并本地验收。2026-09-26 生产 HTTP + Electron + worker 的指定第三条/正常批次重新筛选通过；详细映射和基线遗留失败见 docs/project-management/implementation/automation-project-inputs/README.md。只进入草稿评审，releaseAccepted 仍为 false。
