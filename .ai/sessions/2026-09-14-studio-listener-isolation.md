# Studio SSE 订阅者隔离

2026-09-14；状态 confirmed。StudioEventClient.dispatch 原先把界面回调异常传入传输重连/命令查询分支，造成重放和误查询。现逐订阅者捕获并输出错误，继续派发；业务数据不附加写入日志。3 项新增复现加恢复回归 9 项通过，内存/HTTP 双实现。详见 docs/migration/studio-frontend-completion/listener-isolation.md。
