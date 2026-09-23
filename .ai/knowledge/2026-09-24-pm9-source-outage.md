# PM9 来源断网与拉取事实

日期：2026-09-24。状态：confirmed（下述定向范围）；完整回归和当前原生候选按专项 JSON 更新。

依据：DATA-CLAIM-09、生产 SheetsSyncService/SqlAlchemyProjectSync/resolve_record_lease、真实 HTTP/SQLite/worker/浏览器断言。范围为已批准规则的有界修复，不增加 TTL、第二执行器或跨进程恢复。

1. 先完整拉取，Google transport 持续断网，失败拉取保留本地数据与原身份核验证明；真实 worker 仍冻结原记录/内容版本，打开浏览器，经人工继续后保存本地新值并保留 pending 推送意图。领取/执行不发送来源请求。
2. 在线完整扫描发现重复身份后，将证明标为无效。再次断网/拉取失败不恢复信任；新批次配置错误，零 Task/无新增浏览器请求/无活动 lease，本地修改保留。
3. 定向 HTTP 测试先因缺少 lastPulledAt 失败。补实现后揭示页面原先从只含出站变化的 sync-operations 找 pull，接口不会返回该项。复用已有 kind=pull 查询，从同步状态提供 latestPull；成功来源时间从当前 bindingEpoch 的 confirmed pull 聚合，推送、失败尝试和旧代次不冒充来源新鲜度。
4. 前端组件测试先因缺少成功来源时间失败，改后同时展示成功时间与持久失败提示；出站队列失败不阻断拉取卡。远端原始诊断不进入页面，不自动重发。

执行切片：后端契约/查询 → 生成客户端 → 拉取卡 → HTTP 与真实 worker/组件测试 → 必要完整回归/构建 → 同分支提交、推送、草稿 PR。当前 CI35895754111@25bb8ab2不包含此生产修复，保持运行；后续稳定候选验证不借用它的成功结论。

未覆盖：完整缓存信任组合、当前 PM9 打包 Google 联合 UI、Windows/Intel 同新增场景、真实授权/OAuth/签名/物理验收。249有定位断言/2未定位、206partial/45planned/0verified未升级。P/L/M/FR/AD/W等未批准附录不实现；releaseAccepted=false。

验证进展：新 worker/HTTP最终2 passed（13.00s），组件12，全前端5474/409（246.92s），102脚本、4映射/251引用、Ruff/mypy408/typecheck/lint/OpenAPI、前后端构建与ARM打包通过。新包契约检查及完整桌面22截图通过，但不等于打包Google联合UI。首轮后端3483 passed/79 skipped/4 failed（1072.44s）；两项kernel入口5秒、一项SSE关闭3秒、一项浏览器退出回收2秒。原时限定向6 passed（9.84s），保留失败，资源压力仅假设；未依据假设改启动代码或延长时限。相同源码的串行完整回归进行中，当前任务不再叠加前端/构建/打包负载。详见source-outage-follow-through.json。

已提交生产切片51e8991e198f782030b678e8decce9a424decaf5；后续证据提交只记录该源码。原25bb8ab2三平台继续，不能覆盖51e8991e；新矩阵等待串行本机回归和现有矩阵收口。

串行完整复验终态：3487 passed/79 skipped/2 warnings，836.98秒，生产51e8991e。首轮四项失败及日志保留，未声明其时序原因已修复；未延长任何时限。此前已完成的前端/构建/打包结果不重复运行。稍后新增反向写测试不在此次收集快照内，单独验收并纳入下一次CI选择。
