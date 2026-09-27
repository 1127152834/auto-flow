# 浏览器节点真实只读补测

日期：2026-09-28；状态：confirmed；置信：高。使用当前生产 HTTP sidecar、项目 worker、统一 WorkflowRuntime/production registry 和公开 CloakBrowser 145.0.7632.109.2，全新专属 SQLite 工作区与浏览器配置。

一组真实工作流、1 个任务、26 次节点访问、19 种节点类型，全部执行成功；9 项实际断言全部通过。实际运行 2026-09-28 01:34:47–01:35:05 +08:00。这组独立计数，不并入此前 7 批次/14 任务或其他代理的节点脚本场景数量。

输入仅为公开 `https://example.com/` 和仓库当前 `apps/backend/pyproject.toml`、`package.json` 的真实文件；没有生成测试 HTML、替换 Browser provider、安装依赖、登录账号、上传数据或写第三方网站。节点图通过真实 API 创建，执行事实来自生产持久节点尝试、输出和产物接口。

| 实际执行节点类型 | 实际场景/断言 |
|---|---|
| `open_page` | 公开 HTTPS 当前页、实际 TOML 新标签页、实际 JSON 当前页均成功；后续比对真实内容 |
| `wait_page_load`, `page_load_complete` | 页面完成 load/domcontentloaded，持久输出 `public_loaded=true` |
| `wait_element`, `get_element_info` | 等待真实 h1 可见并读到 `Example Domain` |
| `element_exists`, `element_visible` | 查询真实 h1，节点成功；本组只覆盖正向元素，不宣称反向/隐藏分支已覆盖 |
| `get_child_elements`, `get_sibling_elements` | body 子元素和 h1 兄弟元素 selector 列表非空，与当前真实 DOM 对应 |
| `hover_element` | 对真实 h1 执行 hover，持久节点尝试 succeeded |
| `inject_javascript` | 只读 document.title/h1/location、滚动量和文件正文；不修改 DOM |
| `screenshot` | 生产产物 API 返回并下载实际公开网页 PNG，20,253 字节，视觉复核为 Example Domain 页面 |
| `switch_tab`, `use_opened_page` | 首 tab index=0/title=Example Domain，末 tab index=1/url=真实 TOML；按真实 URL 定位已打开页面成功 |
| `refresh_page` | 刷新实际 TOML 标签页，节点成功且后续正文与磁盘原文一致 |
| `scroll_page` | 滚动真实长 TOML 文件，断言 `scrollY>0`，正文仍与真实磁盘文件一致 |
| `go_back`, `go_forward` | 返回 TOML 时完整文本匹配；前进 JSON 时完整解析结果匹配实际 package.json |
| `close_page` | 最后关闭公开网页 tab，节点成功，整个任务 succeeded |

清理：任务后的临时环境目录为空；sidecar 正常关闭，进程列表确认无本工作区进程。没有操作任何既有用户浏览器会话。

证据：[机器结果及精确配置/节点清单](browser-node-results.json)、[原始持久结果](run-plf91uw9/results.json)、[HTTP 记录](run-plf91uw9/http.jsonl)、[截图](run-plf91uw9/browser_nodes-d69604df-886d-4de1-8557-3aacb61ef113-ada8b2af-8e53-49ae-b85d-3f4a69b8cc10.png)、[可运行脚本](browser_node_qa.py)。

未覆盖：真实账号写入/提交、上传、验证码、反爬挑战、iframe、下载交互、第三方付费服务、浏览器崩溃或长期稳定性。本组 19 种类型与其他组存在重叠；综合类型覆盖必须求集合并集，不能直接相加。
