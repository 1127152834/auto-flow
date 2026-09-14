# 自动化管理配置：逐图审查

2026-09-15。独立审查员实际打开原图与运行截图。评分为人工主观视觉评分，不是像素匹配；每页单独判定，没有平均分。用户手动验收未执行。

| 页面 | 原图 / 实图 | 人工评分 | 判定与偏差 |
|---|---|---|---|
| 基本信息 | [原图](../../../../prototype/project-management-pm3/automation-detail-overview.png) / [实图](../management-runs/run-eSwQYK/04-overview.png) | 89/100 | 通过：项目上下文、四页签、字段、摘要和保存栏一致；运行条件独占一行，字段略下移。 |
| 输入与参数 | [原图](../../../../prototype/project-management-pm3/automation-detail-inputs.png) / [实图](../management-runs/run-eSwQYK/02-inputs.png) | 86/100 | 通过：数据输入与六列参数表完整；编辑行较原图空态更高，内容密度尚可继续优化。 |
| 资源与环境 | [原图](../../../../prototype/project-management-pm3/automation-detail-resources.png) / [实图](../management-runs/run-eSwQYK/05-resources.png) | 90/100 | 通过：修正前82分；删除重复标题并对齐资源表后四行事实首屏完整，保存栏无遮挡。 |
| 运行设置 | [原图](../../../../prototype/project-management-pm3/automation-detail-run-policy.png) / [实图](../management-runs/run-eSwQYK/03-run-settings.png) | 88/100 | 通过：五组策略、实时摘要、保存栏一致；右侧摘要较原图偏左且更紧凑。 |
| 自动化目录 | [原图](/Users/zhangtiancheng/Documents/projects/autoflow/docs/references/project-management-prototypes-2026-09-13/latest/02-automation/001-automation-v1-approved-a45201.png) / [实图](../management-runs/run-eSwQYK/07-directory.png) | 90/100 | 通过：主体结构、数量、搜索排序、卡片和分页一致；卡片字与图标更小，有轻微阴影。 |

原资源页 `run-nQhPnq/05-resources.png` 82分不通过，四项资源事实不能在首屏完整显示；修复后仅复核该问题，在 `run-eSwQYK` 闭合。其他四页沿用同一实现，重新截图留存。历史截图未覆盖。

授权差异：全局顶部导航保持现状；Studio demo 联调排除；尚未接入批次启动不显示假运行按钮。资源“已选择”仅表示引用事实，不冒称许可、安装或启动就绪。真实数据量及未保存状态不扣为布局缺陷。

截图元数据见同目录运行 `result.json`：CDP viewport=1440×1024、DPR=1；原生窗口 contentBounds=1440×997，二者不能混称。200% 截图 CDP viewport=720×512、DPR=2、原生 zoomFactor=2。源码与构建 SHA256 均记录。

异常截图：离开确认、真实CAS冲突、响应未知及200%窗口另见运行目录；它们不是专门绘制的同状态原图，未给伪精确相似度。此次评分覆盖五张正常页面，不代表加载、保存中、全部错误分支和全部200%滚动位置均完成视觉验收。

候选截图没有被写成用户已确认回归基线。Windows、其他架构和打包未执行。

最终目录搜索按钮位置独立复核90分，无匹配画面88分；证据 run-eSwQYK/07-directory.png 与 11-no-match.png。已实际对照图库002-search-sort及007-no-results。
