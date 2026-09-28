# UI-03 同版打包原生闭环

日期2026-09-28，macOS arm64；状态confirmed，置信度高。代码e49144f2，完整门禁final-frontend-v3-gates.command.json，asar SHA256 7105eb1ce8633cd4005a93c7a6c245bc560daa87d8413312f30deabe363fb867。所有界面输入经CUA；native-evidence.mjs只读截图/正文；SQLite仅mode=ro核验，没有API或数据库补写修正UI结果。

复用原失败专属工作区autoflow-packaged-end-DFc1th，工作流6b2e9cdf-38f0-472f-a3be-273bc11a97fe。原revision3含outer name=原生 End 保存重载验收、config.name=打包真实登录。首次打开正确显示保留勾选、两个独立名称（../native-session-ZM6bSH/initial-fixed-*）。原生分别修改备注=节点备注独立保存、环境名=原生 End 修复后环境、open_page URL=真实本地站点49566/native-end，保存revision4；saved-sqlite.json确认原namespace独立保留。关闭/重开Studio回显一致。完整退出应用且原进程退出后，再启动同工作区，restarted-fixed-*再次显示同值。

随后在主窗口以原生启动弹窗确认1个任务。Task87a4d6f5-08d8-48c9-883c-9e028bdcddfe，Runc9645a83-df96-4a05-9cb1-53e3ea70316d。真实生产worker/CloakBrowser访问本次生成网页，持久output=session_state: native-end-page-read；Run=succeeded，End=completed，环境名实际为原生 End 修复后环境。actual-run-sqlite.json记录全部事件，forbidden后继零访问事件；实际HTTP只有/native-end一次和favicon一次。UI显示成功、End已完成、浏览器退出并清理，环境目录显示新环境就绪（actual-end-completed-*、environment-name-confirmed-*）。

本场景不含正式项目记录关联目标；那部分仍按源码/冻结worker独立场景计数，不混同。新环境已写数据库，未伪造外部结果。整个应用退出后的owned PID/birth全部消失（owned-before-quit.json、exit-check.json）。专属HTTP服务已关闭，完整请求记录在../native-end-site-nFZ3tN/result.json。工作区暂保留用于最终修复后验收与证据清理。

最终广度审查随后要求修复静态recordTargets数组隐藏和SubflowConfig下拉漏读nested两项；本场景不覆盖这些组合，不能因此关闭其finding。最终修复后的补测另记，禁止改写本次e49144f2身份。

额外观察UI-04（待进一步核验，未修复）：当前任务页显示本地19:18执行，持久环境目录保存时间显示11:18，而页面刷新时间19:19。原始截图/文本保留；时间序列化与呈现约定尚需独立核对，不能将其误称本轮已修。此显示问题不改变上述真实环境名和执行终态的核验。
