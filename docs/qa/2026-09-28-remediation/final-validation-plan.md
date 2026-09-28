# 最终稳定版验收顺序与计数口径

日期：2026-09-28；状态：proposed（执行安排，非通过证据）。来源：用户本次验收要求、当前 npm scripts、生产 End 独立审查。

前置：End 两项 Important 修复并复审；Task4 共享进程归属修复并复审。Python 稳定后运行默认后端全量，此时只可并行独立前端 UI-02 切片；若测试期间再改 Python，该轮只能作为诊断，不能标为最终稳定版。

| 门禁 | 命令 / 执行位置 | 结果口径 |
| --- | --- | --- |
| 后端默认 | apps/backend：`.venv/bin/python -m pytest -q -ra --junitxml=<唯一文件> --basetemp=<本轮专属根> -p cleanup_diagnostic_plugin`；PYTHONPATH仅追加本次诊断目录 | passed/failed/skipped分别记录；诊断插件只记录原异常，不改变结果 |
| 真实浏览器 | AUTOFLOW_TEST_CLOAKBROWSER指向真实已安装内核，执行当前适用门控测试；单独XML与临时根 | 按参数化场景计数；真实执行后内部回执注入单列，不冒充实际断线或物理未知 |
| 冻结worker | 完成backend:build后设置AUTOFLOW_TEST_PROJECT_WORKER，执行数据及End真实正向链 | Python宿主调度+冻结worker，不能称整个Electron原生链 |
| 前端默认 | 根目录 `npm test` | 文件数和tests分别记录，不与历史定向检查相加 |
| 根脚本 | 根目录 `npm run test:scripts` | 原始失败保留；不改写历史验收文件 |
| 静态门禁 | Ruff src/tests、普通mypy src、strict增量检查；npm lint/typecheck/openapi:check | strict历史债务与新增问题分别记录，不称全仓strict通过 |
| 构建 | npm run build / backend:build / package:dir | 每个构建独立记录退出码及产物版本，不当成UI验收 |
| 迁移 | 迁移heads、升级路径、真实SQLite metadata与alembic check现有测试 | 新库/历史库路径分别记录，不改历史迁移 |
| 原生与重启 | 专属工作区启动当前打包应用，End配置保存重载、运行结果持久展示；UI-02真实断连恢复；原生导入导出原场景按变动决定重跑范围 | 原生动作、持久事实、进程退出证据互相核对；不把CDP状态注入计为用户操作 |

原生辅助脚本 `native-session.mjs <existing dedicated workspace>` 返回唯一证据目录。只读抓取使用 `native-evidence.mjs <该目录/session.json> <unique prefix>`；输出使用wx，不能覆写历史文件。脚本语法检查只证明语法，不证明当前应用已验收。

所有执行记录需包含实际HEAD及开始/结束源码稳定性、命令、cwd、有限环境设置、退出码、原始log/XML。不得记录令牌与用户凭据。专属临时根保留到必要证据归档，再按准确所有权清理。不同套件可能覆盖相同逻辑，禁止把各批passed相加成独立业务覆盖数量。

人工跨应用重启续接仍依赖既有待裁定差异；外部账号、付费模型、邮件消息发送、供应商变更、共享VM修复、Windows与Intel实机均不据本机结果算通过。当前尚不具备完整生产验收结论。
