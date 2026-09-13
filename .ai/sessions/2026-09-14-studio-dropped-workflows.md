# Studio 文件拖入保护

2026-09-14；状态 confirmed（实现与定向测试）。

源 WorkflowEditor 的 FileReader/密码/解密链无文档身份保护，多文件同时争用密码弹窗；mergeWorkflow 未记录历史或未保存状态。提取同一入口为 droppedWorkflows，按文件顺序处理并订阅文档身份失效；复用 Store 合并、原密码提示和 Web Crypto。mergeWorkflow 增加历史与 dirty；密码请求替换/卸载取消旧等待。

验证与边界见 docs/migration/studio-frontend-completion/dropped-workflow-protection.md。F0–F6 继续推进，当前只有前端和 Mock 合同，不代表真实运行或正式 Electron 文件拖拽验收。
