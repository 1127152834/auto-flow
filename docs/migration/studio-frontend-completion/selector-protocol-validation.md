# 定位测试协议与场景验收

## 范围

发布 StudioSelectorTestRequest / StudioSelectorTestResult 及候选、元素摘要 schema，通过 OpenAPI 生成前端类型；没有安装真实自动化后端路由。成功结果必须有 matched 与非负安全整数 count，且二者一致。可选候选/元素字段保持源接口兼容，前端拒绝格式错误的成功响应，不展示 undefined 命中数。

Mock 增加显式零/一/四匹配与服务失败夹具，仅开发预览入口提供场景按钮。关闭浏览器返回业务失败；错误方法405，非法请求422。预览不会根据选择器猜测 DOM，不执行真实定位。

## 源码映射

依据冻结 reference/WebRPA/backend/app/api/element_picker.py 的 TestSelectorRequest 和 test_selector：selector/hints/highlight、count/matched/tried/element 原字段保留。源关闭浏览器通过 HTTP200 success:false 返回，本实现相同。源空选择器返回业务失败；Mock 作为非法请求以422拒绝，后续真实接口适配需遵守已发布契约。源可能把候选语法错误放入 tried 后返回零匹配；显式 Mock 失败场景不声称修复源定位器行为。错误响应复用现有错误包，不冒充成功结果 schema。

## 测试

新增协议28项：内存/真实本地HTTP各10项，畸形成功响应8项。首次26失败2通过，修复后28通过；与既有上下文保护9项合计37通过。后端新增18项契约通过。UI实际点击零/一/多/失败/未打开浏览器通过，见 evidence/f4-selector-protocol/browser.md。

类型、lint、Ruff、mypy、构建、21脚本及 OpenAPI 检查通过。完整前端回归138文件1690项通过。全部证据保存于 evidence/f4-selector-protocol。

## 尚未完成

全局拾取/录制会话所有权、真实定位执行、框架失效、正式Electron及跨平台仍未验收；本批不代表F1或F4整体完成。
