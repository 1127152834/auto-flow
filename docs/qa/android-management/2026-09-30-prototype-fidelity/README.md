# Android 原型恢复验收（2026-09-30）

状态：confirmed（本次前端恢复、软件检查及真实桌面入口）；在线设备控制 blocked。整个 AM1–AM4 仍为 partial。

## 范围与基线

- 用户在确认原型后明确要求“我需要做成这种”。隔离分支 `codex/android-prototype-fidelity`，基线 `77d0bb28`。
- 原型基线：`reference/redroid-demo/prototypes/2026-09-13/00-resource-board.png`、`01-manual-control.png`、`02-create-instances.png`。完整原始版本还保存在 android-handoff 的 references 目录，已核对相同图片。
- 恢复暖灰页面、标题与操作区、三列看板、手机预览/状态卡片、列表切换、原创建与控制台结构。
- 现有状态/模板/数据筛选、批量与历史保留；诊断、镜像、模板、备份、清理移入显式工具导航。历史原型中的工作流分配、临时创建、接管不恢复。
- 后端、数据库、OpenAPI 契约、原生控制租约没有生产改动。

## RED → GREEN 与审查

- Task1 原型分组/列表/次要操作：RED 2 failed/21 passed，GREEN 23 passed（task1-red/final.log）。
- Task2 工具导航/诊断：RED 3 failed/46 passed；其后选择保留明确 RED；修复后页面与诊断 50 passed。
- 独立审查发现同一 instance 更换 client 会清空 visitedTools，导致未知请求回执丢失。RED 1 failed → GREEN 3 passed（43 unrelated skipped），仅在 instanceId 改变时重置工具，原控制会话重置保留；检查 POST 始终 1 次，核实沿用原 requestId。
- 旧临时实例曾被新增卡片硬编码为持久实例；补 camelCase/snake_case 两例，RED 2 failed → GREEN 2 passed（23 unrelated skipped），现按真实配置显示“历史临时实例”。没有恢复临时创建。
- 独立全 diff 复审：没有未解决 Critical/Important。批量 checkbox 在浏览器实测从16×42修复到16×16。

## 视觉证据

所有本目录 `*-fixture.jpg`、board/list/create/environment/empty 截图均来自真实 React 组件 + 明示开发夹具，不是 Android 实例运行验收。入口不在 production build inputs，也没有生产导入。

| 证据 | 检查内容 |
|---|---|
| board.jpg | 1487×1024（原截图去除34px OS标题栏）的三列看板 |
| list.jpg | 实例列表切换 |
| create.jpg | 原型创建布局，磁盘未知确认16px复选框 |
| environment.jpg | 诊断只在工具入口显示，时间/能力中文化 |
| empty.jpg | 0台设备的真实组件空状态 |
| board-1280.jpg | 1280×800，页面无横向溢出（scrollWidth1268） |
| board-744.jpg | 744×800重排，无横向溢出（scrollWidth732）；不是200%浏览器缩放证明 |
| console-fixture.jpg | 既有DeviceConsole组件，沿用原型手动控制示例，未声称真实控制会话 |

交互实测：列表/看板切换、设备更多菜单、操作历史打开/关闭、关闭历史焦点回原更多按钮、批量选择→环境配置→返回后仍checked。

## 真实桌面构建检查

使用最终 `out` 构建、生产 sidecar 和隔离的 `/tmp/autoflow-android-prototype-fidelity-20260930` 用户目录启动 Electron。原用户数据未改。通过实际桌面操作打开安卓看板→环境配置→返回→创建页：本地服务正常，真实设备列表0台；环境页确认Lima已停止、Docker不可访问；创建页显示未连接且“创建并启动”禁用。`electron-board.png`、`electron-environment.png`、`electron-create.png` 是真实 Electron 截图，无夹具。独立 `adb devices -l` / `limactl list --json` 观测一致，见 runtime-observation.json。

## 工程命令与结果

Node v26.7.0 / npm11.19.0；日志归档只规范化行尾空格与尾部空行，保留实际结果。

| 命令 | 实际输出摘要 | 日志 |
|---|---|---|
| `npm --workspace @autoflow/desktop test -- --maxWorkers=2` | 455文件 / 5977项全部通过，532.48s，exit0 | frontend-complete.log |
| `npm run typecheck` | exit0，无诊断 | typecheck-final.log |
| `npm run lint` | exit0，无诊断 | lint-final.log |
| `npm run openapi:check` | 重跑exit0，生成类型一致 | openapi-retry.log |
| `npm run build` | exit0，renderer built in42.59s；既有依赖PURE注释警告 | build-final.log |
| `git diff --check` | exit0 | 完成时现场执行 |

本次没有运行后端全量测试：生产改动全部限于前端；没有宣称此次重新通过整个安卓模块后端验收。本轮第一次全量命令参数被npm吞掉（日志有Unknown cli config），在并行负载下出现非Android用例失败，已中止并使用正确命令限制2 workers重跑；没有调整测试超时或绕过断言。OpenAPI首次冷启动超时，独立schema_export成功后原openapi:check重跑exit0。

## 阻塞与剩余风险

- 整个安卓模块既有十实例/GApps等完整验收阻塞不由此次UI变更解除。
- 真实在线设备管理/控制验收 blocked：Lima停止、ADB无设备；未启动重负载运行时。
- 200%桌面实际缩放未验；744px仅为窄视口重排。
- 真正设备的截图和占用状态以服务返回为准；不可用画面显示占位，不用原型壁纸冒充设备。
- 当前版本保持原型视觉结构，额外保留既有管理筛选和批量操作；不声称像素逐点一致。

完整回归第一次正确限制并发的结果为454文件/5958断言通过，另1文件因缺少忽略的reference/WebRPA/RecorderPanel.tsx而加载失败。复用主仓库既有参考目录后重跑整个测试集；参考文件SHA256为fb659eec5a180ed431d57022b5198ba622db9ec21f755d2e445508a5cf99990d，未修改参考内容或测试。

最终完整回归已通过：455文件、5977项；包含补齐参考文件后的17项以及最后新增的历史临时实例2项。独立最终复审无未解决Critical/Important（高置信）。构建产物JS/HTML扫描未包含视觉夹具水印，三个QA sidecar环境开关均未设置。

历史状态（superseded）：原型独立验收时提交位于隔离分支，主仓库推进到53b87b59。用户随后授权合并与分支收敛；当前集成结果见[baseline收敛验收](../2026-09-30-baseline-consolidation/README.md)，独立分支结果不代称集成验证。
