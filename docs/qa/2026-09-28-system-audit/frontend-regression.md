# 前端与工程回归实测

- 日期：2026-09-28（Asia/Shanghai）。状态：confirmed，失败原因中尚未验证的部分单独标明。
- 源码：`33ae3aa49600840b1700c83723408c494dc201a8` 加当前工作树；开始时已有用户文档改动，尤其 `docs/migration/studio-frontend-completion/component-tools.json`，测试按当前工作树执行。
- 环境：macOS，本机 Node `v26.7.0`、npm `11.19.0`、uv `0.10.6`；失败复核使用已安装的 `/usr/local/bin/node` `v22.17.1`，与 CI 的 Node 22 主版本一致。
- 本报告范围：所有已注册前端 Vitest、所有脚本单测、结构、TypeScript、ESLint、OpenAPI 一致性和 Electron Vite 构建。没有修改业务源码或生成 API 源码；审计产物由主任务统一提交。
- 这些是辅助回归证据：Vitest 全局 setup 明确配置 Studio mock；本报告不将其当作真实服务、真实浏览器或真实外部系统 E2E 成功证据。真实 Electron/UI 和后端业务场景由同次审计其他报告记录。

## 执行结果

| 检查 | 实际命令 | 结果 | 证据 |
|---|---|---|---|
| 前端全量 | `npm test -- --maxWorkers=2` | **失败**：428 文件中 421 通过、7 失败；5628 测试中 5574 通过、54 失败；190.60 秒 | [vitest.log](frontend/vitest.log) |
| 失败集 Node 22 复核 | `/usr/local/bin/node ../../node_modules/vitest/vitest.mjs run --maxWorkers=2` 加下文 7 个文件，cwd=`apps/desktop` | **失败**：7 文件、54 失败、1160 通过；11.08 秒；失败集合与全量一致 | [vitest-node22-failure-recheck.log](frontend/vitest-node22-failure-recheck.log) |
| 类型 | `npm run typecheck` | 通过，退出 0 | [typecheck.log](frontend/typecheck.log) |
| ESLint | `npm run lint` | 通过，退出 0 | [lint.log](frontend/lint.log) |
| OpenAPI | `npm run openapi:check` | 通过，退出 0；没有运行 generate 或改写生成文件 | [openapi-check.log](frontend/openapi-check.log) |
| 结构 | `npm run test:structure` | 4 通过、0 失败 | [structure.log](frontend/structure.log) |
| 脚本全量 | 在隔离快照执行 `npm run test:scripts` | **失败**：96 项中 92 通过、4 失败；1.81 秒 | [scripts.log](frontend/scripts.log) |
| 构建 | `npm run build` | 通过，退出 0；renderer 构建 35.22 秒 | [build.log](frontend/build.log) |

全量命令中的 `--maxWorkers=2` 被根脚本转发给 npm 而不是 Vitest，npm 打印了 Unknown cli config 警告，因此该次实际使用 `vitest.config.ts` 中的 4 workers。Node 22 定向复核直接调用 Vitest，实际使用 2 workers。全量没有被该参数缩小范围。

`test:structure` 的 4 项也包含在 `test:scripts` 96 项中，不能把两者简单相加当作独立覆盖。Node 22 复核同样不是新增 1214 项覆盖。

## 失败分类与复现

| 文件（均相对于 `apps/desktop`） | 失败数 | 发现与判断 |
|---|---:|---|
| `src/main/index.test.ts` | 3 | 两项明确因 FakeWindow 缺 `hide()` / `isVisible()` 抛 TypeError；工作区确认一项返回 `ok:false`，调用路径同样经过 Studio 关闭回调。此为测试替身与主进程实现不一致，不能据此宣布真实 Electron 的窗口/工作区功能失败。 |
| `src/renderer/domains/workflows/tests/catalog-field-contract.test.ts` | 31 | 当前组件字段清单与冻结的字段验收账本不一致，失败发生在第 65 行的面板字段映射断言。包括 network_capture 的 3 个旧字段和 AI 节点的 apiKey/apiUrl/model 等。源码 `AIModuleConfigs.tsx:23,74,101-109` 已改为 modelId，并主动清除旧凭据字段；至少 AI 这部分是当前设计与历史账本冲突，不应简单恢复旧字段以消除红灯。 |
| `src/renderer/domains/workflows/tests/shared-control-entry-wiring.test.tsx` | 16 | 14 个已从当前目录排除的通知节点仍从历史 cases 装配测试，另两项为 AI 生图/视频直接 VariableInput 入口已变化；第 52-54 行只按工具类型过滤，未按当前保留节点过滤。 |
| `src/renderer/domains/workflows/tests/documentation-loading.test.ts` | 1 | **实际产品文案缺陷**：已加载的通知教学包含被排除的 notify_discord，断言第 54 行失败。见下文。 |
| `src/renderer/domains/workflows/tests/module-scope.test.ts` | 1 | 第 7 行仍要求 213，实际为 216。 |
| `src/renderer/domains/workflows/lib/__tests__/moduleColors.audit.test.ts` | 1 | 第 235 行仍要求核验 213，实际为 216；失败点是计数，不是颜色差异。 |
| `src/renderer/domains/workflows/lib/__tests__/helpers/addNodeDefaults.test.ts` | 1 | 第 89 行字段分布快照不一致：resultVariable 实际 114、基线 115；variableName 实际 15、基线 14。仅凭本断言不能判定运行时变量错误。 |

上述 7 个文件是 Node 22 复核的完整参数列表。54 个失败在 Node 22 全部重现，不能归因于 Node 26 输出的 localStorage 实验性警告。

脚本 4 个失败：

1. `scripts/inventory-studio-completion.test.mjs` 在模块导入阶段执行生成器，`scripts/inventory-studio-completion.mjs:26` 拒绝 216 个节点；该文件内部测试未执行，Node test runner 将它计为 1 个失败文件项。
2. `scripts/studio-docs.test.mjs:5` 调用 `audit-module-docs.mjs:26`，同样仍冻结 213。
3. `scripts/studio-required-fields.test.mjs:57` 调用 `export-studio-required-fields.py --check`，生成器第 79-80 行仍冻结 213。
4. `scripts/studio-required-fields.test.mjs:62` 的第 67 行仍要求 capabilities 长度 213，当前文件为 216。

## 可确认的问题

### F-01 / P2：新增能力没有同步验收合同，当前分支没有绿色回归基线

置信度：高。`moduleCatalog.ts:5` 已新增 `proxy_change_ip`、`proxy_change_location`、`proxy_query`，与 2026-09-25 已确认的代理控制决策一致；多个校验器仍散落着硬编码 213。它们让全量测试、中文文档审计、能力清单再生成和必填字段再生成同时失败。新增节点不是未经批准的范围漂移，问题是批准后的变更未贯穿检查链。

除了数量，历史节点字段、通知工具 cases 和变量分布基线也与当前实现分叉。因此不能把“生成类型/lint/build 通过”解释为“系统已完成全量验收”。应逐项按已批准能力核对账本；不能直接删掉断言或批量改数字来制造通过。

### F-02 / P2：正式教学仍宣称支持已移除的通知渠道

置信度：高。`apps/desktop/src/renderer/domains/workflows/components/documentation/content-notify.ts:6` 明确称支持 16 种通知渠道；第 35 行起提供 Discord 的配置与使用步骤，第 78 行起提供钉钉，另有其余已排除通知节点。`contents.ts:34` 仍将该文件登记为 `notify-guide`，`loadDocContent()` 真实加载其原文。当前目录只保留获准通知渠道，用户按照教程会寻找不存在的节点。

教学开头还统一保留“Mock 用于交互演示，不执行真实网页、模型或系统操作”的迁移期说明（例如该文件第 4 行）。这属于文档状态没有随真实后端接入更新，不能代替逐能力的真实可用性声明。

### F-03 / P2：工程检查会改写受版本控制的验收证据

置信度：高。`scripts/inventory-studio-completion.test.mjs:6` 与 `scripts/studio-service-inventory.test.mjs:9,48` 在检查期间调用生成器；生成器分别在 `inventory-studio-completion.mjs:178` 和 `inventory-studio-services.mjs:138,170` 写入 capabilities/test-cases/component-tools/service-inventory/contract-matrix。检查不是只读，且部分目标文件在本次开始前已有用户改动。

本次采取隔离复制：复制 scripts 和 studio-frontend-completion 目录，其余仅作为读取输入链接；从临时目录运行完整 scripts 命令，生成器只改临时副本。路径与策略保存在 [script-isolation.json](frontend/script-isolation.json)。没有覆盖用户已有证据。建议检查使用临时输出或纯 `--check`，把再生成作为显式动作。

## 构建观察与覆盖边界

构建有两条动态/静态 import 混用提示，涉及 getting-started 教学文档和 workflows/events。构建成功；这些提示本身不是运行故障证据。

输出 JS 中主入口约 2.55 MB、Studio 约 3.32 MB、共享 useDesktopSession chunk 约 5.08 MB、按需 AICodeAssistant chunk 约 7.34 MB（均为构建报告中的未压缩大小）。这是后续启动/内存/打开编辑器性能测量的输入，不凭体积直接宣称卡顿。

本机检查不能证明 Windows、Intel、签名安装包、原生文件选择、真实外部账号和所有节点都可用。当前证明的是上述命令已真实执行、工程门槛中哪些通过/失败，以及失败对当前代码的准确影响。

## 当前源码 macOS arm64 发行产物验证

2026-09-28 补测，状态：confirmed，置信度：高。基于同一源码 `33ae3aa49600840b1700c83723408c494dc201a8`，没有业务代码改动。系统 macOS 26.4.1 / arm64，Python 3.11.13，PyInstaller 6.22.2，electron-builder 26.15.3，Electron 41.10.3。

| 检查 | 实际命令（仓库根目录执行） | 结果 |
|---|---|---|
| frozen backend 构建 | `UV_OFFLINE=1 UV_FROZEN=1 npm run backend:build` | 退出 0，PyInstaller 构建 167.56 秒；现有 187 个 Python 依赖已满足，没有下载 Python 依赖。 |
| 目录包 | `CSC_IDENTITY_AUTO_DISCOVERY=false npm --workspace @autoflow/desktop run package:dir -- --config.mac.identity=null --config.mac.notarize=false` | 退出 0；生成 `apps/desktop/dist/mac-arm64/AutoFlow.app`；日志明确跳过 macOS 应用签名。 |
| 独立 frozen sidecar | `npm run smoke:sidecar -- --executable apps/backend/dist/autoflow-backend/autoflow-backend` | 退出 0；独立临时数据目录启动，真实 ready 和带 token 的 `/health` 返回匹配 instanceId，随后回收进程与临时目录。 |
| 包内 sidecar | `npm run smoke:sidecar -- --executable apps/desktop/dist/mac-arm64/AutoFlow.app/Contents/Resources/backend/autoflow-backend` | 退出 0；验证实际复制进 .app 的 sidecar，而非源码 Python。 |
| 真实 packaged Electron | `npm run smoke:desktop -- --executable apps/desktop/dist/mac-arm64/AutoFlow.app/Contents/MacOS/AutoFlow` | 退出 0；独立 `--user-data-dir`，真实 packaged renderer 通过 preload 取得 sidecar 状态并访问 `/health`；终止宿主后 sidecar 健康端口消失。日志输出 `desktop connected (packaged, darwin/arm64)` 和 `sidecar exited after desktop termination`。 |

执行 smoke 时显式移除了继承环境中的 `AUTOFLOW_BASE_URL`、`AUTOFLOW_INSTANCE_TOKEN`、`AUTOFLOW_HOST_TOKEN`、`AUTOFLOW_QA_SIDECAR_MODULE` 和 `AUTOFLOW_PM4_QA`，packaged desktop 还移除了 `ELECTRON_RENDERER_URL`。测试凭据由 smoke 脚本为本次临时实例生成；没有使用 fake sidecar、外部 readiness、开发服务器或用户工作区。

证据目录为 [frontend/package/](frontend/package/)：

- [backend-build.log](frontend/package/backend-build.log)
- [package-dir.log](frontend/package/package-dir.log)
- [frozen-sidecar-smoke.log](frontend/package/frozen-sidecar-smoke.log)
- [embedded-sidecar-smoke.log](frontend/package/embedded-sidecar-smoke.log)
- [packaged-desktop-smoke.log](frontend/package/packaged-desktop-smoke.log)
- [input-metadata.json](frontend/package/input-metadata.json) 与 [artifact-metadata.json](frontend/package/artifact-metadata.json)：源码、输入锁文件/规格摘要、产物 SHA256、架构、签名及历史安装包保留核验。

可重建的 ignored backend build/dist 与 mac-arm64 .app 使用标准输出目录更新。已有 `AutoFlow-0.1.0-arm64.dmg` 及 blockmap 保留，前后 SHA256 一致；没有生成新的 DMG、安装或发布。`uv.lock`、`package-lock.json`、PyInstaller spec、electron-builder 配置前后 SHA256 一致。包内 sidecar 可执行文件 SHA256 与本次 frozen backend 完全一致。

签名边界：没有使用 Developer ID、TeamIdentifier 或公证。PyInstaller 和 Electron 的 Mach-O 保留/生成了 macOS arm64 本地运行所需的 **ad-hoc** 签名；`codesign -dv` 显示 `Signature=adhoc`、`TeamIdentifier=not set`，不是可发行签名或完整 bundle 签名验收。目录包磁盘占用约 2.22 GiB，frozen backend 约 1.51 GiB（`du -sk`，精确值见 metadata）。

构建警告包含未采集的 MediaPipe LLM converter、TensorBoard 等可选模块，以及扫描到的 Windows/Linux 动态库名字；当前基础启动通过，不能由此推断所有 ML/OCR/桌面节点都已在冻结包里验证。electron-builder 还提示缺少 description/author、使用默认 Electron 图标和重复依赖引用，均没有阻断目录打包。其日志记录了 Electron archive 下载/解压阶段，因此仅 backend 构建可称本次明确的离线构建，不能把整个桌面打包描述为已证明离线。

这轮退出证据是现有 smoke 脚本的**宿主进程终止与 backend 父进程回收**，没有把它描述为原生菜单 Cmd+Q 正常退出、安装升级、Gatekeeper、签名公证或全工作流功能验收；Windows x64、macOS Intel 仍未在本机执行。

## Studio JS 场景的测试构造校准

2026-09-28，confirmed，置信度：高。`ui-realqa.mjs` 初次通过 API 构造的节点使用了 `type:'custom'`、`data.moduleType:'js_script'`。只读检查隔离 QA SQLite 确认保存的文档原样保留该矛盾结构（工作流 `d4e82c4a-535a-41db-96ef-ca62579f6847`，revision 1）。

`editor-store.ts:3278-3316` 的正式导入逻辑只把 `moduleNode/groupNode/noteNode/subflowHeaderNode` 识别为画布格式；其他普通节点按存储格式读取 `node.type`，所以该节点加载后 `data.moduleType` 被转成 `custom`，而原 `label:'JS脚本'` 保留。随后的运行快照会携带 custom。后端 scope 对 custom 拒绝符合当前批准范围，不能把这次 `WORKFLOW_PREFLIGHT_FAILED` 归为 JS 执行器缺失或正式 UI 回归。本文未捕获该次 HTTP 响应完整 details，不虚构其实际响应内容。

审计脚本现已改为存储格式 `type:'js_script'`，保留 `data.code` 与 `data.resultVariable`。这两个字段与 `JsScriptExecutor` 及正式 `JsScriptConfig` 的契约相符；业务源码没有改动。校准脚本通过 `node --check`；修正后真实 UI 运行结果应以本次审计 UI 场景证据为准，静态校准不等于重跑通过。
