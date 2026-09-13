# 概览、自动化与统计原型对齐

日期：2026-09-13
状态：design alignment（不是实施计划或验收结果）
实现工作树基线：`88efe07`

## 取证边界

本轮逐张通过 `view_image` 查看清单中 `latest/01-overview` 9 张、`latest/02-automation` 11 张、`latest/04-statistics` 11 张，共 31 张。下表“看图事实”只记录画面真实可见结构；“对齐决定”是结合现规格提出的新设计要求，两者不能互相冒充。清单的 `latestLocated` 只代表当前找到的最新稿，不自动产生新批准。

用户已确认保留应用顶部导航。三组页面统一保留：左侧全局导航、顶部返回/面包屑与窗口信息区、项目头、项目六页签。当前实现已有 `ProjectOverviewPage`、`ProjectHeader`、`ProjectTabs` 和 `ProjectsWorkspace`，应在其上对齐，而不是恢复旧整页壳。旧实现可复用依据见 `reviews/2026-09-13-prototype-alignment/legacy-reuse.md`：`ProjectOverview`、`AutomationListPanel`、目录交互和统计原型状态均有代码/测试来源。

## 逐图对齐表

| 原图 ID | 原图路径 | 实际看图证据/页面结构 | 动作或状态 | 需保留及差异 | PM阶段 |
|---|---|---|---|---|---|
| `PMUI-cd10948e1923` | `latest/01-overview/001-overview-cd1094.png` | 项目头+六页签；指标横条；左活动时间线、右关注/继续工作 | 活动行跳对象；关注修复；编辑项目 | 保留顶部全局栏、项目头和页签；演示计数不落产品 | PM1/PM3/PM7 |
| `PMUI-b960a779ac4f` | `latest/01-overview/002-activity-filter-b960a7.png` | 概览不变，最近活动右上展开筛选菜单 | 全部/数据变更/自动化配置/来源异常筛选 | 保留筛选与其他区块独立；筛选只影响最近活动 | PM1→各包 |
| `PMUI-734910769df0` | `latest/01-overview/003-activity-expanded-734910.png` | 时间线单行展开，内含对象、完成时间、数量和入口 | 展开/收起；打开当前数据表 | 保留行内展开；入口不得声称定位演示的120条 | PM1/PM2 |
| `PMUI-c2947aa44aa7` | `latest/01-overview/004-new-project-empty-c2947a.png` | 真实零值指标；活动空态；关注空态；继续工作空态 | 去自动化/去数据 | 保留双入口且说明自动化可无数据；零态须查询成功 | PM1 |
| `PMUI-e8dc42b85f0e` | `latest/01-overview/005-capability-unavailable-e8dc42.png` | 计数部分存在，活动区显示能力未接入 | 其他页签/继续工作仍可用 | 按能力独立降级，不把未接入写成0或项目故障 | 对应能力首次包 |
| `PMUI-6d99f9db578a` | `latest/01-overview/006-initial-loading-6d99f9.png` | 指标、活动、关注和继续工作分别骨架 | 等待加载 | 保留项目头/导航；未知总量不闪0 | PM1 |
| `PMUI-cae7e1c3cb38` | `latest/01-overview/007-activity-load-error-cae7e1.png` | 仅最近活动区错误，其他已加载内容保留 | 重新加载活动 | 局部重试，不清空指标/关注/继续工作 | PM1 |
| `PMUI-7d3ff7ccac9d` | `latest/01-overview/008-overview-load-error-7d3ff7.png` | 指标均为破折号+读取失败；三区各自错误 | 重新加载本页；仍可切页签 | 失败不是0且不暗示运行异常 | PM1 |
| `PMUI-bfd624d1cf4d` | `latest/01-overview/009-attention-return-bfd624.png` | 来源异常筛选保留，关注卡展开详情，底部返回提示 | 展开关注、检查连接 | 跨页返回恢复筛选/展开项/位置；Toast只是反馈 | PM1/PM6 |
| `PMUI-a4520177a6d5` | `latest/02-automation/001-automation-v1-approved-a45201.png` | 双列卡目录；搜索、排序、新建；卡含名称用途、配置状态、数据输入数、修改时间 | 开卡、新建、更多 | 保留配置状态与执行状态分离；卡片数据来自真实事实 | PM3-A |
| `PMUI-7bda3913caea` | `latest/02-automation/002-search-sort-7bda39.png` | 搜索名称/用途；排序菜单最近修改/创建/名称升降 | 输入、清除、选择排序 | 查询签名含project/q/sort/page，切换回第1页 | PM3-A |
| `PMUI-79f558a4954d` | `latest/02-automation/003-more-menu-79f558.png` | 卡片更多菜单含编辑基本信息/删除自动化 | 打开菜单、编辑、删除 | 菜单不触发卡片打开；键盘焦点返回 | PM3-A/PM8 |
| `PMUI-54c9040c9b1e` | `latest/02-automation/004-delete-confirm-54c904.png` | 删除Modal分“将删除/将保留”，名称确认 | 读取影响、输入名称、取消/删除 | 展示真实影响；不可撤销；名称确认；此图删除细节到PM8 | PM8-A |
| `PMUI-eb1bd069a3ca` | `latest/02-automation/005-delete-conflict-eb1bd0.png` | 删除影响过期冲突，输入禁用 | 重新核对影响 | 冲突不删除/不自动重试；重读后重新输入名称 | PM8-A |
| `PMUI-695f71d9b872` | `latest/02-automation/006-automation-empty-695f71.png` | 0项空态，中央新建入口；搜索排序栏隐藏 | 新建自动化 | 允许先保存空白草稿、无需数据输入 | PM3-A |
| `PMUI-8f42cb699f7b` | `latest/02-automation/007-no-results-8f42cb.png` | 搜索“周报”0结果，条件栏保留 | 清除搜索/调整关键词 | 与项目真空态分开；仍保留新建 | PM3-A |
| `PMUI-95c1cb5850e9` | `latest/02-automation/008-loading-95c1cb.png` | 六卡骨架、加载提示、总数读取中 | 加载期间保留查询控件 | 未知总数；旧结果不可混成当前结果 | PM3-A |
| `PMUI-b0e31b952e74` | `latest/02-automation/009-load-error-b0e31b.png` | 加载失败、总数未知，搜索词仍在 | 重新加载/修改关键词 | 保留条件；失败不显示0 | PM3-A |
| `PMUI-46a6a4f5d0b5` | `latest/02-automation/010-archived-readonly-46a6a4.png` | 项目已归档提示，卡片动作改“查看”，无新建/更多 | 搜索排序查看 | 只读仍可浏览；隐藏写入口 | PM1/PM3-A |
| `PMUI-6939c71803c5` | `latest/02-automation/011-page-return-6939c7.png` | 返回第2页、长名称两行、Toast，页码7–8/8 | 上一页/开卡 | 恢复q/sort/page/scroll；长名完整可访问 | PM3-A |
| `PMUI-14eafdf1b443` | `latest/04-statistics/001-statistics-v1-approved-14eafd.png` | 自动化+日期筛选；四指标；按日条；失败去向；资源占位 | 筛选、查看运行记录/失败记录 | 演示225/98.7%等不得落产品；真实查询截止时间 | PM7-B |
| `PMUI-eaef3ad61726` | `latest/04-statistics/002-date-range-eaef3a.png` | 快捷日期+双日期输入+月历，显示已选范围及时区说明 | 取消/应用 | 按项目统计时区与结束时间；未来日期禁选 | PM7-B |
| `PMUI-9160590b9793` | `latest/04-statistics/003-automation-filter-916059.png` | 可搜索自动化Select，全部项+搜索结果 | 搜索/选自动化 | 按稳定automationId筛选，重命名不改历史归属 | PM7-B |
| `PMUI-6704bb14fe85` | `latest/04-statistics/004-empty-6704bb.png` | 真实0任务；成功率/均耗时为破折号；空态 | 调整时间/清除筛选 | 分母0省略比率/均值，查看运行记录禁用 | PM7-B |
| `PMUI-ba31478a35ac` | `latest/04-statistics/005-loading-ba3147.png` | 筛选已更新，指标和分区骨架；入口暂禁用 | 等待新统计 | 切筛选不显示旧数字为新结果 | PM7-B |
| `PMUI-2a8897564195` | `latest/04-statistics/006-statistics-error-2a8897.png` | 所有指标破折号，中心错误；筛选保留 | 重新加载 | 统计读失败不等于自动化任务失败 | PM7-B |
| `PMUI-00b0dbc56af2` | `latest/04-statistics/007-frozen-drilldown-00b0db.png` | 运行记录任务页，显示“来自统计·失败任务”、固定筛选chips/范围/时区/快照 | 查看日志、翻页、返回统计 | 下钻绑定resultSet快照，不改查实时；顶部导航保留 | PM7-B |
| `PMUI-e9114406e7a0` | `latest/04-statistics/008-task-detail-return-e91144.png` | 任务详情日志页；返回任务列表；保留统计来源/范围；节点尝试与日志 | 返回列表、筛日志/切详情页 | 返回链维持统计快照；图中具体节点与编号仅示例 | PM7-A/B |
| `PMUI-dde8efe76b2d` | `latest/04-statistics/009-statistics-restored-dde8ef.png` | 回统计后恢复自动化/日期，Toast提示；快照50任务 | 继续筛选或查看记录 | 恢复筛选及原统计快照，不自动刷新 | PM7-B |
| `PMUI-8036c5ce20b2` | `latest/04-statistics/100-metric-definition-8036c5.png` | 指标名称更精确；截止时间+时区；刷新到当前；均耗时popover含公式/样本 | 打开说明、刷新到当前 | 口径说明可保留；具体2150秒/50是示例；刷新创建新事实集 | PM7-B |
| `PMUI-b18988a89e35` | `latest/04-statistics/100-refreshed-summary-b18988.png` | 刷新后截止13:35，52任务；Toast说明新增2 | 刷新反馈/查看运行记录 | 只展示真实前后差；不硬编码52/2 | PM7-B |

## 跨图页面结构

### 概览

保留项目身份头和六页签。内容按“摘要指标—项目活动—需要关注—继续工作”组织；各区独立加载、失败和重试。活动支持分类筛选与行内展开，关注事项给出直接修复入口，继续工作只展示真实最近对象。当前 PM1 概览可承载框架；活动与计数随 PM2/PM3/PM6/PM7 的真实投影逐步开放。

### 自动化目录

保留双列舒展卡、名称/用途搜索、最近修改/创建及名称排序、分页、新建、卡片打开和更多菜单。卡片展示配置状态、输入配置摘要和修改时间；“配置已保存/需检查/草稿”不能冒充执行状态。真空、搜索无结果、加载、失败、归档只读和返回恢复均为独立状态。完整删除影响在 PM8；PM3 不应提前实现无真实引用核验的删除确认。

这 11 张图只有目录及删除状态，没有自动化详情四页签。四页签字段、聚合保存、Studio 关联和启动确认必须来自 AU/API/执行合同及另行详情设计，不能从这些图片推导或伪造。

### 统计

保留自动化筛选、日期快捷项与自定义日期、明确时区/截止时间、已结束任务总量、成功率、失败数、平均总耗时、按日任务量、失败自动化去向、指标口径说明、刷新到当前及固定结果集下钻。统计、运行记录、任务详情形成可逆导航链，返回保留筛选和 resultSet 快照。

画面的 225、222、98.7%、36 秒、50、52、2 等全部是演示数据，不得作为默认值、验收阈值或种子数据。成功率、平均耗时、统计分母、时区和下钻过期处理以现 API 合同为准。资源使用区在原图明确“尚未采集”，不能据此宣称资源统计已实现。

## 主要差异与阶段约束

- 顶部导航：保留；同时使用现应用的导航组件和真实路由，不复制旧截图的静态日期、“静态原型·演示数据”标记。
- 概览：PM1 只提供已接入事实；后续能力不可用显示“未接入/不可用”，不得显示零。活动与关注必须由 DataChange、Operation、Batch/Task 等真实投影产生。
- 自动化：PM3-A 交付目录和管理配置；PM3-B/C 才出现真实启动与运行事实；PM8 才完成删除影响。目录状态必须一直区分配置健康与执行状态。
- 统计：PM7-B 才完整交付。PM3 的基础运行列表不等于统计聚合，也不应先填演示数字。
- 当前与旧复用：当前 `ProjectHeader`/`ProjectTabs`/`ProjectOverviewPage` 保留；旧 `AutomationListPanel`、`ProjectOverview` 及其交互测试用于迁移行为。统计旧图与测试是设计来源，数据必须接新 Batch/Task 查询合同。
