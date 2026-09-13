# F0 浏览器检查

日期：2026-09-13；环境：macOS，Codex 内置浏览器，独立来源 http://localhost:5175/studio.html；未修改用户 http://127.0.0.1:5175 的草稿。

真实 UI 操作：
1. 打开独立预览，观察模块库 284。
2. 点击“更多操作”→“全局配置”。AX 展示系统、AI对话、小助手、MCP、AI智能、邮件、存储、数据库、显示、浏览器、触发器、安全、凭据库、留存清理；无 QQ/飞书。
3. Excel 资源入口移除后重新加载：底栏显示执行日志、数据表格、全局变量、图像资源；无 Excel 资源。

使用 CUA click/reload/getAXState，未向页面注入 Store 或修改页面内部状态。此记录为浏览器交互观察，不是 Electron 打包入口验收，也未验收持久化保存。

## F0-UI-003（2026-09-13）

独立 localhost:5175 测试 origin，未操作用户 127.0.0.1 文档。通过真实按钮和浏览器受支持的 filechooser 上传 /tmp/autoflow-f0-legacy-bundle.json，未直接改 Store。

1. 宽窗口原来缺“导入整包”入口，已复用现有处理函数增加按钮。
2. 导入含 old-excel/excel_create 的测试包，画布显示已排除提示，属性区显示原 JSON。
3. F5 返回“工作流包含已排除节点；请移除这些节点后运行，原文档仍可保存或导出。”，保持空闲。
4. 保存显示“工作流已保存: F0 旧节点保护测试.json”。
5. 刷新→打开→双击测试流程→选择旧节点，原 path=/original.xlsx、custom=preserve 及 label 均可见。

原生宿主访问被工具限制拒绝；随后使用浏览器正式 filechooser 接口完成上传，未绕过宿主限制。content.export 不受当前浏览器支持，证据为本会话工具返回的 DOM 状态及本记录，不伪造截图文件。
