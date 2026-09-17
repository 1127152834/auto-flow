# AutoFlow 全局精细网格交付

2026-09-14，基线 `bdca5ee`；独立分支 `codex/global-table-system`。用户选定第二种精细网格，现已接入 **14 处真实表面**：项目记录/字段/状态/来源/Excel、代理与代理组、模型，以及 Studio 虚拟表、变量表和两种 Markdown 表格。主目录未合并；同表新增、筛选语义、CAS、恢复和现有页面层级保留。

- [原型与实图对照](comparison.html)
- [源码使用点与边界](inventory.md)
- [手动验收与启动说明](manual-test.md)
- [机器核验报告](verification/report.json)
- [审查问题与修复](review.md)

## 已核验

| 范围 | 结果与证据 |
|---|---|
| 全量前端 | 254 文件 / 2,839 测试通过；见 verification/vitest-final.log |
| 工程 | typecheck、lint、build、OpenAPI、48 脚本、结构和表面扫描通过 |
| 组件与缩放 | [components-rOXBoV](runs/components-rOXBoV/report.json)，4 场景、10 张截图；真实组件，合成业务数据；14px、32px、内部滚动与下拉不撑宽 |
| Studio 宽表 | 10,000 行 × 12 列，虚拟DOM少于100行；PageDown及横滚对齐；屏外列头聚焦后headerX=rowX=-370 |
| 记录实际流程 | [run-J7B7of](../../project-management/design-alignment/acceptance/record-grid-entry/runs/run-J7B7of/report.json)，17组断言走通、20截图：UI录入/粘贴/编辑、字段竞争、响应丢失、重连/双工作区、筛选导出。脚本整体仍是partial，未执行项保持原样 |
| 字段与来源 | [run-RRCBkm](../../project-management/design-alignment/acceptance/gallery-r3/runs/run-RRCBkm/result.json)，12检查点、21截图：字段原子保存/冲突/恢复，状态/设置/Excel来源；文件面板结果明确为注入 |
| Studio 窗口 | [built-html.json](verification/studio-window/built-html.json)，真实主窗口、独立Studio窗口、重复打开、关闭及服务生命周期回归通过 |

截图对照仅审表格及其查询工具，不把原型中的示例数量、业务按钮或分页数字当成新增功能。多行模型名称/标识允许增高；普通表单及确认框按钮不被全局压小。当前屏幕背景和导航保持现状。

## 尚未运行

Windows、其他架构、打包版本、用户手测、真实外部代理/模型请求、完整执行流程中有数据的Studio变量表、原生中文输入法。既有记录QA的legacy/reimport未覆盖项仍保留；本轮不声称完成新的业务里程碑。独立工程审查无未闭合阻断。

## 重现

在本worktree运行 `node scripts/verify-table-system.mjs` 重新扫描；`npm test` / `npm run typecheck` / `npm run lint` / `npm run build` 为工程入口。GUI脚本串行运行，禁止并行争用原生窗口焦点及剪贴板。主线Studio脚本测试还需要 ignored `reference/WebRPA/backend/app/services/ai_assistant_module_schemas.py` 的冻结只读来源；本轮从主项目复制该文件，未执行其源码。脚本测试生成的无关Studio盘点资料已恢复原状。

自动证据保留失败尝试，最终通过目录以本文件为准，不能将所有runs目录都视作通过。开始手测前按manual-test.md新建隔离工作区，业务数据不参与验收。

提交用日志与DOM文本只去除行末空白和多余结尾空行，保留通过/失败内容；PNG及JSON事实不因此改写。
