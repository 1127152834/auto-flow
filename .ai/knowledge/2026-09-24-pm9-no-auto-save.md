# PM9 XE-A09 不自动保存与清理后的任务界面

日期：2026-09-24。状态：confirmed 本机旧包会话行为/界面反例及源码修复；新包验收进行中，releaseAccepted=false。

当前 cb040daf ARM 包的真实浏览器已证明：保存会话值1；新工作副本改为9，End retainEnvironment.enabled=false；随后新Task恢复1，原环境代次/元数据不变，两次实例清理且目录不存在。旧包完整桌面链通过其当时断言，但截图实际显示已清理任务仍提供“结束并保留”表单，该界面不是验收通过。新脚本追加环境总数不增加、显示已清理说明且无保存按钮的断言，等待新包运行。

根因：TaskEndPanel只区分是否存在实例，没有检查cleaned状态。修复复用现有实例查询：cleaned显示“本次浏览器工作副本已清理，不能再次保存本次会话。”；已知saved_unlinked仍允许原操作仅修复关联，修复成功后依据最新结果移除该入口；结束/修复响应后刷新实例事实。后端保存、身份和权限契约没有变化。

验证：新增cleaned组件反例修复前1 failed/1 passed；相关组件/Task页面8 passed。测试夹具首次未等TanStack异步通知的比较失败已修正并保留。最终完整前端409文件/5475 passed（525.26秒）。初轮桌面检查漏写任务地址/io造成超时属于脚本错误；修正后旧包24截图完整链通过，会话/目录证据与界面缺陷分别记录。构建、最终类型/lint/脚本和新包验收结束后补专项报告。

来源：scripts/project-runtime-smoke.mjs、scripts/smoke-project-management-desktop.mjs、TaskEndPanel.tsx；证据目录 .tmp-tests/pm9-no-auto-save-2026-09-24/。仅固定环境、本机ARM受控站点；不证明输入关联环境、身份持久化I1–I3、Google或Windows/Intel实机。无跨进程恢复或新执行器。
