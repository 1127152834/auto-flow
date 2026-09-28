# UI-09：打开已有工作流后的保存与可见错误

日期：2026-09-28；状态：confirmed；置信度：高。来源：当前源码、真实 macOS arm64 目录包、原生 UI、独立 SQLite 与回归测试。提交：本文件所在修复提交。

根因：打开对话框同步载入 Store 的新 documentId 后，Toolbar 回调仍绑定上一次 React render 的 documentId，导致现有 server workflow 身份被判为无效。后续保存误发 POST 创建，真实后端返回 409 WORKFLOW_ID_CONFLICT。原错误只写日志；已选择历史运行时，保存错误不可见。受影响入口包括打开已有工作流后保存及保存后离开。

修复：共享身份设置回调从当前 Store 读取同步文档身份；异步调用方原有文档/连接有效性检查保持。保存错误在当前文档显示可关闭的 role=alert，保留草稿，拒绝迟到错误污染新文档。不改变服务端冲突契约。

证据：`ui-current/native-save-response.json` 是旧包真实 409；`studio-open-save-red.log` 的新断言在旧代码失败，HTTP 方法预期 PUT 而实际 POST。`studio-open-save-fixed.log`：3 文件48项通过，含 PUT expectedRevision=7、保存后清脏，以及409错误可见且草稿仍脏。前端完整回归 `frontend-final.log`：431文件5650项通过；`studio-open-save-types.log` 和 `frontend-lint-final.log` 通过；构建和目录包见相应 build/package 日志。`before`、`green` 日志保留测试编写期间的 API/断言器错误，不计为产品缺陷或有效红灯证据。

真实验收：专属工作区 LarBgx 中，通过原生 UI 打开已有「实际package.json脚本审计」，修改名称并保存，修订1→2；刷新后重新打开仍为2；正常退出整个应用、启动同一工作区后，目录仍显示新名称和修订2。截图/正文：`native-save-fixed-revision2-*`、`native-save-restarted-*`。这是实际正式文档的保存/读取，不是替身成功响应。原生操作经 CUA，证据捕获只读。流程脚本来自真实仓库 package.json，旧包执行已得到实际包名及15个脚本名称；没有外部账号或供应商调用。

限制：409新横幅的动态拒绝由 HTTP 组件回归验证；未在打包包内人为篡改并发数据库触发409。未验收 Windows/Intel。应用重启后已保存文档可重新打开，不等于运行检查点恢复；PM9 R3 仍独立未完成。
