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

后端真实专项最终 4 passed（其中 3 项使用实际浏览器），见 JUnit；前端专项 4 passed。回归跳过项未计作通过。

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

设计规格第 8 节列出的增强能力仍未完成；此切片不代表“所有行为、所有 JS”均已采集。结构化索引在关闭后读取，没有实时/崩溃恢复承诺；多会话目前明确提示仅显示最后归档会话。ZIP 为原始本地页面证据，不承诺内容已完全脱敏，只有主动下载，助手不会自动上传 ZIP。

实机：macOS 当前主机通过上述项目；Windows、macOS 其他架构、PyInstaller 与正式安装包未验收。项目任务 worker 尚未接入，不能从独立 Studio 路径推断已通过。模型的真实调用和批准/拒绝全矩阵尚未验收。
