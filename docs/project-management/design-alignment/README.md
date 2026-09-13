# 项目管理完整原型对齐设计

- 日期：2026-09-13。
- 当前状态：**设计已获用户确认；实施计划已编写，业务未开始**。批准依据见[决策记录](../../../.ai/decisions/2026-09-13-project-alignment-design-approved.md)，实施入口见[总计划](../../superpowers/plans/2026-09-13-project-management-alignment-implementation.md)。本目录其余proposed与历史核验记录保留原成稿语境，6组缺图仍未生成。
- 工作区：`autoflow-project-management-implementation`，基线 `88efe07`。主项目图库与旧仓只读。

先读[完整设计规格](../../superpowers/specs/2026-09-13-project-management-prototype-alignment-design.md)，其中包含页面结构、路由、草稿、状态、恢复、组件落点和分阶段验收边界。前轮[7组应用对照报告](../reviews/2026-09-13-prototype-alignment/README.md)说明已经确认的实现偏差，本轮不以新增源码测试替代视觉验收。

## 图像依据

来源是主项目[原始图库](/Users/zhangtiancheng/Documents/projects/autoflow/docs/references/project-management-prototypes-2026-09-13/gallery.html)。原文件不复制成另一套未注明来源的设计稿。

| 清单 | 实际审阅 | 内容 |
|---|---:|---|
| [项目、数据与公共模式](projects-data-shared.md) | 23 | 项目1+数据19+公共1+同日占用候选2；其中15张前轮已看，8张本轮补看 |
| [概览、自动化与统计](overview-automation-statistics.md) | 31 | 概览9+自动化11+统计11 |
| [运行记录与环境](runs-environments.md) | 39 | 运行21+环境18 |
| 合计 | 93 | 最新阅读集91+候选2；另19张历史稿明确排除 |

每张图都有ID、观察、动作和新系统适配决策；三个同名JSON是机器可读清单。[coverage.json](coverage.json)保留全部112个来源ID与原始标题/批准状态/hash，不把“最新阅读集”解释为全部已批准，也不把建议采用解释为已经实现。

观察到 `PMUI-3a2ef6f57afe` 的原始标题与画面不一致：文件名为删除影响预览，实际是删除完成结果。来源信息保持原样，实际观察另记；必须补真正的删除前影响画板。同日占用详情推荐紧凑候选，但两个候选的历史先后不能证明。

## 旧能力复用与补充

[自动化管理四页签补充](automation-management-supplement.md)从旧仓固定提交 `324748a` 提取字段、共享草稿、resolve/save、预览、冲突与资源往返。它弥补图库没有四页签的缺口，不声称已生成对应高保真图片。旧源码路径都基于 `autoflow-desktop/`。

推荐参数定义归工作流文档，自动化负责绑定和运行默认覆盖；该模型尚待确认。字段统一草稿/一次保存也需要新增聚合后端合同，现有单字段请求不能伪装成原子整体提交。其余经批准的PM0数据与运行规则继续有效。

完整规格列出6组 `ALIGN-*` 补图任务，均为**未生成**：四页签、聚合保存状态、记录整页、字段统一草稿、PM2文件/批状态增强和环境删除前影响。后续使用imagegen生成对应高保真图；不交付HTML替代原型。

## 核验与交接

- 运行 `python3 docs/project-management/design-alignment/verify-alignment.py`，核对93张审阅覆盖、112份原图哈希、来源ID、Markdown链接和JSON；结果见[verification.json](verification.json)。此脚本只验证设计资产。
- 独立审查和处理记录见[review-resolution.md](review-resolution.md)。
- 上一轮20张图审阅报告、PM0/PM1/PM2机器报告均保留为历史证据；新增93张覆盖记录在本目录，不改写旧报告。
- 本轮没有业务开发、业务测试、新的应用运行截图或Windows验收。已知PM2功能通过不等于原型视觉通过。
- 本规格确认后编写R1–R3详细实施卡、补图并逐包纠偏；完成相关纠偏和真实核心依赖核对后恢复PM3。当前PM3保持暂停。

## 已确认设计后的实施计划

[总计划](../../superpowers/plans/2026-09-13-project-management-alignment-implementation.md)拆成R1页面与目录、R2记录整页与恢复、R3聚合字段与完整数据回归，共18项实施任务；B0先补对应图稿，G1定义恢复PM3的工程门槛。文件责任/来源映射见[机器索引](implementation-plan-index.json)，计划自审见[审查记录](implementation-plan-review.md)，只读及静态结果见[计划核验](implementation-plan-verification.json)。本轮未开始业务实现。
