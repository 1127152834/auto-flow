# F4 拾取会话身份与恢复

日期：2026-09-15；状态：本切片已实现，F4 录制与完整宿主离开协调继续推进。

## 契约

启动和停止使用稳定 `sessionId`。同 ID 同参数启动保留当前选择；改变参数、访问或停止其他活跃会话返回 409。停止失败保留占用；已经停止的原会话可以重复确认关闭，但不能干扰后续新会话。

单选、相似元素、状态和定位测试绑定会话。客户端也校验连接代次与会话身份，拒绝迟到响应。前端刷新后先查询服务状态再恢复当前会话，无法确认启动时保留原 ID 和停止入口。响应丢失后查询原 ID，不自动另开会话。组件卸载仅可清理原连接中的会话。

生成类型来自 `StudioPickerSessionRequest`、`StudioPickerSessionStartRequest`、`StudioPickerSessionState`；定位测试增加可选 `sessionId`。仅扩展正式后端的 OpenAPI 契约，真实浏览器实现仍待后端阶段。

## 验证

- 逐项用例及前置、操作、界面、请求、状态与证据路径见 [用例台账](picker-session-cases.json)。内存与实际本地 HTTP 使用同一组协议断言。
- 前端全量：288 文件 / 3,443 用例通过。之后增加启动非法参数的严格校验和外部关闭状态反馈，最终相关专项分别 104 项和 15 项通过；不把先前全量统计写成新增补丁之后的全量。
- 后端合同：456 项通过，其中新增会话合同 13 项。
- 类型、ESLint、OpenAPI 一致性、Ruff、mypy、renderer/main/preload 构建及 49 项脚本检查通过。原始输出位于 `evidence/f4-picker-session/`；`build-final.log` 为外部关闭状态反馈补丁之后的最终构建。
- 浏览器 UI 完成拖入节点、拾取、定位、保存、刷新和重开；见 [浏览器证据](evidence/f4-picker-session/browser-ui.md)。所有结果来自明确标识的 Mock，不代表真实网页拾取或正式 Electron 实机闭环。

## 剩余边界

录制的全局会话归属、宿主离开矩阵和正式 Electron/打包验收尚未关闭。没有恢复被退役的工作流执行器，也没有扩展已排除节点。F0–F6 整体保持未完成。

## 2026-09-15 页面代际与框架边界补充

状态：confirmed（前端页面代际响应消费已完成专项核验；不是实际 iframe 定位验收）。

冻结 `WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb` 的 `backend/app/api/element_picker.py:155–158` 中，`TestSelectorRequest` 只定义 `selector`、`hints`、`highlight`；`api_test_selector` 使用当前 `page.locator` 进行候选定位，没有结构化 `framePath` 请求合同。`backend/app/services/browser_manager.py:317–374` 的 `_get_picker_result` 遍历页面及其 frames，跳过导航期间的读取异常，直接返回采集元素；该响应没有独立 frame-path 身份。前端沿用已有 selector/hints 消费，不凭空添加结构化 framePath，也不把保留任意 hints 当作已实现框架定位。

本次发现并由主任务修复的前端问题是：服务已经生成的旧页面拾取/定位响应，在同连接页面导航完成后仍会被接受。公共 API 现在同时核对页面操作代际；页面列表轮询观察到服务 revision 变化也会使旧请求失效，首次建立列表基线不会仅因读列表而取消请求。保留原拾取会话身份用于后续状态查询和恢复。

新增测试文件：`apps/desktop/src/renderer/domains/workflows/tests/picker-page-generation.test.ts`。

| 用例 ID | 前置与操作 | 验收结果 / 层级 |
|---|---|---|
| `PICKER.page-generation.memory`、`PICKER.page-generation.http` | 挂起已生成的旧元素响应，确认导航后再释放；查询失效状态并启动新会话，再读新元素 | 旧响应拒绝，新会话新元素可用 / 内存与实际本地 HTTP 消费 |
| `SELECTOR.page-generation.memory`、`SELECTOR.page-generation.http` | 挂起已生成的定位结果，确认导航后释放；恢复后重新定位 | 旧响应拒绝，新请求正常返回 / 内存与实际本地 HTTP 消费 |
| `SELECTOR.page-poll.memory`、`SELECTOR.page-poll.http` | 挂起定位结果，Mock 服务页面变更，通过 `browserApi.pages` 轮询观察更高 revision，再释放旧结果；恢复后重新定位 | 轮询观察使旧响应失效，新请求正常返回 / 内存与实际本地 HTTP 消费 |

六项专项通过，输出见 [target-after-fix.log](evidence/f4-picker-page-generation/target-after-fix.log)。原四项红测记录见 [target.log](evidence/f4-picker-page-generation/target.log)：预期拒绝但实际返回成功；随后增加轮询观察及恢复断言，没有放宽旧响应拒绝要求。初版 HTTP 测试因使用 `String(Request)` 未识别 URL 而超时，修正测试传输包装后才收集该四项纯断言失败证据。

既有 `browser-pages-protocol.test.ts` 已核验页面选择/导航修订、关闭目标及会话变化；`picker-session-protocol.test.ts` 已核验连接切换；`selector-test-context.test.tsx` 已核验节点、字段、文档变更。此次仅补同连接页面变更的在途响应缺口，没有重复上述矩阵。

据此可核销 **前端已观察到页面变化后的拾取/定位响应失效及恢复** 子项。实际跨域/嵌套 iframe 查找、iframe 自身导航的识别与版本发布、脚本重注入、真实页面高亮，仍由真实浏览器后端实现和实机验证；未观察到的后端框架变化不能由前端单独推断。本批没有运行真实 iframe，没有创建假浏览器执行器，不宣称完整真实框架矩阵通过。主计划当前状态优先于本文件早期的全模块剩余边界描述。
