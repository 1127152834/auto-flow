# 本机真实应用验收补充

日期2026-09-28；平台macOS arm64；来源真实Electron、冻结sidecar、SQLite、实际仓库文件与原生对话框；置信度高。仅本次独立工作区；没有供应商账号/外部消息。UI动作经CUA，`native-evidence.mjs`只读保存截图/正文，不修改UI/响应。本次三轮原生会话进程及调试端口已退出（native-sessions-cleanup.json）；原首次退出还独立确认sidecar退出（native-quit.json）。核验目录归属、专属标记及无进程引用后，专属工作区和克隆内核已删除（native-workspace-cleanup.json）；导出xlsx、截图与SQLite只读核验结果保留在本目录。历史会话脚本引用的临时目录已不存在，重跑应创建新的专属工作区。

## 范围及独立计数

- `ui-current/result.json` 是早一轮built Electron脚本：27通过、1失败。失败为UI-06b自动选择Profile未达到目标；保留原结果，不修改为绿。相同生产流程随后经原生UI选择真实配置、打开JS编辑器、测试运行与F5正式执行，真实SQLite中的已完成运行和节点返回实际package.json内容，见native-db-evidence.json；这是一条人工操作补验，不声称原自动脚本通过。
- 原生场景1：导出实际仓库文件元数据5条，macOS保存面板写真实xlsx；openpyxl读取6行（1表头+5数据），内容及SHA可查native-export-verification.json。保存面板将输入全路径误作带冒号文件名，落到记忆的旧验收目录；只将本次新生成文件移动到本目录native-export.xlsx，历史文件未改写。此操作偏差明确记录，不声称第一次面板路径输入正确。
- 原生场景2：从该xlsx导入，将实际文本字节数字段映射为Number，服务端拒绝第2行第2列字段bytes；UI确实显示完整行列字段与原因。原生AX观察及SQLite失败operation为证；当时未另存错误截图，不能声称有截图。
- 原生场景3：使用“修改后开始新的导入”改回Text，新操作成功5条，名为“原生导入源码清单”。刷新、退出整个应用并重启，同一工作区仍有两表、各5条。`native-import-refreshed-*`、`native-import-restarted-*`。这是新操作而非覆写原失败记录。
- 原生场景4：原包打开已有工作流后保存409，修复包保存修订1→2、刷新重新打开、应用退出重启后再读取成功。详见studio-save.md及native-save-sqlite.json。实际Monaco0.57编辑器已打开、编辑和执行真实package.json脚本；没有伪造外部响应。
- 自动真实浏览器补跑独立43项通过（real-browser-current.log/xml）；冻结生产项目worker场景独立1项通过（frozen-project-data.log/xml），不与默认后端跳过项目混算。
- Studio smoke：built/dev/packaged各5个检查，主要是宿主入口/窗口/清理，不是15条业务流程。

## 限制

全局页面遍历只证明本次数据下可进入及布局基本显示，不证明供应商/硬件能力。原生200%只在脚本记录页面检查，不扩为所有输入控件验收。未运行Windows/Intel和真实Android设备；未恢复PM9持久执行检查点。旧JS正式运行后曾出现“项目交互连接中断，正在查询原请求；未重新执行脚本”横幅，刷新后消失；运行与结果已持久成功，但此瞬时横幅的产生机制仍待核查，未记为已修复。
