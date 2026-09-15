# F1 服务消费合同核销

日期：2026-09-15。

## 核销结论

`inventory-studio-services.mjs` 从当前 Studio 源码登记每个服务操作、直接请求和事件入口，生成 `service-inventory.json` 与 `contract-matrix.md`。本次扫描登记 171 个服务方法、83 个事件、50 个直接请求和 105 个 AI 画布操作；23 个服务族全部进入现有矩阵，没有未分类的新服务族。

矩阵中的“已登记”表示前端请求入口、方法表达式、请求体表达式、声明响应类型、静态消费者和源码位置已经冻结。它不表示真实后端、文件系统、浏览器进程或外部服务已执行。共享行为通过下表集中验证，避免给每个入口机械复制相同传输测试。

## 服务族与验证证据

| 服务族 | 前端消费范围 | 请求、响应与恢复证据 |
|---|---|---|
| `workflowApi`、`variableTrackingApi` | 文档、运行、Debug、日志、结果、诊断、分页导出 | `run-start-protocol`、`debug-*-contract`、`execution-log-contract`、`run-results-protocol`、`run-variable-tracking-protocol`、F3 结果与诊断证据 |
| `browserApi`、`browserScriptTestsApi`、`elementPickerApi` | CloakBrowser Profile、页面、拾取、定位及脚本测试 | `browser-*-protocol`、`picker-*-protocol`、`selector-test-protocol`、`browser-script-protocol`、F4 浏览器与拾取证据 |
| `recorderApi` | 录制会话、确认序号、步骤分页、审查与生成 | `recorder-*-contract/protocol/recovery`、F4 录制审查证据 |
| `inputPromptApi`、`jsScriptApi`、`speechApi` | 运行中的输入、脚本和语音命令回传 | `input-command-protocol`、`js-command-protocol`、`speech-command-protocol`；同 ID 重试、所有权、停止竞争和迟到响应均覆盖 |
| `credentialApi`、`mcpApi`、`retentionApi` | 凭据字段、MCP 配置、留存策略 | `credential-*-protocol/contract`、`mcp-service-contract`、`retention-protocol` 及 F5 专项证据 |
| `imageAssetApi`、`systemApi` | 图像资源、路径选择、剪贴板和宿主工具 | `image-asset-contract`、`image-write-contract`、`image-resource-commands`、`path-service-contract`；真实原生对话框归 F6 |
| `localWorkflowApi`、`workflowBundleApi`、`customModulesApi` | 本地文档、导入导出、自定义模块 | F2 文档保存、七种导出、模块列表与依赖链证据；失败回执不会伪造保存或导出成功 |
| `aiAssistantApi` | 会话、模型配置、连接测试和助手请求 | F5.3 模型设置、AI 权限、取消及连接成功/失败证据；真实模型服务单列后端交接 |
| `scheduledTaskApi` | 计划任务配置与日志消费 | 已有计划任务前端与 fixture 合同证据；真实调度服务单列后端交接 |
| `featurePackApi`、`pluginApi`、`executorApi`、`sponsorApi` | 冻结源码中的共享或零消费者候选 | 操作仍逐项登记，静态消费者为零不授权删除；未接入当前 227 节点 UI 的候选不冒充已实现后端能力 |

## 共享合同

- 鉴权和连接：`authenticated-transport`、`connection-composition` 与 `request-connection-binding` 验证请求固定绑定发起时连接；替换连接后的迟到回执不能写入新工作区。
- 错误：`transport-errors`、`command-http-error-recovery` 验证网络错误、HTTP 业务错误、取消和恢复提示互不混淆。
- SSE：`event-client`、`event-gap-recovery`、`event-truncated-recovery`、`event-listener-isolation` 验证序号补读、断帧不确认、监听器隔离和无重复恢复。
- 事件所有权：`execution-event-ownership`、`log-event-timestamps` 验证工作流及运行身份、源时间戳、批次去重和旧连接隔离。
- 幂等命令：`command-response-identity`、`command-recovery`、各输入/脚本/语音/Debug 协议验证稳定命令 ID、原 ID 查询、冲突拒绝及停止竞争。
- 分页与大值：运行结果、日志、录制步骤和变量诊断专项验证游标补读、重复节点结果及超过 64 KiB 的内容读取。
- Schema：OpenAPI 生成一致性与后端 contract 套件验证已生成 DTO、错误状态和确认回执。无显式响应类型的遗留入口继续按矩阵中的实际消费字段交接，不能把 `unknown` 解释为任意成功。

## 当前验证结果

- 前端合同专项：54 个测试文件，1565/1565 通过，同时覆盖 memory 与实际本地 HTTP/SSE 传输。
- 后端 contract 套件：503/503 通过。正确命令为 `uv run --project apps/backend pytest apps/backend/tests/contract -q`。
- 服务清单脚本：8/8 通过，包含确定性生成、multipart、动态方法、直接请求、普通事件和全部 23 个服务族登记。
- OpenAPI 一致性：通过。

## 交接边界

前端消费合同已经冻结。真实自动化执行、浏览器采集与清理、真实模型/MCP/WebDAV/计划任务/秘密存储，以及静态零消费者候选是否提供后端实现，在 F6 后端交接表中逐项列明。Mock 或 contract fixture 的通过不替代这些真实服务。
