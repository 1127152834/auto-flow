# R1 交付与验收

R1 开发与 macOS arm64 本机自动验证完成，等待用户验收。基线 `1e79c7b`，应用代码 `4daa752`，隔离验收工具 `a13e649`。最终自动运行已记录提交、脚本 SHA256 与实际 Electron 构建 SHA256；文档提交不改变应用构建。

交付最近/全部项目目录、紧凑页面层级、数据卡片、筛选/排序/选列浮层、指定文本字段搜索及统一通知。顶部导航和真实 PM2 功能保留。R2 记录整页、R3 字段聚合保存未开始。

## 开始手测

```bash
cd /Users/zhangtiancheng/Documents/projects/autoflow-project-management-implementation
npm run build
node scripts/qa-project-alignment-r1.mjs --manual
```

工具创建独立测试工作区并保持 Electron 打开。按[手动测试方案](manual-test.md)执行 R1-M01–09；先通过界面建立 A/B 和资料库，再用 seed 生成分页样本。终端可制造真实竞争编辑、模拟读取故障/提交后响应丢失、重启服务/应用、切换测试工作区。输入 clean 仅清理本次标记目录，保留截图。

## 已验证与证据

- 前端 **115 文件 / 865 项**；后端目录/组合查询定向 **21 项**；脚本 **22 项**、结构 **3 项**通过。类型、lint、OpenAPI、构建通过，日志见[机器报告](verification.json)。
- [最终 R1 Electron 报告](runs/run-tpXDVQ/result.json)：真实界面新建、最近顺序、50/2 分页、120 行文本搜索、60 行一致导出、三个浮层及200%、原键找回、409、服务/应用重启和双工作区。
- [PM2 编辑回归](pm2-data-result.json)与[批状态/Excel 回归](pm2-detail-result.json)：保留旧业务断言，覆盖表/记录编辑恢复、状态、源文件不变及旧代次隔离。一万行导入6363ms、下一页158ms为本机实测。
- [规格和工程审查](review-resolution.md)、[静态覆盖检查](static-verification.json)。B0 历史报告不改成业务验证，也不放宽其旧门槛。

## 同视口截图

| B0 画板 | 实际应用 |
| --- | --- |
| R1-A | [最近项目](runs/run-tpXDVQ/r1-a-recent.png)、[全部目录第二页](runs/run-tpXDVQ/r1-a-all-page2.png) |
| R1-B | [数据目录](runs/run-tpXDVQ/r1-b-directory.png) |
| R1-C | [记录工具栏](runs/run-tpXDVQ/r1-c-records.png)、[筛选](runs/run-tpXDVQ/r1-c-筛选.png)、[排序](runs/run-tpXDVQ/r1-c-排序.png)、[显示列](runs/run-tpXDVQ/r1-c-显示列.png) |
| R1-C 200% | [筛选](runs/run-tpXDVQ/r1-c-筛选-200.png)、[排序](runs/run-tpXDVQ/r1-c-排序-200.png)、[显示列](runs/run-tpXDVQ/r1-c-显示列-200.png) |
| 异常 | [读取失败](runs/run-tpXDVQ/r1-read-failure.png)、[响应丢失](runs/run-tpXDVQ/r1-lost-response.png)、[真实冲突](runs/run-tpXDVQ/r1-real-conflict.png) |

窗口内容基准1440×1024；200%时CSS视口缩小，搜索区分行、浮层内部滚动，不以应用宽度变化容纳内容。图稿示例字段/数量不填入正式页面。

## 尚未执行

用户逐项手测、Windows、其他架构、打包应用、原生文件面板手动选择及表格软件核对。自动文件流程注入系统面板返回，实际文件 IPC、后端和 XLSX 写入/解析真实。浏览器/代理/模型/设置/Studio 本机检查仅入口，完整功能仍需手测。未修改主项目、旧仓及原三个 QA 目录；并行任务状态不由本任务认定。

收到 R1 问题先修复复验，用户确认后才进入 R2。

## 2026-09-13 用户反馈后的视觉复审

状态：**visualReviewReopened / changesRequired**。用户指出项目列表及其他页面未忠实对齐原型，随后用 CUA 采集 27 张当前截图完成[逐页对照审查](../visual-audit-2026-09-13/README.md)。项目目录、记录列表层级及查询浮层仍有 R1 范围内偏差；记录整页和字段整体草稿继续属于 R2/R3，不能混为 R1 已交付内容。

历史自动检查和功能测试证据保留其原有范围，不作为视觉对齐通过依据。本条更新当前视觉验收状态，不修改旧报告的历史执行结果。当前不进入 R2；本轮仅交付审查资料，没有修改业务实现。
