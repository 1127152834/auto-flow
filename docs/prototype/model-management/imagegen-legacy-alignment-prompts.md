# 模型管理：旧版对齐原型生成记录

- 日期：2026-09-12
- 状态：proposed（图片待确认）；用户已确认沿用旧布局和旧交互。
- 方式：内置 imagegen；主页面生成一次，供应商流程生成后进行两次定向修订，模型流程生成一次。未使用 CLI。
- 实际参考：旧主页面、供应商预设/编辑、模型编辑及叠加移除截图；已确定的代理管理视觉和新模型主页面作为样式参考。
- 原始截图生成时临时以 `.png` 命名，检查后确认其为 JPEG，现已原样更正为 `reference/*.jpg`，未转码或改图。
- 原图输出由工具保存于 Codex generated_images；最终版复制到当前模块目录，保留工具原件。

| 最终资产 | 提示词目标 | 实际 PNG 尺寸 | 原件文件名 |
| --- | --- | --- | --- |
| [主页面](./model-management-overview.png) | 1440×1024 | 1487×1058 | exec-7bcdd3b9-4c70-4daa-8efa-b0242bd6412c.png |
| [供应商流程](./model-management-provider-flow.png) | 3200×2400 | 1448×1086 | exec-bb9faaeb-6bbf-43d2-8621-e5154e94674a.png |
| [模型流程](./model-management-model-flow.png) | 3200×2400 | 1448×1086 | exec-a8332a28-e137-4a22-9cd3-da80e827b9b5.png |

所有示例数量、模型和耗时用于排版，不代表真实服务当前状态。中间修订版本不作为视觉基准；旧三布局记录为 superseded。

## 完整提示词

### 1. 主页面

最终文件：`model-management-overview.png`。

```text
Create a faithful high fidelity Chinese desktop application UI mockup, one full main screen, target 1440 x 1024. This is a revision grounded in the first attached actual old AutoFlow screenshot. The user specifically requires SAME MODULE LAYOUT AND SAME INTERACTIONS as that old app. The second reference is only the already-approved warm ivory/clay AutoFlow global visual system, not a source of features. Do not invent new UX.
Preserve the model module master-detail composition exactly: a 278px LEFT SUPPLIER COLUMN inside the workbench and a wide RIGHT selected supplier panel; no top supplier tabs, no accordion groups, no all-supplier unified model table. One selected supplier controls the entire right panel. Use warm white/ivory, subtle gray borders, restrained clay brown primary actions and sage green status. Crisp shadcn-style controls, 14-16px body type, generous readable spacing, thin neutral dividers, restrained rounded corners. Target Windows/macOS desktop, no OS or browser frame.
Outside this module use existing NEW AutoFlow global TOP NAVIGATION: AutoFlow logo, 总览, 浏览器配置, 代理管理, 模型管理 active, 设置 and 本地服务正常. Do not copy the old application's global left navigation, project management or kernel navigation. The supplier left column IS REQUIRED and is not the global navigation.
Main page heading 模型管理, top right 添加供应商. Workbench left: 供应商 3, plus button, 搜索供应商 input; vertical items OpenRouter (selected, 2 个模型), DeepSeek (2 个模型), Ollama (0 个模型); brand icons, state dots, selected clay edge. Right header OpenRouter brand and name, badge 连接正常, subtitle 暂未填写供应商说明, 最后检查：2026/9/12 10:20. Header right 测试连接, 编辑, ellipsis. Below exact three facts columns 接口协议 / OpenAI 兼容接口; 服务地址 / https://openrouter.ai/api/v1; 访问凭据 / API Key 已配置. No visible actual keys.
Below facts one IN-PAGE feedback bar 供应商连接正常 with 连接正常，发现 2 个模型 · 186 ms. This is an illustrative last check, not live health; no toast.
Then 模型目录, on its right 同步并添加 (secondary refresh icon) and 添加模型 (clay primary).
Toolbar 搜索模型名称、标识或标签; 全部状态 select; 2 / 2 count.
Table exactly five columns 模型, 标签, 上下文, 状态, 操作. Two example rows:
aion-labs/aion-2.0 (display name and monospace ID), tags —, 未设置, 已启用, 测试 + ellipsis.
aion-labs/aion-3.0, tags —, 未设置, 已启用, 测试 + ellipsis.
Show first row ellipsis MENU OPEN with exact items 编辑模型, 停用模型, 删除模型 in danger tone. Preserve old interaction: editing opens a modal; no model row checkboxes and no bulk actions.
No dashboard statistics, quotas, prices, provider tabs, chat composer, default model selector, unsupported capabilities or decorative panels. Date anchor 2026-09-12. Add subtle external design-board footer 数据为原型示例 · 保留旧版布局与交互, clearly not an app control. Output one polished screenshot-style design, no annotations arrows, no additional options or inset canvases.
```

### 2. 供应商流程

最终文件：`model-management-provider-flow.png`。

```text
Generate a HIGH FIDELITY Chinese UI FLOW BOARD for AutoFlow 模型管理, ONE selected design continued from reference screenshots, NOT competing layout options. Target 3200 x 2400 pixels, high resolution, readable Chinese text, 4 roomy modal artboards in a clean 2-by-2 grid with small exterior captions and a narrow interaction note strip at bottom. Every modal uses the same warm ivory, white, thin gray lines, clay brown primary button, sage success styling; crisp shadcn-like controls, no browser/device/OS chrome. First attached actual old screenshot is provider catalog structure; second actual screenshot is provider connection/edit structure; third is approved revised main screen for appearance continuity. Reproduce the OLD FLOW and exact action labels; restyle only. Do not add arbitrary tabs/sidebar/navigation or metrics. Date anchor 2026-09-12. All data are mock examples.

Panel A exterior caption “新增 · 1 选择供应商”. Modal title 添加供应商; helper 选择常用供应商，系统会自动填写接口信息。 Top horizontal nonclickable step indicators 1 选择供应商 active / 2 连接信息 / 3 选择模型. Search 搜索供应商名称. Header 常用供应商 and 10 个可用连接. Three-column compact preset grid EXACTLY DeepSeek, OpenAI, Anthropic Claude, Google Gemini, 通义千问, 智谱 AI, 月之暗面, 硅基流动, OpenRouter, Ollama. DeepSeek selected. Below a full-width 自定义 OpenAI 兼容接口 choice; then selected DeepSeek / OpenAI 兼容接口 / https://api.deepseek.com. Fixed footer 取消 and 下一步. Keep all 10 presets without truncation.

Panel B exterior caption “新增 · 2 连接信息”. Modal title 连接 DeepSeek; same 3-step strip step 2 active. Provider identity DeepSeek · 官方接口 · OpenAI 兼容接口. Same form order and grouping as old: 供应商名称 DeepSeek and 接口协议 OpenAI 兼容接口 side by side; 服务地址 https://api.deepseek.com full width; API Key password dots, no raw secret; 说明 multiline optional; checked 启用供应商 with 停用后，该供应商的模型不会出现在模型选择器中。 Footer 上一步 on left, 取消 and 测试连接 on right. No fake next button. Small exterior note 测试成功自动进入下一步；失败保留输入.

Panel C exterior caption “新增 · 3 选择模型”. Modal title 选择模型; same step strip step 3 active. Inline sage banner 连接测试成功 / 连接正常，发现 2 个模型 · 186 ms. Search 搜索模型名称或标识 and text button 选择全部. Exactly two discovered rows: DeepSeek Chat / deepseek-chat unchecked, DeepSeek Reasoner / deepseek-reasoner checked, each context says 上下文长度未知. Footer 修改连接 left, 取消 and 保存供应商和 1 个模型 right. Small exterior note 不勾选模型时按钮为“保存供应商”；允许先保存供应商. Do not add a 跳过 button or separate confirmation step. The checkboxes exist only in this discovered-model selection step.

Panel D exterior caption “编辑 · 直接进入连接信息”. Modal title 编辑模型供应商; helper 修改名称和说明可以直接保存；连接配置发生变化时会先重新验证。 Same horizontal steps with step 2 active (not clickable); OpenRouter identity; fields 供应商名称, 接口协议, 服务地址, masked API Key, 说明, checked 启用供应商. Footer 取消 / 保存修改. Below this panel OUTSIDE the modal, two small precise behavior notes “仅修改名称、说明、启用状态 → 保存修改” and “修改接口协议、地址或 Key → 测试并保存”. Never show both primary buttons at the same time.

Bottom narrow annotation strip (not app controls) says: “返回保留当前输入；关闭后重新初始化。步骤不可点击跳转。连接测试与保存期间锁定关闭。反馈在弹窗内显示，不新增 Toast。”
No dashboards, pricing, tokens billed, quota cards, live chat, alternative concepts, unsaved-changes confirmation, unverified model abilities. Preserve actual old interactions and same layouts.
```

### 3. 供应商流程修订

最终文件：`model-management-provider-flow.png`。

```text
Edit the attached AutoFlow provider flow board. Preserve the entire styling, warm ivory/clay colors, four-panel arrangement, content and typography except for exactly these corrections needed to match the OLD SOURCE UI:
1. In bottom-left panel C, replace the table with two DISCOVERED MODEL LIST ROWS, no column headers and no 操作 column. Each row has checkbox on left, small DeepSeek icon, then display name with monospace model ID directly BELOW it, and 上下文长度未知 on the far right. First row DeepSeek Chat / deepseek-chat unchecked; second row DeepSeek Reasoner / deepseek-reasoner checked. Preserve search and 选择全部 above, success feedback, and 修改连接 / 取消 / 保存供应商和 1 个模型 below.
2. In bottom-right panel D, all editable fields must remain visible including the MISSING checked checkbox row 启用供应商 with helper 停用后，该供应商的模型不会出现在模型选择器中。 Put that row AFTER the 说明 field and BEFORE the footer. Expand this panel vertically and adjust lower gutter as needed, or reduce excess vertical padding. Do NOT remove any input, do NOT crop the enable checkbox or footer, do NOT make text tiny. Keep name, protocol, URL, masked key, description, enable checkbox and 取消/保存修改 in this exact order.
No other changes, no new controls or options. Keep one 3200x2400 high-resolution flow board.
```

### 4. 模型流程

最终文件：`model-management-model-flow.png`。

```text
Create one high fidelity AutoFlow MODEL MANAGEMENT interaction storyboard. This is a continuation of the exact legacy flow, not design alternatives. Target 3200 x 2400 pixels. Four generously sized artboard cells in a 2x2 grid; same warm ivory/clay/sage style, white modals, thin neutral borders and rounded corners, readable Chinese. Use reference 1 (actual model editor) as exact structural authority for split model Modal, reference 2 (actual nested removal confirmation) as overlay authority, reference 3 (new main page) only for visual style. All labels below are requirements. No OS chrome or global sidebar. No extra features. Date 2026-09-12, sample data only.

TOP LEFT “添加模型”：Large split Modal titled 添加模型 with close X, fixed full-width footer 取消 / 保存模型. Left narrow 28% summary: OpenRouter identity, 模型标识 deepseek/deepseek-chat, 状态 已启用, 本次测试 尚未测试, outline 测试模型 button; helper 发送一条简短对话，检查模型是否正常响应。 Right wide form 模型设置: 显示名称 input DeepSeek Chat; 模型标识 searchable combobox with chosen deepseek/deepseek-chat and its dropdown OPEN showing 2 discovered options, label 也可手动输入模型标识，按 Enter 确认。 small discovery status 已发现 2 个模型 and refresh icon; 上下文窗口（最大） input 可选，留空不设置 plus tokens; 自定义标签（可选） input; collapsed disclosure 运行默认值（可选） / 使用供应商默认参数. Do not add description outside that disclosure or a toggle enabled in this form. No remove button in ADD mode.

TOP RIGHT “编辑模型”：Large split Modal titled 编辑模型, same exact left supplier summary/test layout. Right form: 显示名称 input DeepSeek Chat, 远程模型标识符 readonly deepseek/deepseek-chat with copy icon, 上下文窗口（最大） optional blank tokens, 自定义标签（可选） with user tag 日常任务 and an input. Show disclosure 运行默认值（可选） EXPANDED with exact helper 本页不覆盖采样参数。使用模型时由调用方传入；未传入的参数沿用供应商默认设置。 and 使用说明 textarea. Small red ghost action 从目录移除 below form; fixed footer 取消 / 保存修改. Fit every field, no cropped content. Do not introduce sampling sliders, chat controls, enabled switch, or an extra right sidebar.

BOTTOM LEFT “本次测试与失败反馈”：A focused excerpt of the SAME split editor, left summary shows 本次测试 / 测试通过 · 10:20:18 and 测试模型 outline button. Right lower-form shows in-place sage result: deepseek/deepseek-chat 调用成功 / 186 ms · OK. Below it collapsed disclosure 查看本次返回的思考内容. Small exterior caption explains 仅在接口实际返回思考内容时显示. Beneath the success excerpt, show separate clearly labeled error STATE EXCERPT (not simultaneously inside same editor): red inline card 模型调用失败 / 供应商拒绝认证，请检查 API Key. Another small sample validation inline error 上下文长度请填写大于 0 的整数，或留空。 These are excerpts of the same flow, no new UI tabs, no toast or separate test page. Small exterior note 测试仅属于当前模型和当前弹窗会话.

BOTTOM RIGHT “移除与删除确认”：Two vertically stacked mini-scenes, clearly separate states.
Upper mini-scene shows the model EDIT MODAL softly dimmed behind a smaller centered confirmation overlay. Exact foreground title 删除模型, description 确认从目录移除“DeepSeek Chat”？, body 只移除 AutoFlow 中的模型配置，不会删除供应商的远端模型。, footer 取消 / 确认移除. Exterior note 取消只关闭确认框，返回原编辑内容；移除成功才关闭两个弹窗.
Lower mini-scene is a small standalone 删除供应商 confirmation: 将删除“OpenRouter”及其模型。此操作需要明确确认。 Body 工作流中引用的模型将不再可选；当前接口未返回确切引用数，请先核对相关配置。历史记录不会被改写。 Footer 取消 / 确认删除. No invented reference counts.
Keep all modal primary actions and labels legible. Tiny exterior footer: “标签支持 Enter / 失焦提交；关闭直接丢弃未保存内容；结果在页面或弹窗内显示，不新增 Toast。”
Do not add unsaved confirmation, bulk model selection, health dashboards, prices, quotas or false capabilities. Faithfully mirror old flow.
```

### 5. 供应商流程最终修订

最终文件：`model-management-provider-flow.png`。

```text
Make a precise composite edit of this AutoFlow provider flow board. There are two references of the SAME board. FINAL BOARD MUST use the TOP HALF (panels A and B) from reference image 1, because its panel B correctly contains the checked 启用供应商 section. FINAL BOARD MUST use the BOTTOM HALF (panels C and D) from reference image 2, because its panel C correctly uses checkbox + brand icon + stacked name and ID rows, and panel D correctly includes the checked 启用供应商.
Do not redesign, respace, simplify or omit any controls. Reference 1 TOP A/B remains identical. Reference 2 BOTTOM C/D remains identical except fix the erroneous step 2 text in panel D: it must read 连接信息, not 选择模型.
Verification before output: BOTH connection form B and edit form D must show a checked 启用供应商 row. All four footer pairs must remain fully visible. All three steps everywhere are 选择供应商 / 连接信息 / 选择模型. All 10 provider presets remain. Panel C has NO TABLE HEADER and NO ACTION column. No other changes. One final high resolution 3200x2400 image, same layout and original text.
```
