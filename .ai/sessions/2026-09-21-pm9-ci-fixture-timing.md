# PM9 三平台矩阵时序失败

日期：2026-09-21。状态：confirmed。来源：Actions 35590418456 @0303924d（生产 f580b1c6）的真实日志。

ARM 完整成功：后端 3329 passed / 60 skipped / 760.33s，前端 5459 / 406，通过真实 worker、源码/打包 HTTP/业务/桌面冒烟、DMG 与固定合成日志负载；报告 ci-capabilities-darwin-arm64.json。该报告不代表新增 C1/C2 源码。

Windows 全量 3317 passed / 71 skipped / 1 failed / 1156.01s。人工继续测试的 100ms 自动预算在两次数据库状态迁移和第二次 pause 前用尽，生产正确拒绝过期代次。测试预算改为 2s，两次人工等待分别 2.1s，仍严格超过完整自动预算，自动期间仍断言扣费；不修改生产预算。28 dispatcher tests passed / 10.74s。

Intel 后端通过，前端 5458 passed / 1 failed。ProxyManagementPage 的初次过滤请求由 0ms 定时器发起，原测试在初始异步 effect 完成前启动 findByText 的期限。测试等待 act 完成及该零延时请求后再断言，未加全局宽限。14 tests passed / 4.25s。平台复验随共享领取稳定候选执行，不把本机通过当作 CI 已修复。

完整 PM9 仍未退出，releaseAccepted=false。
