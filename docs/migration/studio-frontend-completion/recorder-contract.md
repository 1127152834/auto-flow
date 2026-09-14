# 录制补读合同（F1 局部）

日期：2026-09-13；状态：局部合同已实现并验证。冻结源的 destructive drain 行为在 AutoFlow 中被本约定替代。

- POST /recorder/start 携带稳定 sessionId；同一会话重试不清空步骤，其他活跃会话409。旧会话被新会话替代后，旧标识不能重新启动。
- 每条事件含递增 sequence；事件合并仅发生在前端审查列表，不修改服务端序号。
- GET /recorder/events?sessionId=...&afterSeq=... 非破坏读取，返回 success、sessionId、nextSeq、data（事件数组）。重复读相同游标返回相同步骤。
- POST /recorder/stop 携带 sessionId、afterSeq；返回同一会话标识及 data.events、nextSeq，成功确认后才显示已停止。失败保留录制状态和审查列表，可重试。
- 会话标识不匹配409；非法游标400。请求响应丢失可重试原标识及游标。停止响应与在途轮询交错，以 sequence 去重，旧会话不得更新新会话。
- 暂限现有单会话内存夹具；服务重启恢复、容量上限、持久录制、完整宿主离开矩阵在F4/F5另行验收，不能把此合同补读测试当真实浏览器采集。

用例：REC-PROTO-001重复补读；002停止尾部/重试；003错会话/非法游标；004启动响应重试；REC-UI-001停止失败保留；002迟到轮询不重复；003新会话拒绝旧响应。实现后补实际结果。

## 实际验证

2026-09-13：完整前端 91 个测试文件、1,107 个用例通过；typecheck、lint、renderer/main/preload 构建通过。日志见 f1-recorder-tests.log、f1-recorder-build.log。

- transport-parity.test.ts：同一合同在内存和真实本地 HTTP 下验证重复读取、启动重试、停止尾部、错会话及非法游标。
- recorder-recovery.test.tsx：停止失败不关闭、迟到轮询不重复、跨框架/目标不误合并、生成一次撤销且保留日志。
- editor-roundtrip.test.ts：React Flow 自动测量/选择不写历史、不污染未保存状态，第一步可撤销，分叉后不能重做覆盖。
- 浏览器 UI + Mock 手动验收（localhost:5175/studio.html，独立来源存储）：录制三条步骤，离线停止明确报错且保留录制中状态；重连停止无重复；生成节点后 Cmd+Z 回到零节点、Cmd+Shift+Z 恢复；以“F1 录制恢复验收”保存成功。此证据不是 Electron 端到端，也不代表真实浏览器采集。

发现并修复：冻结源码在生成时调用 loadWorkflow，清空历史和日志；现改为一次编辑事务。React Flow 自动测量曾再次插入历史，破坏重做；改为仅显式尺寸编辑进入历史。拖动手势及全局变量历史仍需进一步逐项验收。

## 2026-09-14：确认游标校验

前端按完整批次验证：sequence 为正安全整数、连续且不重复，动作类型已登记；新事件必须从当前确认位置的下一序号开始；nextSeq 与批次尾部一致，空批次不得推进游标。允许重送已确认前缀，原始事件序号不受审查步骤合并影响。任何错误整批不应用，停止尾批次非法时仍可按原游标重试，不显示停止成功。

新增12项组件用例；初始17项中10失败，修复并增加原始输入合并用例后组件18项及内存/实际本地HTTP协议20项共38项通过。TypeScript、ESLint和renderer/main/preload构建通过。证据 evidence/f4-recorder-cursor。当前切片没有新增真实浏览器采集或正式Electron测试，不代表F4完成。全局会话所有权、连接切换、容量及宿主清理继续待验收。
