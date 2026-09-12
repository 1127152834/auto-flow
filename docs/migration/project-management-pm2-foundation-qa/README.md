# PM2 基础包上的 PM1 实际应用回归

- 日期：2026-09-13（机器 UTC 时间保留在 built-html.json）。
- 状态：passed，**仅 PM1 项目入口与已有模块回归**。
- 执行命令：`node scripts/smoke-project-management.mjs --output-dir docs/migration/project-management-pm2-foundation-qa`。
- 运行环境：macOS arm64，真实 Electron 构建 HTML 和真实 FastAPI，两个独立临时测试工作区。
- 源范围：PM2 身份/持久表/XLSX基础与表目录API存在；本次脚本没有使用PM2数据能力。
- 九组结果和截图见 [built-html.json](built-html.json)。检查涵盖新建/编辑项目、目录搜索分页和返回、真实CAS冲突、服务恢复、200%缩放下拉宽度、工作区隔离、已有模块入口与应用重启持久化。

**此时数据页仍显示“暂未开放”。这些截图不能证明字段、记录、状态、Excel导入导出、文件IPC、Sheets或项目真实执行已经交付。** 只有后续专项实际应用验收才可登记对应业务证据。Windows、macOS x64和发行包均未执行。

证据复核后为 JSON 补充 scope/scopeAnnotation；没有改变原 checkedAt、检查事实或截图。原 PM1 证据仍保留在 `../project-management-pm1-qa/`。

脚本工程复核发现旧参数解析把 `--output-dir --dev` 当合法目录，且默认路径会覆盖 PM1 截图。失败测试曾改动本工作区两张 PM1 截图，已从本分支 HEAD 的原始 Git blob 精确恢复，并用 `git diff -- docs/migration/project-management-pm1-qa` 确认无差异。新脚本先严格解析参数，默认创建独立运行目录，显式输出也拒绝 PM1 历史目录及其真实路径别名。无外部工作区被修改。
