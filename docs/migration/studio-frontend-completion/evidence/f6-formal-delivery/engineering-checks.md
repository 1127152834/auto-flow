# F6 工程与产物检查

日期：2026-09-15；平台：macOS arm64。

| 检查 | 结果 |
|---|---|
| 前端全量 Vitest | 330 个文件、4,979 项全部通过；267.04 秒 |
| 前端 TypeScript | `tsc --noEmit` 通过 |
| 前端 ESLint | `eslint .` 通过 |
| OpenAPI 一致性 | `generate-api.mjs --check` 通过 |
| 工程脚本 | 首次 48/50；发现 227 节点范围已生效但必填字段脚本仍写死 284。修复范围边界并重生成后 50/50 通过 |
| 227 范围关联回归 | 5 个文件、32 项通过；数据库和 DP 不进入目录、设置、教学、自定义分类或必填元数据 |
| 后端合同 | 503 项通过，2 条第三方弃用警告 |
| 后端 mypy | 202 个源文件，无错误 |
| renderer/main/preload 构建 | 通过；`studio.html` 与主入口同时生成 |
| PyInstaller 后端冻结 | 通过；产物位于 `apps/backend/dist/autoflow-backend` |
| Electron 目录包 | 通过；`apps/desktop/dist/mac-arm64/AutoFlow.app` |
| 打包宿主 smoke | 通过；打包 sidecar 启动，宿主被终止后 sidecar 退出 |
| 开发入口 Studio smoke | 通过；见 `development-url.json` 与 `development-url.png` |
| 打包入口 Studio smoke | 通过；见 `packaged.json` 与 `packaged.png` |

## 检查中发现并处理的问题

`moduleCatalog.ts` 和交付清单已经执行用户批准的 227 节点范围，但 `export-studio-required-fields.py` 及其测试仍要求 284，导致工程脚本首次失败。修复只调整批准数量、重生成覆盖清单，并增加数据库与 DP 的显式排除断言；没有恢复节点或放宽覆盖检查。

## 不属于本批的仓库状态

全后端 `ruff check apps/backend/src apps/backend/tests` 报告 109 个既有 import-order 问题，分布在项目数据、内核、代理、模型及其测试中。本批没有修改这些 Python 文件，也没有用自动格式化改写其它任务成果；后端合同和 mypy 均通过。该结果作为仓库级代码风格债务记录，不冒充 F6 通过项。

Electron 目录包未签名：当前机器没有有效 Developer ID Application 证书，同时包仍使用默认 Electron 图标且 package metadata 缺 description/author。这不阻止本机目录包启动和正式 Studio smoke；对外分发前仍需发布证书及品牌元数据。

macOS Intel 与 Windows 没有可用实机，本批不标通过。
