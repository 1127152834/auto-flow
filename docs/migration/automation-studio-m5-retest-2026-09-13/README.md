# M5 用户请求复测

日期：2026-09-13；状态：confirmed，全部本轮用例通过。测试提交：`d18cc82ac556eee790bd7da298b16263c3037ae0`。

本轮重新运行测试，未直接沿用此前通过结论。环境为 macOS arm64、CloakBrowser Chromium 145.0.7632.109.2；正式 AutoFlow.app 与冻结后端，独立临时工作区及本地多 origin 页面。原 M5 验收证据保持原样。

## 结果

| 检查 | 本轮结果 |
| --- | --- |
| 后端全量 pytest | 571通过，85.10秒 |
| 前端 Vitest | 427通过、66个文件，20.31秒 |
| 静态与契约 | Ruff、mypy（162源码文件）、TypeScript、ESLint、OpenAPI一致性通过 |
| 正式包一致性 | 包内renderer/main/preload共9个文件与当前构建产物逐字节一致；包内后端可执行文件与冻结产物一致 |
| 正式Studio界面 | 4组通过：真实画布编排/保存重开、变量修改/单步/页面列表、日志搜索/原生导出、暂停中的取消/保存冲突/放弃停止 |
| 冻结后端真实浏览器 | 8组通过，详见下列场景与JSON证据 |

真实浏览器核对了：跨域iframe中逐轮断点和修改值，结果为modified/second；重复单步不会多执行；定位失败保留浏览器，结束后仍failed；顶层直跑跳过前置，手动导航后执行；70KiB变量文件及导出完整；1000轮追加结果长度和末项均为1000；嵌套运行至此及纯变量暂停/停止；双层循环每次单步只增加一次调度，条件未选路径不产生点击；真实SIGKILL sidecar后清理受管浏览器，恢复为interrupted且不重放，可再次取得资源。

暂停离开保护使用真实revision冲突：取消及保存失败都保留草稿和暂停浏览器，放弃并停止后才切换新文档。检查截图确认调试控制栏可见，变量与诊断内容正常展示。

本轮未发现新的阻塞问题，业务代码无修改。测试创建的临时会话和工作区由验收脚本清理。置信度高，仅针对本轮实际执行的用例；Windows/macOS Intel未实机测试。本轮没有重新打包，使用与当前构建产物核对一致的正式包。

## 证据与重跑入口

- [工程统计](checks.json)、[命令与时间](run.json)。
- [正式UI四组](packaged-studio.json)、[冻结浏览器八组](frozen-debug.json)。
- [画布](packaged-editor.png)、[暂停与变量](packaged-paused.png)、[运行结果](packaged-executed.png)、[诊断搜索](packaged-diagnostics.png)。
- 后端：在apps/backend运行`uv run pytest -q`、`uv run ruff check src tests`、`uv run mypy src`。
- 前端：根目录运行`npm test`、`npm run typecheck`、`npm run lint`、`npm run openapi:check`。
- 真实入口：根目录运行`node scripts/smoke-workflow-debug-studio.mjs --executable apps/desktop/dist/mac-arm64/AutoFlow.app/Contents/MacOS/AutoFlow`及`node scripts/smoke-workflow-debug.mjs --executable apps/backend/dist/autoflow-backend/autoflow-backend`。
