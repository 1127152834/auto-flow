# 模型管理原型：图像生成记录

- 日期：2026-09-12
- 状态：superseded。用户后续明确要求沿用旧项目布局与交互；以下三种改版均不再参与选择，不作为实现基准。当前生成记录见 [旧版对齐修订](./imagegen-legacy-alignment-prompts.md)。
- 生成方式：内置 imagegen，三次独立调用；每次附带 `docs/prototype/proxy-management/proxy-management-overview.png` 原图作为视觉参考。
- 指定目标：1440×1024；实际输出：每张 1487×1058 PNG，原样保存。
- 以下编号按对话中图片显示顺序记录。示例数据仅用于布局设计。

## 布局 1：顶部供应商切换

产物：[model-management-layout-01.png](./model-management-layout-01.png)

完整生成提示词：

```text
Use case: ui-mockup. Create a realistic, production-quality Chinese desktop UI screenshot for AutoFlow 模型管理. Target dimensions 1440 x 1024. Current date anchor 2026-09-12. This is a design mock with explicitly illustrative data, not a live service. Design direction name: 顶部供应商切换. Do not show numeric option labels.
Attached image is ONLY the established AutoFlow visual-system reference: match its warm ivory canvas, muted clay-brown primary buttons, graphite text, subtle sage green statuses, fine warm gray borders, simple line icons, crisp shadcn/ui + Tailwind-like controls. DO NOT carry over proxy fields/content/side drawers. No sidebar at all, no persistent right rail, no split workspace. Full-width single main area under a slim global top navigation.
Top app nav: AutoFlow logo/name; 总览, 浏览器配置, 代理管理, 模型管理 (active underline), settings icon. No inner left navigation.
Main heading 模型管理; small subtitle 管理供应商连接与模型目录. Main primary CTA 添加供应商 at upper right.
Under heading a horizontal strip of three COMPACT selectable supplier tiles, shallow height about 100px, not giant metrics: selected DeepSeek 工作账号 / 上次测试通过 / 2 个模型 ; OpenRouter / 未测试 / 1 个模型 ; 本地 Ollama / 已停用 / 0 个模型. These are standalone supplier resources with modest logos or monograms, not charts. All content sample. Do not show balances, uptime, costs, usage graphs or credit totals.
Below a flat full-width selected-supplier header "DeepSeek 工作账号" with muted subline "OpenAI 兼容接口 · API Key 已配置". On right only 测试连接 and a ... menu. A compact muted description line may show "最近测试 09-12 10:18 · 286 ms（示例）".
Then section title 模型目录, count 2; tools search placeholder 搜索模型名称、标识或标签, status dropdown 全部状态, secondary 添加模型. Normal clean full-width table with generous 64px row heights, columns 模型名称 / 模型标识 / 标签 / 上下文 / 状态 / 操作.
Rows: DeepSeek Chat / deepseek-chat / 通用 / 未设置 / 已启用 toggle / 测试模型  ... ; DeepSeek Reasoner / deepseek-reasoner / 推理 / 未设置 / 已启用 toggle / 测试模型 ...
First row is expanded to show an INLINE model test result panel beneath the row (NOT a sidebar): green check "模型响应正常", subtext "本次调用耗时 842 ms（示例）", output preview "已收到测试消息。", unobtrusive collapse chevron. Another row shows ordinary untested state. Small footer “供应商连接测试与模型调用测试分别记录” as meaningful clarification. Plenty of comfortable whitespace, body 14-16px, Chinese typography highly legible.
Include one small success toast at lower right "模型已保存". No floating editor modal on this version: hero use case is provider switching and testing saved models.
Presentation: app content only, orthographic screenshot, no device mockup/bezel, no browser chrome, no annotations/diagram labels. Avoid cards inside cards, giant KPI cards, decorative gradients, AI sparkle art, additional default-model feature, billing/marketplace/training/chat composer. Supplied reference visual language must remain recognizable.
```

## 布局 2：分组展开

产物：[model-management-layout-02.png](./model-management-layout-02.png)

完整生成提示词：

```text
Use case: ui-mockup. Generate a realistic polished Chinese AutoFlow desktop app screenshot. Target 1440 x 1024, current date 2026-09-12, sample data only. Direction name 分组展开. No numbered option label. Use attached AutoFlow proxy screenshot strictly as the established STYLE REFERENCE (ivory, warm gray, clay brown, fine borders, graphite typography, sage green). Content must be MODEL MANAGEMENT only, no proxy content. Body text 14–16px. No left sidebar, no right sidebar, no permanent detail pane, no cards inside cards, no device frame or browser chrome.
Top thin app navigation AutoFlow | 总览 浏览器配置 代理管理 模型管理(active clay underline) | 设置.
Page header 模型管理 with small subtitle 按供应商组织模型，按需展开管理 and one clay primary button 添加供应商.
Below search “搜索供应商或模型” and status filter 全部状态. Make the page a FLAT ACCORDION RESOURCE LIST, not selectable top cards, not a unified global model table. Every supplier is a wide horizontal GROUP HEADER ROW with chevron, discreet provider icon/name, model count, last test status, right aligned 测试连接 and ... actions. Supplier header height about 64px.
First provider expanded: DeepSeek 工作账号 ; “2 个模型 · 上次连接测试通过”, API Key 已配置 in small muted subline. Under its header, a clear indented but FULL-WIDTH two-row model table on SAME surface with lightweight separators. Heading strip says 已添加模型 and local secondary 添加模型. Columns 显示名称 / 模型标识 / 自定义标签 / 上下文 / 启用 / 操作. DeepSeek Chat / deepseek-chat / 通用 / 未设置 / green switch / 测试 ... ; DeepSeek Reasoner / deepseek-reasoner / 推理 / 未设置 / green switch / 测试 ...
Second provider collapsed: OpenRouter 团队网关 / 1 个模型 / 未测试.
Third provider expanded empty state: 本地 Ollama / 0 个模型 / 未测试, inside short centered “还没有添加模型”, subtitle “从供应商发现，或手工填写模型标识”, secondary button 添加模型. This is a smaller expansion, not enormous illustration.
Show an OPEN compact dropdown MENU anchored to first supplier's ... button: 编辑连接 ; 停用供应商 ; divider ; 删除供应商 in restrained dangerous red. The menu must not dominate the page.
At bottom right a compact green toast 供应商已保存. Modest whitespace at bottom. No fabricated account metrics, price, context window capacities, success-rate statistics, default model, chat input, token budget, workflow counts. Distinguish enabled toggle from connection-test state. Stopped supplier if shown neutral gray. Honest example data. Do not copy the reference screenshot's sidebar layout or summary cards. Strong row hierarchy, very clean grouping, compact information density, no excessive card shells.
```

## 布局 3：统一模型目录

产物：[model-management-layout-03.png](./model-management-layout-03.png)

完整生成提示词：

```text
Use case: ui-mockup. Create a high-fidelity realistic Chinese AutoFlow desktop model management UI screenshot, 1440 x 1024. Current date anchor 2026-09-12, all data clearly illustrative. Direction name 统一模型目录, no option number text.
Attach existing AutoFlow proxy image ONLY as visual-style reference: warm ivory canvas, clay-brown primary, fine gray borders, graphite Chinese typography, subtle sage success, restrained line icons. Reuse recognizable app logo and top bar. Model management is the only subject. No app/module left sidebar, no permanent right rail, no resource-detail split.
Top nav AutoFlow | 总览 浏览器配置 代理管理 模型管理(active) | 设置.
Main large heading 模型管理, subtitle 在一个目录中管理已添加的模型. Primary upper-right 添加模型, secondary 管理供应商 immediately to its left.
This version centers a SINGLE FULL-WIDTH CROSS-PROVIDER MODEL DIRECTORY TABLE, no supplier cards and no supplier accordion. Directly above table: search field 搜索名称、模型标识或标签, dropdown 全部供应商, dropdown 全部状态. A small plain count "4 个模型 · 示例配置", no metric cards.
Columns 模型名称 / 所属供应商 / 模型标识 / 自定义标签 / 上下文 / 状态 / 操作.
Four illustrative rows:
DeepSeek Chat / DeepSeek 工作账号 / deepseek-chat / 通用 / 未设置 / 已启用 (green switch) / 测试模型  ...
DeepSeek Reasoner / DeepSeek 工作账号 / deepseek-reasoner / 推理 / 未设置 / 已启用 / 测试模型 ...
DeepSeek Chat / OpenRouter 团队网关 / deepseek/deepseek-chat / 备用 / 未设置 / 已启用 / 测试模型 ...
本地测试模型 / 本地 Ollama / local-demo / 本地 / 未设置 / 已停用 (gray switch) / muted 测试模型 ...
The first row is lightly selected and has a compact INLINE test result directly below it: green check 本次测试通过, 已返回响应 · 842 ms（示例）, small monospace reply preview "OK", close/collapse control. No giant analytics card. Models are local configuration records, testing is single call not persistent health. No capability claims for tags.
Open a small conventional action dropdown anchored to second model ...: 编辑模型, 复制模型标识, 停用模型, thin divider, 删除模型 (red). Avoid covering most table; align to edge below anchor.
Near bottom of table a short neutral tip "供应商停用后，其模型不再出现在调用选择器中。" This is true operational guidance, not implementation prose.
Remaining space clean white/ivory. Body 14–16 px, table row height around64, comfortable margins32–40. No billing, price, tokens-per-minute, quotas, default-model button, graph, fake context length, training feature, chat prompt input, third-party integrations. Do not copy any proxy IP or expiry data from reference. Orthographic app screenshot only, no canvas labels, no device frame. Strong visual hierarchy through spacing and separators not nested cards.
```
