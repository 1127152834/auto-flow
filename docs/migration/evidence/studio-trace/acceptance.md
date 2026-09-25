# Trace 第一切片验收

日期：2026-09-26；状态：部分实现、部分验收。规格：[设计](../../../superpowers/specs/2026-09-24-studio-cloakbrowser-trace-design.md)。

## 范围及隔离

基于 `2cc06c63`，工作树 `studio-trace`、分支 `codex/studio-trace`。主仓库、架构基线工作树及用户数据库未修改。临时独立 Electron userData、临时 SQLite 与本地受控网页；仅使用已安装 CloakBrowser 145.0.7632.109.2，包装版本 0.5.9。证据不能推定其他内核或平台通过。

## 实际通过

| 验收 | 结果与证据 |
| --- | --- |
| 真实采集 | `tests/integration/test_workflow_trace.py`：真实点击改变 DOM，同时记录网络、Console、JS 异常、PNG 和 native ZIP；归档全部登记为 diagnostic |
| 正常和停止收尾 | 同文件两个真实子进程用例：正常完成与等待期间停止均先归档，manager 活跃进程归零，归档可读取 |
| 索引边界 | 损坏/缺失文件 422/404、跨项目 404、分类/分页、重复 finish、采集失败保留原失败状态；见 [JUnit](backend.xml) |
| 组件和工具 | `trace-panel.test.tsx` 4 项：快照、对比、正确 run 下载、分页、无证据、迟到响应、助手显式 run 与有界查询 |
| 现有链路回归 | worker 协议/进程/项目读取 81 passed、3 skipped；助手 LangGraph/合同/service 23 passed（测试替身，不是实际模型调用） |
| 开发 Electron | 真实 UI 新建 Profile，拖入打开网页节点，填写 URL，保存，F5 运行；真实浏览器退出后显示网络/控制台/异常/快照 |
| UI 筛选/下载 | JS 异常筛选只显示受控错误。原生保存对话框下载 ZIP：14,601 bytes、8 entries、存在 .trace、CRC 校验通过 |
| 小助手交接 | 点击交给小助手填入 run/evidence 引用、不自动发送。临时工作区没有模型，发送禁用；未宣称真实模型推理通过 |
| 正常关闭恢复 | Cmd+W 关 Studio，主窗口重开，真实打开保存流程，历史快照仍可读取；[截图](electron-reopen.png) |
| 构建入口 | 完整 main/preload/renderer 构建后，退出应用，用 file HTML 入口重启；主窗口进入 Studio，旧 Trace/PNG 恢复，节点名称来自运行快照；[截图](electron-built-history.png) |
| 工程检查 | TypeScript、定向 ESLint、Ruff、定向 mypy、OpenAPI check、git diff --check、main/preload/renderer build 通过；构建保留已有大 chunk/混合导入告警 |

后端真实专项最终 5 passed（其中 3 项使用实际浏览器），见 JUnit；前端 Trace 专项 6 passed；加节点范围测试共 9 passed。回归跳过项未计作通过。

运行方式（仓库根目录）：
```sh
PYTHONPATH="$PWD/apps/backend/src" AUTOFLOW_B1_CLOAK_EXECUTABLE="<已安装 CloakBrowser 可执行文件>" apps/backend/.venv/bin/python -m pytest apps/backend/tests/integration/test_workflow_trace.py -q
npm --workspace @autoflow/desktop test -- src/renderer/domains/workflows/tests/trace-panel.test.tsx
npm run typecheck
npm run openapi:check
npm run build
```
依赖环境是本机已有环境的符号链接；子进程需显式 PYTHONPATH，避免 editable 安装指向其他工作树。第一次相关回归因该环境指向错误失败，修正启动环境后原断言全部通过。

## 剩余及限制

设计规格第 8 节列出的增强能力仍未完成；此切片不代表“所有行为、所有 JS”均已采集。结构化索引在关闭后读取，没有实时/崩溃恢复承诺；多会话首切片只显示最后归档的限制已由下方增强切片解除。ZIP 为原始本地页面证据，不承诺内容已完全脱敏，只有主动下载，助手不会自动上传 ZIP。

实机：macOS 当前主机通过上述项目；Windows、macOS 其他架构、PyInstaller 与正式安装包未验收。项目任务 worker 尚未接入，不能从独立 Studio 路径推断已通过。模型的真实调用和批准/拒绝全矩阵尚未验收。

## 同轮诊断节点追加验收

- 真实 worker 用例扩展为打开、提取、标记、快照、保存片段五节点：三节点全部 node_complete success；PNG/DOM 引用均存在、组件无缺失；片段首项为选定标记，包含快照事件、不含之前打开网页事件；全程原生 ZIP 仍生成。
- 关闭追踪时保存片段明确 TRACE_NOT_ENABLED；跨会话/不存在标记明确报错；敏感关联值不原文写入标记。
- 前端共享默认值和三个表单测试；冻结源目录仍严格 213 个，不恢复排除项。界面 219 = 原 213 + 项目 3 + 诊断 3。
- 真实 Electron：画布快捷菜单加入标记、填写参数与变量、手动保存、F5 后日志显示实际节点成功。快照节点入口、默认变量 diagnostic_evidence、DOM/截图/控制台三项开关及保存验证；[原生可访问树](electron-diagnostic-config.txt)。没有调用 Store 或内部页面函数模拟操作。
- DOM 页面内容按文本渲染，不建立 HTML 元素；助手 DOM 分段读取、8,000 字符上限、错误 ID 和缺失原文均有组件/工具合同测试。无模型真实调用证据。
- 新节点最终完整 UI 连线重放、项目任务执行路径、跨框架快照、独立可移植片段仍待验收，不能从 worker 测试推定通过。

最终相关回归：LangGraph 单元、助手合同、助手 service 与 worker 协议合计 47 passed；与前述 23 项有重叠，不累计成独立通过数量。最终 TypeScript、定向 ESLint/Ruff/mypy、OpenAPI 和 main/preload/renderer 构建均通过。三个诊断节点之后的构建成功，构建 HTML 原生历史恢复证据属于前一切片，未冒用为新增三节点完整端到端证据。临时应用正常退出，测试 userData 和下载文件已清理，未替换用户主应用。


## 增强源码、多会话与模式持久化（2026-09-26）

- 后端关联回归 **130 passed**：[JUnit](backend-enhanced.xml)。最终补充真实worker增强源码断言后，Trace专项 **9 passed**：[最终Trace JUnit](backend-trace-final.xml)。两者重叠，不相加。4个实际Cloak用例：标准页面、增强页面、正常worker、停止worker。
- 实际网页外部脚本和内联脚本内容归档可读；增强页含 debugger 语句，导航在5秒预算内完成，后续点击及JS异常仍可确认；正常worker接收冻结 enhanced 字段，归档包含 window.workerTraceProof=17 的实际脚本。
- 发现并修复两项真实失败：并发直接丢弃导致内联脚本漏采，改100任务有界队列/4并发；仅skipAllPauses无法阻止 debugger 暂停，增加关闭CDP断点激活。失败用例保留原断言。
- 源码去重、单值及累计容量、超限缺口、未知模式拒绝、运行投影和保存往返；多manifest交错时间、页ID相同、分页、过滤、错误traceId及精确证据身份有可执行用例。
- 前端 Trace/文档导出/结构复制/节点范围关联回归 **32 passed**；其中Trace **10**。覆盖模式历史与导入、旧快照隔离、源码惰性文本展示、助手有界读取、已有归档时活跃运行继续刷新、跨会话禁止同页对比、所属ZIP下载及真实Radix会话筛选。
- 构建HTML正式Electron UI：独立临时userData、独立测试应用标识；主窗口→Studio→运行菜单选择“增强：同时采集网页 JS”→填写Trace Enhanced QA→Cmd+S，出现保存成功→Cmd+W正常关闭Studio→主窗口重开→“打开”选择保存流程→运行菜单增强项Value1、标准Value0。随后Cmd+Q正常退出。没有通过Store或页面内部函数操作。
- 此UI证据是模式保存重开，不冒充增强源码显示/多会话浏览器完整UI验收。当前临时主应用无Profile、无模型；实际源码来自独立后端受控测试。
- TypeScript、ESLint、Ruff、定向mypy、OpenAPI一致性通过；main/preload/renderer构建通过（原有chunk/混合导入告警保留）。构建后的模式重开通过；此轮不是PyInstaller冻结包或安装包验收。
- 本次仍隔离于codex/studio-trace，未修改用户应用或数据库、未合并。真实模型诊断、项目任务接入及设计11.2列出的其余缺口不能标为完成。
