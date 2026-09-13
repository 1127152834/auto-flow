# 运行事件归属防护

实测外来completed/stopped能结束当前暂停，外来数据能污染结果。对六类节点/终态/数据事件检查已知workflowId，保留当前事件处理。内存和真实本地HTTP-SSE覆盖，不宣称完整runId隔离。见docs/migration/studio-frontend-completion/event-ownership-validation.md。
