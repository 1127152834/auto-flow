# F2.2 AI 模型选择器与四节点入口核销

日期：2026-09-15。状态：confirmed（仅本页列明的 8 项组件用例）；不将节点整体或 F2.2 标为完成。

## 范围与来源

使用现有 `AIModelPicker` 的源版本行为：从 Studio 全局 AI 配置的 `models` 选择模型，将地址、密钥、模型名及存在的可选数值写入当前节点；`autoFallback` 生成其它有效模型的有序配置。源码入口为 `components/config-panels/AIModuleConfigs.tsx` 的 `AIModelPicker`，由 `AIChatConfig`、`AIVisionConfig`、`AIVisionActConfig`、`AITaskConfig` → `AITaskApiBlock`（ai_route）消费；真实派发入口为 `components/ConfigPanel.tsx`。

本切片只增加测试，未改 Store、API、Toolbar 或业务组件。没有调用真实模型服务，没有宣称全局模型管理、凭据安全存储、模型执行或运行时自动回退已经验收。当前范围仅四个保留节点，不恢复数据库/DP 等已排除能力。

## 已核销用例

所有用例位于 `apps/desktop/src/renderer/domains/workflows/tests/ai-model-picker-entry.test.tsx`。测试挂载真实 `ConfigPanel`、真实模型选择下拉与工作流 Store；仅补齐测试环境缺失的 `scrollIntoView`，不替换模型选择组件。

| 用例 ID | 归属能力 | 验证行为 | 层级 / 状态 |
|---|---|---|---|
| `NODE.ai_chat.model-picker.entry` | `node:ai_chat` | 选择写回地址/密钥/模型/温度零/Token 数；不改另一节点；真实文档导出并重新导入后保留字段及选择回显 | 真实入口组件＋编辑器文档往返 / 已实现且已验收 |
| `NODE.ai_vision.model-picker.entry` | `node:ai_vision` | 同上，在 AI 视觉节点真实配置入口执行 | 真实入口组件＋编辑器文档往返 / 已实现且已验收 |
| `NODE.ai_vision_act.model-picker.entry` | `node:ai_vision_act` | 同上，在 AI 视觉操作节点真实配置入口执行 | 真实入口组件＋编辑器文档往返 / 已实现且已验收 |
| `NODE.ai_route.model-picker.entry` | `node:ai_route` | 同上，在 AI 路由节点真实配置入口执行 | 真实入口组件＋编辑器文档往返 / 已实现且已验收 |
| `TOOL.ai-model-picker.empty` | 上述四节点共用 `AIModelPicker` | 模型列表为空时隐藏快捷选择，保留节点手工地址/密钥/模型与数值 | 共享组件规则，经 `ai_chat` 入口集中验证 / 已实现且已验收 |
| `TOOL.ai-model-picker.fallback` | 上述四节点共用 `AIModelPicker` | 回退配置保留有效候选顺序，排除当前 URL＋model 身份（包括不同 ID 的同身份条目）及缺模型名条目；关闭自动回退后清空，不改当前模型 | 共享组件规则，经 `ai_chat` 入口集中验证 / 已实现且已验收 |
| `TOOL.ai-model-picker.removed-profile` | 上述四节点共用 `AIModelPicker` | 全局列表移除已选模型后显示手动填写，保留节点已经选择的字段 | 共享组件规则，经 `ai_chat` 入口集中验证 / 已实现且已验收 |
| `TOOL.ai-model-picker.optional` | 上述四节点共用 `AIModelPicker` | 档案缺少 temperature/maxTokens 时，不覆盖节点既有数值 | 共享组件规则，经 `ai_chat` 入口集中验证 / 已实现且已验收 |

## 证据与边界

专项命令：`npm --workspace @autoflow/desktop test -- src/renderer/domains/workflows/tests/ai-model-picker-entry.test.tsx`。

结果：1 文件、8 项通过，原始输出见 [target.log](evidence/f2-ai-model-picker/target.log)。独立文件 ESLint 与全局 TypeScript 检查通过。类型检查首轮指出测试参数为宽 string，将参数限定为正式 ModuleType 并将四节点表设为字面量后通过；不修改产品代码或放宽断言。未重复运行全量测试回归。

这些证据只核销原 `NODE.<type>.field-map-and-unique-branches` 中的模型选择接入及上述共享分支。各节点其余字段、模型请求/权限/真实运行、AI 代码助手、原生窗口交互仍不由本页证明；工作流导出/导入是编辑器规则往返，不是文件系统保存或正式宿主 E2E。既有代码补全、剪贴板和全局模型管理用例没有重复计入。
