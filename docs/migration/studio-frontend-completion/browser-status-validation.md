# 浏览器状态合同与停止期间结果失效

2026-09-14，状态：confirmed（有界交付，F0–F6 未全部完成）。

冻结 WebRPA 的 backend/app/api/browser.py 状态接口返回 isOpen 和 pickerActive 布尔字段。新增严格 OpenAPI 模型并生成前端类型；两字段独立，不把异常组合静默改写。前端共享 API 拒绝缺失、字符串和数字标志，保留最后确认状态。AutoBrowserDialog 在变更命令期间暂停轮询并作废在途结果，停止尚未完成时迟到的选择结果不能复制到剪贴板。

用例：内存和实际本地 HTTP 分别验证关闭、打开、拾取、停止关闭的状态往返；六种畸形响应；实际组件刷新失败保留已打开状态；停止等待时迟到结果不复制。后端八项严格合同校验通过。协议首次六失败两通过，新增 UI 首次两失败，修复后相关三文件23项通过。

完整前端146文件1736项通过；类型、lint、renderer/main/preload构建、21工程脚本、OpenAPI一致性、Ruff、mypy通过。证据位于 evidence/f4-browser-status。此处 HTTP 使用受控 Mock 服务，未声称真实浏览器执行、原生宿主或各平台打包端到端通过。

仍需完成跨入口拾取所有权、稳定会话/命令标识和宿主异步离开保护。本次轮询失效不等于这些全局生命周期已完成。

## 2026-09-15：目标页与 Profile 适配（F4.1）

属于已批准 F4.1 增强和 AutoFlow 必要适配。保留冻结 AutoBrowserDialog 的面板及打开/关闭/拾取/原配置行为；新增 BrowserPagesPanel，以既有请求层消费页面身份，复用父组件命令锁，未新建RPC或执行器。Profile读取复用 `/api/v1/profiles`，选中后启动只传 profileId，不把原版参数混入所选Profile；未选择时保留原版设置。

GET `/api/browser/pages` 返回 sessionId、revision、targetPageId、pages(pageId/title/url)。POST 同路径接收 sessionId、expectedRevision、pageId、action(select/focus/navigate)、url；会话或修订变化409，目标关闭409。聚焦不改变目标和修订；选择/导航更新修订并使原拾取结果失效。页面列表不根据索引自动替换关闭的目标。正式后端需兑现该合同，Mock只提供受控状态变化。

实际CUA浏览器UI：打开→两个页面服务夹具→选择弹出页→聚焦→导航，页面列表仅更新所选页；目标关闭夹具→重开面板，显示请选择，聚焦/跳转禁用；选择受控Profile并打开后显示空白页。没有直接修改Store。Mock聚焦只验证命令确认，不是原生浏览器聚焦验收。

检查：25文件275项浏览器/拾取/录制定向回归，9项后端页面合同，TypeScript/ESLint/OpenAPI/mypy及renderer/main/preload构建通过，详见evidence/f4-browser-pages。原命令串行回归发现页面命令曾绕过父锁，已修复并保持原断言；失效拾取按既有合同返回active=false/selected=false，不把正常失效当HTTP错误。

未关闭项：正式Electron/原生聚焦归F6；运行/录制互斥及宿主离开归F5；页面导航中的复杂框架失效矩阵继续核销。此处不宣称 F4 全部完成。
