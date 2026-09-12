# 模型供应商品牌资源

- 日期：2026-09-12
- 状态：confirmed，已下载并核对官方品牌参考。
- 来源：用户要求纠正模型管理中不真实的供应商图标；官网、官方媒体/品牌资源包及图标仓库。
- 范围：10 个预置供应商品牌。自定义接口使用现有 Phosphor 连接图标，不伪装为某个品牌。

## 来源与选择

8 个文件直接来自官方，DeepSeek 和 MoonshotAI 为与官网对照过的 LobeHub 整理版。下载/解包后保留原字节、路径、颜色和比例，不做手绘重建、着色或裁切。

| 品牌 | 文件 | 官方参考 | 下载来源 | 选择说明 |
| --- | --- | --- | --- | --- |
| OpenAI | [openai.svg](./openai.svg) | [品牌规范](https://openai.com/brand/) | [官方品牌包](https://cdn.openai.com/brand/OpenAI-Logos-2025.zip) | `OpenAI-logos(new)/SVGs/OpenAI-black-monoblossom.svg`，黑色 Blossom |
| Anthropic Claude | [anthropic.svg](./anthropic.svg) | [官方新闻室](https://www.anthropic.com/news) | [官方媒体包](https://anthropic.com/press-kit) | `Anthropic media resources/Anthropic logos/Claude logos/3 Claude Spark/SVG/Claude Spark - Clay.svg`，Claude 产品星花 |
| Google Gemini | [gemini.svg](./gemini.svg) | [Gemini](https://gemini.google.com/) | [Google CDN](https://www.gstatic.com/lamda/images/gemini_sparkle_aurora_33f86dc0c0257da337c63.svg) | 官网引用的彩色 Aurora sparkle，内嵌 JPEG 也随文件保留 |
| DeepSeek | [deepseek.svg](./deepseek.svg) | [官网](https://www.deepseek.com/en/) / [官方仓库字标](https://github.com/deepseek-ai/DeepSeek-LLM/blob/main/images/logo.svg) | [LobeHub SVG](https://raw.githubusercontent.com/lobehub/lobe-icons/master/packages/static-svg/icons/deepseek.svg) | 与官方鲸形标志核对的单图形 SVG；第三方整理，非官方分发 |
| 通义千问 | [qwen.png](./qwen.png) | [Qwen 官方站点](https://qwenlm.github.io/) | [官方 favicon](https://qwenlm.github.io/favicon.png) | 512×512 PNG；Qwen 品牌，不是阿里云标志 |
| 智谱 AI | [zhipu.png](./zhipu.png) | [智谱官网](https://www.zhipuai.cn/zh/about) | [官方 favicon](https://www.zhipuai.cn/favicon.png) | 96×96 PNG；官网当前 Z.AI 标志 |
| 月之暗面 | [moonshot.svg](./moonshot.svg) | [Moonshot 官网](https://www.moonshot.cn/about/) / [官方 favicon](https://statics.kimi.ai/moonshot-ai/favicon.ico) | [LobeHub SVG](https://raw.githubusercontent.com/lobehub/lobe-icons/master/packages/static-svg/icons/moonshot.svg) | 与官网核对的 MoonshotAI 图形；不以 Kimi 产品图标替代供应商品牌 |
| 硅基流动 | [siliconflow.svg](./siliconflow.svg) | [官方品牌资源页](https://siliconflow.cn/brand) | [官方品牌包](https://static02.siliconflow.cn/www/cn/res/20260615/SiliconFlow_LOGO.zip) | `siliconflow_logo_SVG/siliconflow_Single graphic LOGO.svg`，原始单图形 |
| OpenRouter | [openrouter.svg](./openrouter.svg) | [官网](https://openrouter.ai/) | [官方 v2 glyph](https://openrouter.ai/brand/v2/openrouter-glyph-light.svg) | 浅色背景适用的官方紫色 v2 标志 |
| Ollama | [ollama.svg](./ollama.svg) | [官网](https://ollama.com/) / [官方仓库](https://github.com/ollama/ollama) | [官方仓库 SVG](https://raw.githubusercontent.com/ollama/ollama/main/docs/logo.svg) | 透明底黑色 llama 图形 |

## 显示与打包

- `../provider-icons.ts` 使用 Vite 可静态分析的 `new URL(..., import.meta.url)`，随应用打包，无运行时外部图标请求。
- `ProviderLogo` 统一 32/40/56 px 容器，白底与中性边框，保留品牌自身颜色；旁边始终显示供应商名称。
- OpenAI 和 SiliconFlow 原始 SVG 自带留白，组件不重复加内边距；不改写其 viewBox 或图形。
- 品牌图标为伴随文本的装饰元素（`aria-hidden`、空 `alt`），不重复朗读；加载失败才显示通用连接符，失败不会影响之后切换的供应商。
- 协议、预设 ID、连接地址及原有交互不变。Claude 产品星花对应现有 `Anthropic Claude` 文案，代码仍沿用 `anthropic` 预设 ID。

## 归属与许可记录

各品牌名称和标志属于其权利人，这些标志只识别用户可连接的供应商，不表示合作或背书。官方下载素材未统一附带开源许可证，保留各自来源与品牌规范，不能将应用许可证或代码仓库许可证视作商标授权。

- DeepSeek、MoonshotAI 的 LobeHub 图标代码来源为 MIT；完整版权与许可见 [LICENSE.lobehub](./LICENSE.lobehub)。
- Ollama 官方仓库的 MIT 版权与许可见 [LICENSE.ollama](./LICENSE.ollama)。
- OpenAI 按 [官方品牌规范](https://openai.com/brand/) 保留原标志、颜色、比例与留白。

## 完整性

本次 SVG 均通过 XML 解析；未包含脚本、foreignObject、事件处理或外部资源链接。Gemini 原 SVG 的 `data:image/jpeg` 是自包含资源。两个 PNG 的签名和尺寸已核对。

| 文件 | SHA-256 |
| --- | --- |
| anthropic.svg | `6d53db4be375e899c937c26cf16684a80d6e869b1928d72b37748bef2560e219` |
| deepseek.svg | `8f9443e351b6dacce71871790201b799d92e8bf96a45ef79aeb5e9bf4db423e2` |
| gemini.svg | `f56df33f86dc0c0257da337c63bf7ad68c0a1b27b796ec707e147984351bccb3` |
| moonshot.svg | `435f41b74e6a87639b6bf860e9628f20cbe7d6229bece412d548f4cea3081852` |
| ollama.svg | `cfcdccd391bdff7c16b55eb9f6e13aa8b8bfe9f6e4a75a3a39783a6a1601c45f` |
| openai.svg | `7be72f1fea831d3ba81a545cee79b7e0ae69449d5d7837c9571ccbfb4aa1e00b` |
| openrouter.svg | `f1be26f98d70ac8d5541c517905ef2dcac1b59d20f49ca8c175219e6cf52d5d1` |
| qwen.png | `a98b91d365fba5f08370d8d8755aa60692be0e6c64124cc33bb282c9fb2432cb` |
| siliconflow.svg | `05c50978b752802e478fec109a1ff911370124ec848efaa4a438073e3345cb1f` |
| zhipu.png | `3e979232af050c67d2a8ceda1359e6b38301f6d9d6b00ac9c7e0e8a77df167ea` |
