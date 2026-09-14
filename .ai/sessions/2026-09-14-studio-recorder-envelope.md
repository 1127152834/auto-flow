# 录制会话与投递信封合同

2026-09-14，confirmed（局部F1）。

新增StudioRecorderStartRequest、ReadRequest、Started、Batch、Stopped及事件/尾部嵌套schema。会话标识必需且包含非空白字符，确认游标为0至最大JS安全整数，事件序号从1开始；事件类型限定现有10种。批次相邻序号连续且尾部等于nextSeq。空批次、首个新事件仍须在前端结合当前游标校验；不在无请求上下文的DTO里猜测。

前端start/stop/events使用生成类型，拒绝非法会话/游标后不发送请求。已保留动作专属扩展字段，不宣称这些参数已完成逐字段验证；status尚未冻结。现有Mock兼容入口仍接受无sessionId的旧直接调用，正式消费者已强制标识，后端接入以必需标识的交接合同为准。此处没有新增真实自动化路由。

后端19项通过，前端新增9项先全部失败，修复后相关4文件51项通过；TypeScript、ESLint、Ruff、mypy（202源文件）、OpenAPI一致性、49脚本及构建通过。证据evidence/f1-recorder-envelope。上一批全量264文件3036项在本批新增合同前完成，本批没有重新执行全量，不合并虚报新总数。
