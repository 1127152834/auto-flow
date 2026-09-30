# Android 前端核验与预览验收（2026-09-23）

- 状态：partial，完整目标 active。
- 基线：隔离分支 `codex/android-management-complete@1399f07b`；本文件随前端增量提交。
- 本轮范围：AM3/T14 预览生命周期、T15 应用操作和 APK 核验；校准 `.ai/plans` 的旧基线。无后端 DTO、OpenAPI 类型或数据库形状变化。
- 既有 3 个 Studio 文档的未提交改动不覆盖、不纳入本轮提交。

## RED → GREEN

| 复现 | 修复与覆盖 |
| --- | --- |
| 应用与 APK 核验首次 `3 failed / 13 passed` | 只有服务端 422 且错误码为确定失败时释放本地写入锁；unknown 保持禁用；APK 按原请求 generation 核实 |
| generation 变化后的迟到核验 `2 failed / 16 passed` | 响应必须仍对应当前设备、会话、generation、控制端点及访问类型 |
| 关闭或卸载组件后的迟到核验 `4 failed / 18 passed` | 已关闭或卸载的控制台不接受旧结果，不恢复旧会话 |
| 初始应用动作/APK 响应 `2 failed / 22 passed` | 同一响应保护用于初始应用操作、安装、启动和核验，不只修复核验按钮 |
| 预览首次 `3 failed / 5 passed` | 首次可见性未知时不请求；不可见时卸载查询观察者并取消请求；迟到旧截图不覆盖重新显示的画面 |
| 预览保留边界回归 | 全局最多 2 路；排队取消立即清除；共享请求保留到最后一个可见使用者退出；后端实例切换丢弃旧响应；释放已显示的 ObjectURL |

业务代码使用现有 TanStack Query 的观察者取消语义和现有 ApiClientError；没有新增依赖。仅在 IO 边界使用替身，未据此声称真实 macOS 画面或人工操作通过。

## 运行时校准

发现默认 shell 的 Node 为 **26.7.0**，与规格 GC-02 要求的 22.x 不符。前面的运行保留为定位证据，不作为指定运行时的最终门槛。

通过 `npm exec --yes --package=node@22 -- node --version` 准备隔离运行时，实际为 **22.23.2**。只使用 npm 缓存，不修改项目 package.json 或锁文件，不替换系统 Node。后续命令使用固定版本前缀：

```sh
npm exec --offline --yes --package=node@22.23.2 -c '<实际命令>'
```

## 实际命令与结果

桌面命令 cwd 为 `apps/desktop`；结构、OpenAPI 和 build 命令 cwd 为仓库根。

| 命令 | 结果 |
| --- | --- |
| Node 22 `npm test` | **failed**：424 files：415 passed / 9 failed；4702 tests：4677 passed / 25 failed；615.19s |
| Node 22 `npm run typecheck && npm run lint` | passed，exit 0 |
| Node 22 `vitest run src/renderer/domains/android/tests` | passed，14 files / 100 tests |
| Node 22 `npm run build` | passed，exit 0；renderer built in 1m 49s；保留既有 zod 注释及工作流导入警告 |
| Node 22 `npm run openapi:generate && npm run openapi:check && npm run test:structure` | passed，生成无差异；结构 4 passed |
| Node 22 `npm run test:scripts` | **failed**：95 tests / 92 passed / 3 failed，7.56s |

Node 22 全量的 6 个持续失败文件与下方 Node 26 基线相同，另有 recorder-review、StatusEditorDialog、RecordEditorDialog 的 5 个交互失败。同机观测到另一工作区测试进程并行运行，但未证明它是唯一原因。未改断言或超时，单独复跑这 3 个文件和 Android 目录，**17 files / 149 passed，31.18s**；这不能替代全量通过。

复跑命令：`vitest run src/renderer/domains/android/tests src/renderer/domains/workflows/tests/recorder-review.test.tsx src/renderer/domains/project-data/components/StatusEditorDialog.test.tsx src/renderer/domains/project-data/components/RecordEditorDialog.test.tsx`，同样使用上面的 Node22 前缀。嵌套 `npm exec` 曾因继承外层 call 配置返回 EUSAGE，未执行测试；改为调用 PATH 中的 vitest 后才形成上述证据。

脚本 3 个失败：frozen required-field data regenerates exactly、every service family is assigned to the frozen frontend contract matrix、MCP requests nested in validation helpers。尚未获得将这些失败排除出最终门槛的用户确认。

本机原始输出：`/tmp/android-frontend-node22-full-20260923.log`、`/tmp/android-frontend-node22-checks-20260923.log`、`/tmp/android-node22-android-only-20260923.log`、`/tmp/android-frontend-node22-focused-20260923.log`、`/tmp/android-node22-build-20260923.log`、`/tmp/android-node22-contracts-20260923.log`、`/tmp/android-node22-scripts-20260923.log`。这些临时日志不是跨机器持久证据，本页保留实际摘要与复跑命令。

历史定位运行（Node 26）：

- Android 聚焦曾为 `14 files / 98 tests passed`，另追加预览 11 条回归通过；由下方指定 Node 22 结果替代最终门槛。
- 第一次全量：`9 files failed / 415 passed`，`23 tests failed / 4675 passed`，442.58 秒。
- 其中新增的 settings sidecar 集成单独复跑 `1 passed`；DataTableDetailPage、log-history-panel 单独复跑 `59 passed`。未删除断言或增加超时。
- 不并行构建后重新全量：`6 files failed / 418 passed`，`20 tests failed / 4682 passed`，260.59 秒。
- 6 个持续失败文件：catalog-field-contract（能力与冻结字段清单不一致）、recording-source-parity（reference 文件缺失）、documentation-loading（排除模块仍在文档）、recorder-review-protocol（commandId 预期不一致）、shared-control-entry-wiring（16 个配置入口与冻结清单不一致）、addNodeDefaults（字段分布基线不一致）。没有删除这些测试、恢复退役执行链或覆盖 Studio 改动来制造通过。
- 类型、lint、结构（4 passed）、OpenAPI check 通过；较早增量的 build exit 0，renderer `built in 3m 9s`。最终代码 build 以指定 Node 22 重跑为准。

## 剩余工作

- 前端核验失败后的永久锁定和预览取消缺口已修复；真实应用/画面、1/5/10 台性能尚未形成新证据。
- AM3 持久容量预留、应用命令完成语义、重启/中断恢复仍需继续；AM4 安全链接/属性、恢复异常、高级日志及临时文件仍未闭环。
- 完整后端与 Ruff 的已知失败见 [后端增量记录](2026-09-23-validation.md)。完整前端、全脚本以及最终全分支审查未完成，不能报告完整交付。
