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

## F4.1 管理端 Profile 统一接入（2026-09-15）

差异类别：已批准的 AutoFlow 必要适配，依据 scope-database-dp-cloakbrowser.md。浏览器窗口与运行工具栏共享管理端 Profile 选择，运行、浏览器打开及拾取发送 profileId；旧 browserConfig 保留在旧配置数据中，但不再作为启动请求发送。录制继续消费既有浏览器会话，不新建配置体系。失效配置明确阻止启动，不静默换成其它配置；已经打开的浏览器保持原 Profile，后续选择不改变其身份。

Profile 请求期间预占启动身份；关闭不能越过尚未确认的启动。查询失败释放本地未发送占用，启动回执丢失仍由既有状态确认机制接管，不能直接报关闭。服务变化使旧响应失效。配置选择属于工作区界面偏好，不修改流程节点或撤销历史。

新增用例：F4-PROFILE-001（共享选择/不可用项），002（空/失败），003（旧参数不发送/活跃配置冻结），004（查询中关闭/失败释放），005（删除配置禁止替代），006（运行快照冻结配置），007（正式窗口入口与关闭取消）。组件与协议文件 browser-profile-select.test.tsx、browser-profile-protocol.test.ts、run-start-boundary.test.tsx；旧浏览器/拾取/离开测试继续保留。

正式 Electron macOS arm64，构建 HTML，独立验收 user-data-dir：从主窗口“工作流工作台”进入，工具栏显示“受控浏览器配置（Mock）”；打开自动化浏览器，显示同一配置且无内核/路径管理；点击打开后出现空白目标页；界面输入 http://local.test/profile 并跳转，目标页回显该地址；启动选择器后显示停止选择；关闭触发结束会话确认，取消后浏览器和拾取仍活跃；再次确认结束后恢复“打开浏览器”及配置选择。全部为 CUA 真实点击/输入，没有 Store 注入。此证据仅验证 Mock 服务消费与正式窗口交互，未启动真实 CloakBrowser，也不证明真实导航/聚焦。

检查记录见 evidence/f4-browser-profiles。10文件125用例联合回归首次124通过，导航用例在页面列表就绪前点击禁用按钮而失败；改为先断言按钮已就绪，再保留原重复提交/互斥断言，18项生命周期回归通过。后端23项合同通过，renderer/main/preload构建通过。最终集合结果以随后同目录日志为准，不将分次通过数相加。

最终本块：10文件125项回归通过（final.log），另页面代际6项专项通过；二者不重复相加。TypeScript、OpenAPI、ESLint、Ruff、3项目录检查通过。正式窗口证据运行在Profile接入构建；随后代际补丁构建见build-final.log，迟到响应本身以memory/HTTP受控传输验收。
