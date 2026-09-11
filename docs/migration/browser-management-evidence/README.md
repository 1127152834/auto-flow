# 浏览器管理原始运行证据

以下 JSON 是本轮 macOS arm64 隔离验收时记录的原始响应和观察结果，从临时目录原样归档；没有输入 License，也没有更改用户业务数据。

- [validation-evidence.json](validation-evidence.json)：冻结 sidecar 的真实发布列表、公开内核 `145.0.7632.109.2` 安装任务终态和实际安装目录信息。列表中的正式版元数据不代表授权版下载已通过。
- [cancellation-evidence.json](cancellation-evidence.json)：公开内核 `142.0.7444.175` 下载取消后，worker 已退出、staging 已删除，服务仍健康。
- [timezone-before-evidence.json](timezone-before-evidence.json)：修复前冻结进程在 `PYTHONTZPATH=''` 下拒绝有效 `Asia/Shanghai` 的 422 响应。修复后结果由提交的源码/打包 smoke 验证，详见 [验收记录](../browser-management-validation.md)。

JSON 中的临时安装路径和 operation/request ID 仅用于追溯这次运行，不是运行配置，也不保证系统临时目录永久保留。
