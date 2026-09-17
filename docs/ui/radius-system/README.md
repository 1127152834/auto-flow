# 全局小圆角交付

2026-09-14，用户明确授权。从精细网格提交d3afba6继续，在codex/global-table-system隔离分支完成；主目录未合并。

按钮、输入/搜索/选择与文字标签4px；卡片、弹窗、表格外框6px；小型标记2px。主应用和Studio共用radii.css，旧固定像素类改用语义令牌。圆形状态点、开关、画布端口及系统原生窗口边框保持原用途。

- [前后实图对照](comparison.html)
- [设计规范与例外](design.md)
- [手动测试](manual-test.md)
- [机器核验](verification/report.json)

全量254文件/2839测试通过，最终设置回归8测试通过；typecheck、lint、build通过。真实Electron测量按钮和输入4px、背景卡片与弹窗6px，100/200%无页面横溢；恢复100%后验证Escape焦点恢复。浏览器/代理/模型/设置入口和独立Studio令牌一致。表格QA四场景/10图及1万行虚拟滚动回归通过。

最终圆角证据为runs/run-XnkKTB，表格证据为../table-system/runs/components-NUh1kM；两种脚本的hash文件范围不同（前者多含HTML/JS），分别重算均与当前源码相符。早期run-ASnpuy因测试脚本精确匹配“工作流工作台”而漏掉带说明的入口失败；定位已修正，原失败保留。截图按各自viewport及DPR显示，不宣称像素相似度。Windows、打包和用户手测未执行。日志只规范行尾空白，保留原结果。

独立审查补齐文字标签、截图通知和全局Tooltip漏项；最终无阻断。网页示例代码中的圆角不属于应用UI，不随此任务更改。
