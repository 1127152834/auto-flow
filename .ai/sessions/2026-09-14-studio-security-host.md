# Studio 旧令牌 UI 清理

按 F5.1 规格删除旧 WebRPA 安全开关/重置/复制/输入接口及 get/setAuthToken 空实现。保留只读安全归属说明，Mock 旧路由 410，不修改 AutoFlow 真鉴权。6 新测试、相关 95 通过；类型/lint/scripts/build 和浏览器只读通过。全量回归进行中，完成后补证据。

下一批核对 retention：源码接口有具体 removed/freedMB，当前 UI 忽略保存/清理错误而伪成功、读取失败无限加载，需要 DTO/Mock/UI/离开完整处理。保留运行数据清理配套，不恢复被排除的 Excel 等节点。

本批完整回归：277 个前端测试文件、3271 项测试通过（481.17 秒）；后端契约 412 项通过，OpenAPI 一致性和目录检查通过。该结果不代表真实自动化或正式 Electron 验收完成。
