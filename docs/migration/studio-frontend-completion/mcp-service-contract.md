# MCP 配置服务消费合同

2026-09-14；本批契约与消费通过，F1/F5。源：冻结 ai_assistant.py 与 mcp_manager.py。只发布 DTO 和前端消费，不安装真实 MCP 业务路由。

| 方法 | 路径 | 数据 |
|---|---|---|
| GET | /api/ai-assistant/mcp/config | mcpServers 名称映射；保留扩展配置 |
| PUT | 同上 | 请求 {config:{mcpServers:…}}，响应 {success:true,saved:true} |
| GET | /api/ai-assistant/mcp/status | servers 列表及 total_tools_injected |
| POST | /api/ai-assistant/mcp/reload | connected/failed/disabled 列表与 total_servers |

配置字段采用旧协议：transport、command、args、env、cwd、url、headers、disabled、autoApprove。可选值缺省或 null 按未配置解释；不因读取自动持久化。transport 兼容不区分大小写的 stdio/sse/http/streamable_http/streamable-http，缺省按 command、URL 推断。状态字段 tool_count、last_error、connected_at、auto_approve、total_tools_injected 保持原蛇形命名，不被 AutoFlow 默认别名转换偷偷改写。

保存和重连的 HTTP200 错误包继续拒绝。重连总命令成功不等于所有服务器连接成功：各失败项保留具体错误，由状态读取显示；Mock 明确记录未执行远程连接，不能返回虚构的连接成功或注入工具。

本合同保留配置扩展字段，避免简单编辑丢失来源配置；本轮前端表单只编辑已支持字段。跨客户端 revision、服务切换中的在途命令、真实凭据存储和实际 MCP 工具执行尚未在本切片交付，不以 DTO 测试冒充这些能力。

## 实际交付与验证

DTO 进入既有 schema-only OpenAPI 注册及 generated.ts；无真实 MCP 业务路由。配置、状态、保存、重连接口均经 mcpApi 和共享运行时校验，Mock 使用相同配置规则，非约定方法返回 405、非法写入返回 422 且不落盘。源文件可省略所有服务选项；生成器把带默认值字段具体化，前端以生成类型 Partial 适配源文件的缺省语义，不手写字段类型。

重连 Mock 返回 connected=[]，对启用项明确失败，对禁用项登记未尝试；随后状态读取保持零连接、零工具。实际 IAB 启用 mcp-ui-check 并点击重新连接后，显示“部分 MCP 服务器连接失败：mcp-ui-check：Mock 未执行外部 MCP 连接”，服务器行与总数一致。验收后恢复禁用并关闭配置面板。

后端 29 项验证命名、别名、可空字段、严格保存确认、状态蛇形字段和部分失败；前端服务合同 17 项，新增表单 2 项。API 目录清单确认四个受控请求均可定位到实际消费者。完整记录及专项/全量边界见 mcp-text-validation.md。

初次类型检查暴露生成器默认字段变为必填，与源文件缺省配置不一致，使用生成类型的 Partial 适配修复；未修改全局生成选项或强制补写旧文件。Ruff 发现新测试导入排序，已修正。
