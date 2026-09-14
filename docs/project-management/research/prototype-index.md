# 项目管理原型使用索引

日期：2026-09-12；状态：文件存在性及 SHA256 confirmed；非本轮逐图视觉验收。

[原始总目录](/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/Prototype-Assets-20260911/) · [原始说明](/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/Prototype-Assets-20260911/README.md) · [完整哈希清单](prototype-manifest.json)

198 个 PNG 文件，按内容去重后 112 张。多个目录含同一稿的副本；不可把文件数当作独立页面数。

## 作为六面板起点的快照

| 模块 | 图数 | 主稿入口 | 使用说明 |
|---|---:|---|---|
| 概览 | 9 | [活动优先](/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/Prototype-Assets-20260911/01-audit-snapshot/01-overview-01.png) | 保留活动→对象→返回，数字必须来自新系统事实 |
| 自动化 | 11 | [舒展条目](/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/Prototype-Assets-20260911/01-audit-snapshot/10-automation-01.png) | 这组主要是列表与状态，不代表四页签/Studio 内页全部定稿 |
| 运行记录 | 21 | [批次主视图](/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/Prototype-Assets-20260911/01-audit-snapshot/21-runs-01.png) | 覆盖任务、日志、输入输出、异常和人工；未实现的运行不能伪装为真实 |
| 统计 | 9 | [轻量汇总](/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/Prototype-Assets-20260911/01-audit-snapshot/42-statistics-01.png) | 细化规则需叠加后续统计 v2；候选不等于已批准 |
| 数据 | 17 | [数据表目录](/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/Prototype-Assets-20260911/01-audit-snapshot/51-data-01.png) | 图中的外部 SQLite 来源已与最新两来源方案不符，需局部重绘 |
| 环境 | 10 | [现场优先](/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/Prototype-Assets-20260911/01-audit-snapshot/68-environment-01.png) | 需叠加最新维护与清理规则；可折叠摘要替代不必要的侧栏 |

项目列表另有 [单独入口图](/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/Prototype-Assets-20260911/04-standalone/01-projects-prototype.png)。六面板快照共 77 张；早期 initial-design 共 96 个 PNG，仅用于追溯确认关系和被替代方案。

## 最新修订

| 批次 | 图数 | 内容与状态 |
|---|---:|---|
| [数据规则 v2](/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/Prototype-Assets-20260911/02-refinement-20260910/data-rules-v2/) | 3 | 占用记录、字段影响、Sheets 双方向；候选 |
| [公共控件 v1](/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/Prototype-Assets-20260911/02-refinement-20260910/shared-controls-v1/) | 7 | 公共状态与多页面应用；视觉细节以新 AutoFlow 已统一控件为准 |
| [统计规则 v2](/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/Prototype-Assets-20260911/02-refinement-20260910/statistics-rules-v2/) | 3 | 口径、刷新、冻结下钻；规则候选 |
| [环境维护 v1](/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/Prototype-Assets-20260911/03-refinement-20260911/environment-maintenance-v1/) | 4 | 列表、名称备注、冲突、删除影响；其中列表/重命名已有更高版本 |
| [环境维护 v3](/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/Prototype-Assets-20260911/03-refinement-20260911/environment-maintenance-v3/) | 2 | 当前归档中版本最高的持久列表和重命名抽屉；未找到对应批准记录，不自动升级为已确认 |
| [环境规则 v2](/Users/zhangtiancheng/Documents/projects/browser-automation/.ai/01-Project-Management/Prototype-Assets-20260911/03-refinement-20260911/environment-rules-v2/) | 5 | 保存警告、失效引用、清理未知/失败/完成；候选 |

## 后续需要补图的具体范围

1. 四页签自动化管理与新 Profile 资源选择；旧五步启动动线不再复刻。
2. 数据目录移除 SQLite；Excel 本地 CRUD；Sheets 发送后必经核验及同源绑定冲突。
3. 批次资源固定、任务写回冲突、失联待核实与人工现场容量提示。
4. 持久环境独占维护/工作副本的入口、保存和引用删除影响。
5. 统计同一结果版本的下钻/失效恢复，以及真实归档/删除长操作。

这些是总体方案通过后需补充的原型范围，本轮未生成新图。不要根据旧图重新引入全局左栏、独立内核页或多余资源侧栏。
