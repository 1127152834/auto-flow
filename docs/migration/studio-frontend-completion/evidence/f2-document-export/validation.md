# F2.3 七种导出入口

实际 Toolbar → ExportDialog 覆盖 JSON、Markdown、加密分享包、依赖整包、Playwright Python、Selenium Python、Playwright JavaScript。成功路径校验序列化内容或服务请求；取消不请求、不下载；服务拒绝显示错误并保留草稿。加密包使用真实 WebCrypto 加密/解密及错误密码验证。

停止前 16 项中 13 项通过、3 项红例：已有工作流更新返回错误时，两个脚本导出 handler 仍继续请求脚本并下载旧内容，见 `before.log`。修复仅检查现有 `workflowApi.update` 返回值；失败则写错误日志并立即返回。最终 16 项通过。

Blob URL 和 anchor click 是组件测试替身，不计原生落盘；脚本内容来自明确 Mock，不能算真实后端代码生成。正式 Electron 原生下载保留给 F6。
