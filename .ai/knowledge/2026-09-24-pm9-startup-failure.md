# PM9 启动失败与记录再次领取

2026-09-24 DATA-CLAIM-03启动失败根因修复（confirmed本机源码子范围）：真实子进程在浏览器启动失败时返回finished/failed，旧父进程仅接受ready并误报interrupted。共用协议入口现接受启动前failed/cancelled，仍核验消息身份、清理证明、退出码和进程所有权；启动前成功、事件与能力请求继续拒绝。真实生产路由/SQLite/子进程及恢复后的CloakBrowser联合验证：失败计入2个任务上限，业务值/非空状态及版本不变，原lease释放，允许继续时同一记录由第二Task成功执行，关闭继续时只有失败Task；同键重放无新增。专项8项通过，相关81 passed/3 skipped；新增两个早期非法消息反例及完整后端/新包验证继续中。该项仅planned→partial，251合计208partial/43planned/0verified；249有断言/2未定位，缺口241生产/19实现/8测试/24外部不变。新三平台、打包启动失败界面、系统性启动资源故障受阻组合仍保留，releaseAccepted=false。见startup-failure-follow-through.json。

来源：原始 data-and-state-rules.md DATA-CLAIM-03；生产 worker 协议；本轮真实子进程及受控启动故障测试。Ruling：只修正已确认的启动前失败分类，不把协议异常/缺失清理/进程退出异常降为普通失败，不改准入安全边界。准备夹具错误另存日志，不能作为产品反例；原产品 RED 为 interrupted != failed。
