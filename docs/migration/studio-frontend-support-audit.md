# Studio 非节点功能与基础设施审计

日期：2026-09-13。代码基线：690f13f。范围：已确定 Web 节点之外的工作台能力；只读审计，不实施业务改动。

## 结论

编辑器主体与多数 Store 已迁入，但完整工作台尚未接通。必须区分前端遗漏、Mock 协议缺口和正式后端适配；不把用户允许暂用 Mock 等同于实现错误，也不把有界面等同于已完成服务。

置信度：下表直接源码判断高；未逐项实点的交互完整性未知。本文不将历史测试结果冒充本轮测试。

| 配套模块 | 已有 | 尚未完成 | 分类 |
|---|---|---|---|
| 画布与编辑 | 原画布/块视图、分组、便签、子流程、历史、剪贴板、属性表单 | 全交互逐项对照验收尚未完成；本轮未发现这些主体整体漏迁 | 验收缺口 |
| AI 面板布局 | 原面板、会话与配置、布局 Store | 原 App 的右侧宽度避让未接入 Studio；浮动入口改成 Mock 横条按钮 | 前端遗漏 |
| 提示与快捷键 | 本地键盘快捷键、源事件转发 | 全局 Tooltip 未迁入；custom_action 转发后无 DOM 消费方；全局热键注册未接通 | 前端/宿主遗漏 |
| 连接反馈 | studioFetch、SSE 断线续读 | studio:connection-error 无消费者；缺统一可恢复连接提示 | 前端遗漏 |
| 交互请求 | 输入提示与 JS 等消费者、结果回传方法 | Mock 不产生/等待对应请求，除停止外反向事件直接确认成功；没有完整交互场景 | Mock 协议缺口 |
| Debug 和变量 | 断点、单步、暂停面板、变量追踪 UI/Store | Mock 仅节点数组推进与初值记录；缺循环多次执行、变量变化等场景；真实调试服务未接入 | Mock + 正式服务 |
| 日志与结果 | 基础日志、数据行、序号续读 | 事件/运行数据在内存；刷新后历史不恢复；批量、长日志、结果与诊断真实持久化未接通 | Mock + 正式服务 |
| 浏览器、拾取、录制 | 面板、轮询、录制步骤生成、模拟页面 | 正式 Profile/浏览器会话未接；定位只有固定结果，缺零/多/错误/iframe 场景；录制无真实采集恢复 | Mock + 正式服务 |
| 文档与目录 | 虚拟文件夹、本地保存/打开、JSON/加密/bundle 导入导出 | 正式工作区存储、目录选择与权限、跨工作区身份未接通；不能将 localStorage 视为正式持久化 | 正式服务 |
| 关闭与退出 | 单窗口复用；未保存时放弃/继续；退出先关 Studio | 原生提示无“保存后关闭”；缺草稿+运行/拾取/录制清理统一协调及换区握手 | 宿主配套 |
| 服务控制 | AutoFlow 主服务与窗口边界仍保留 | Studio 固定 Mock origin；正式连接上下文、鉴权、服务恢复/重启限制及生成 API 类型适配未完成 | 正式基础设施 |
| 自定义模块与资源 | 自定义模块 CRUD、源前端工具动作、图片字节与目录、bundle | 原生文件资源桥接、正式资产服务未接入；已排除 Excel 的资源入口需另行清理 | 正式服务/入口清理 |
| AI 与 MCP | 对话/权限/工具相关源代码、会话本地保存、流式模拟回复 | 模型调用、MCP 服务/工具发现未接；Mock status/reload 为空。不能说所有 AI 工具都不存在，已有本地画布操作实现 | 正式服务 |
| 凭据与配置 | 配置 Store、凭据名称/掩码、保留策略表单 | 非真实凭据存储；保留策略用量固定为零；旧安全令牌开关仍可见但路由不支持；需映射 AutoFlow 权限 | 正式服务/前端边界 |
| 导出工具 | JSON/加密/整包等前端导出 | Playwright/脚本导出仅 Mock 文本，不能运行；不与已实现的 JSON 导出混称 | 正式服务 |
| 性能与交付 | renderer/main/preload 可构建、开发及构建窗口曾验收 | 大图/长日志/大量资源性能、正式分发包及平台实测未完成；Studio 主构建块约 8.5 MB 未压缩，需测量再拆分 | 验收/工程 |

## 关键证据

- `apps/desktop/src/renderer/app/StudioApp.tsx` 与 `reference/WebRPA/frontend/src/App.tsx:534`：AI 布局避让差异。
- `apps/desktop/src/renderer/domains/workflows/hooks/useStudioIntegration.ts`、`events.ts:819`：custom_action 事件消费者缺失。
- `apps/desktop/src/renderer/domains/workflows/api.ts:52`：连接错误仅分发事件；renderer 搜索无对应消费者。
- `apps/desktop/src/renderer/domains/workflows/api/mock-server.ts:141`：反向命令；`:195` 变量追踪；`:196` 脚本占位；模块顶部 events/runRows/tracking 为内存状态。
- `apps/desktop/src/renderer/domains/workflows/api/config.ts`、`transport.ts`：固定 Mock origin 与默认 Mock 传输。
- `apps/desktop/src/main/ipc/automation-studio.ts`：关闭对话只有放弃/继续；控制器负责窗口，未持有真实运行会话。
- `apps/desktop/src/renderer/domains/workflows/api/mock-settings.ts`：MCP 空状态、保留用量、凭据掩码。
- `apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:342` 起：本地画布工具实际已保留，不列为整体缺失。

## 已排除能力的配套入口

`GlobalConfigDialog.tsx` 仍有 QQ、飞书 tab/表单；资源库仍有 Excel 数据资源与 Mock 预览。节点范围收紧后，这些入口需要清理或按实际 Web 用途收口，而不是投入开发补服务。SAP、通用文件处理、桌面控制、媒体处理等不进入待实现清单。

保留流程文件保存、导入导出、网页截图与结果文件；它们不等于用户排除的文件处理节点。计划任务、企业、发布、版本等不因原版有入口而自动加入本轮范围。

## 推进顺序

1. **前端收口**：清理排除能力的设置/资源入口；修 AI 布局、Tooltip、连接提示、快捷键消费与关闭保存入口。逐项验证正常、取消、失败。
2. **Mock 可验收**：补输入/JS 请求响应、循环多次事件、变量变化、定位零/多/错误、断流补读和迟到响应场景；保留单一 API/SSE 边界，不另写执行引擎。
3. **正式服务接入**：先连接上下文、工作区文档、Profile 与资源占用，再运行/调试/拾取/录制、持久日志与产物；按垂直切片替换 Mock。
4. **交付验证**：大图和长日志性能、原生关闭/换区异常、正式包与平台实测。

更细的源文件清单与前端缺口证据见 `studio-frontend-module-audit/README.md`、`inventory.json`。本轮未修改业务代码，未重新运行构建或功能测试。
