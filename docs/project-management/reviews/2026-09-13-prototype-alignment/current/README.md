# PM2 当前实现截图证据

采集时间：2026-09-13（Asia/Shanghai）
状态：confirmed
验证方式：使用仓库现有 Electron/CDP smoke，在两个全新临时用户数据目录和隔离工作区中执行真实 UI 流程；运行结束后临时工作区由脚本删除。

## 截图

| 文件 | 页面或状态 | CSS viewport | PNG 像素 |
| --- | --- | --- | --- |
| `01-project-directory.png` | 项目目录；真实 55 项筛选结果，截图时列表已滚动 | 1440 × 1024 | 1440 × 1024 |
| `02-project-overview.png` | 项目概览及能力入口 | 1440 × 1024 | 1440 × 1024 |
| `03-data-table-directory.png` | 数据表目录；仅一张“客户资料”卡片，采集时仍为 0 条记录 | 1440 × 992 | 2880 × 1984（Retina 2×） |
| `04-records.png` | 记录列表，含真实字段值与业务状态 | 1440 × 992 | 2880 × 1984（Retina 2×） |
| `05-record-editor.png` | 记录编辑发生并发冲突后，仍保留本地草稿的弹窗 | 1440 × 992 | 2880 × 1984（Retina 2×） |
| `06-fields.png` | 字段页，字段经真实创建和影响确认后编辑 | 1440 × 992 | 2880 × 1984（Retina 2×） |
| `07-statuses.png` | 状态页，业务状态经真实创建和编辑 | 1440 × 992 | 2880 × 1984（Retina 2×） |

## 实际执行流程

- `node scripts/smoke-project-management.mjs`：通过 UI 创建、编辑、搜索和分页项目，打开项目概览，验证并发冲突、服务重连、200% 缩放、工作区隔离与应用重启。本次证据源运行：`docs/migration/project-management-regression-qa/run-W6Td3i`，结果 passed。
- `node scripts/smoke-project-data.mjs`：通过 UI 创建数据表、字段、状态和记录；编辑字段与状态；处理记录并发冲突；设置和清除记录状态；验证删除保护、未知写入恢复、服务重连、200% 缩放、工作区隔离与应用重启。本次证据源运行：`docs/migration/project-data-directory-qa/run-VoRvWR`，结果 passed。

PM2 采集实际运行了两次，且两次都通过。`run-577a57` 是第一次采集，生成了字段、状态和记录证据，但没有采集已创建数据表的目录画面。`run-VoRvWR` 是第二次完整运行，在相同步骤补充了数据表目录截图。它不是对失败运行的覆盖；两份原始 `result.json` 均保留完整结果和时间。

这些截图用于核对当前信息结构、控件和流程。`01-project-directory.png` 的 55 项筛选滚动状态，以及 `03-data-table-directory.png` 的单卡片、0 记录状态，与目标原型的数据量和滚动位置不同，不能作为逐像素对齐证据。

字段、状态和已填充数据表目录截图通过仅用于本次采集的临时 `capture` 调用生成；采集后已移除这些临时调用，业务代码及 smoke 的既有行为未改变。
