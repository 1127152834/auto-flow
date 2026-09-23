# Telegram 节点正式窗口验收（2026-09-23）

证据：[result.json](result.json)。macOS arm64 开发构建中，通过真实鼠标和键盘在 Studio 添加 `notify_telegram`、填写三个字段、保存、切换文档、重开并运行。生产执行器及 `httpx` 未修改；临时测试进程将 Bot API 的 TCP 连接定向到本地受控 TLS 服务，保留原域名与证书主机名校验。服务确认中文 JSON 请求一次成功、一次返回 `ok=false`，运行状态和节点日志分别为成功与失败，日志不含测试 Token。两个运行终态均在 worker 清理后写入；Electron 退出、夹具端口关闭。独立临时工作区，不接触用户数据库。

先前失败目录 `formal-telegram-electron-yIcHNY`、`nMsfgx`、`eu9yrX`、`6x6GbI`、`AL73MY`、`LX8VSM` 留作夹具排错记录：最初连接未定向到本地服务，假 Token 得到失败响应；随后同步探针阻塞了 Node 服务的 TLS 握手，再修正为异步探针。`formal-telegram-electron-w7xeLb` 已通过业务断言，本次复跑补齐端口及 Electron 退出断言。没有用 Mock 执行器或改写节点规则。真实 Telegram 供应商投递、macOS Intel、Windows 和冻结包未验收。
