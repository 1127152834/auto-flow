# F2.2 AI 代码助手真实入口与响应消费

日期：2026-09-15。状态：confirmed（仅本页所列组件及响应消费切片）；不将三个脚本节点整体或 F2.2 标为完成。

## 来源与修改

冻结 `WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb` 的 `frontend/src/components/workflow/AICodeAssistant.tsx` 已提供 OpenAI JSON、Ollama JSON/NDJSON 分支，以及“生成后填入编辑器、用户继续修改、显式保存”的交互。当前迁入组件通过 `studioFetch` 请求配置的模型端点，三个真实配置入口分别为：

- `InjectJavaScriptConfig` → `InjectJsEditorDialog` → `AICodeAssistant`，保存写入 `javascriptCode`。
- `JsScriptConfig` → `JsEditorDialog` → `AICodeAssistant`，保存写入 `code`。
- `PythonScriptConfig` → `PythonEditorDialog` → `AICodeAssistant`，保存写入 `scriptContent`。

本次测试复现并修复两个沿用原版的问题：合法温度 0 被 `|| 0.7` 改写；NDJSON 响应先执行 `response.json()`，随后又尝试 `response.text()`，导致多行 JSON 解析失败或响应体重复读取。仅修改 `AICodeAssistant.tsx`：数值使用空值默认，响应体读取一次，依 Content-Type 区分 NDJSON 与 JSON。NDJSON 保留逐行拼接与 done 终止行为；不增加服务端协议、模型执行器或取消协议。

生成期间禁用取消是冻结原版行为，本批没有擅自增强。此处“取消验收”明确指生成前关闭需求弹窗，以及生成后放弃编辑器草稿。

## 用例与能力映射

测试文件：`apps/desktop/src/renderer/domains/workflows/tests/ai-code-assistant-entry.test.tsx`。

| 用例 ID | 能力与层级 | 断言 |
|---|---|---|
| `NODE.inject_javascript.ai-code.entry` | `node:inject_javascript`；真实 ConfigPanel / Dialog / Assistant / Store 入口 | 请求包含 JavaScript 提示、配置的模型参数及鉴权头；生成先进入审查草稿，节点不变；修改后显式保存才写入 javascriptCode |
| `NODE.js_script.ai-code.entry` | `node:js_script`；同上 | 生成草稿与节点 code 分离，编辑后保存才写回 |
| `NODE.python_script.ai-code.entry` | `node:python_script`；同上 | 请求包含 Python 提示；生成草稿与节点 scriptContent 分离，编辑后保存才写回 |
| `TOOL.ai-code.cancel` | 三节点共用助手规则，经 js_script 集中验证 | 生成前取消没有请求；生成后放弃编辑器草稿不改节点 |
| `TOOL.ai-code.rejection` | 共用响应消费，经 js_script 集中验证 | HTTP 503 展示错误并保留原草稿；用户显式重试后消费 Ollama JSON，不提前写节点 |
| `TOOL.ai-code.missing-model` | 共用请求准入，经 js_script 集中验证 | 模型配置缺失在发送前明确拒绝 |
| `TOOL.ai-code.zero-temperature` | 共用请求参数，经 js_script 集中验证 | 显式配置 temperature=0 时实际请求仍为 0 |
| `TOOL.ai-code.ndjson` | 共用响应消费，经 js_script 集中验证 | 标准 Response 的 NDJSON 分片拼成完整代码，done 后内容不采用；节点仍保留原值等待审查保存 |

## 证据与范围

专项命令：`npm --workspace @autoflow/desktop test -- src/renderer/domains/workflows/tests/ai-code-assistant-entry.test.tsx`。

- 修复前 6 项通过、2 项失败：[before.log](evidence/f2-ai-code-assistant/before.log)。失败为温度 0 被改写及 NDJSON 不能生成，不是测试前置失败。
- 修复后 1 文件、8 项通过：[target.log](evidence/f2-ai-code-assistant/target.log)。没有跳过或放宽失败断言。
- 组件与新测试文件 ESLint 通过；TypeScript 通过，输出见 [typecheck.log](evidence/f2-ai-code-assistant/typecheck.log)。类型检查首轮指出测试 getByRole 不支持 exact 参数，改为等价锚定名称后通过，未改产品断言。未重复运行全部测试。

测试仅替换 Monaco 渲染为受控 textarea，实际配置派发、编辑器弹窗、助手组件、Studio 请求边界和工作流 Store 均保留。模型响应使用明确夹具，没有请求外部模型、验证真实生成质量、执行代码或宣称正式 Electron UI 通过。JS 执行、剪贴板和补全已有专项，本批不重复计入。三个节点的其它独有字段与服务运行仍不能由本页整体核销；能力总台账由主任务协调回填。
