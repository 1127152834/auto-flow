# 变量追踪服务消费与竞态保护

2026-09-14，confirmed（有界切片）；F0–F6 未整体完成。

来源：冻结 WebRPA backend/app/api/workflows.py:1294、1317 及原 VariableTrackingPanel。保留 GET/DELETE /api/workflows/{workflowId}/variable-tracking 的路径和 snake_case 记录。GET 返回 tracking 与一致的 count；DELETE 成功返回非空 message。OpenAPI 模型发布后生成前端类型，共享 API 校验记录形状、操作类型、数量及清空确认，继续使用现有鉴权/连接适配。

读取失败或畸形数据保留最后确认记录并显示错误。清空期间禁止重复提交，先取消在途读取；清空失败保留记录，成功确认后才清空。组件关闭/换流程会取消请求，迟到读取或清空响应不能写入新上下文。轮询不重叠，重新打开即读取；清空活跃 Mock 运行后仍可追加新变量变化。

浏览器实测发现对象搜索使用 String(object) 导致命中失败，改为搜索 JSON 内容；筛选零匹配单独提示，不再声称没有运行记录。更新前值为 null 也明确展示。

专项测试：16 个面板/读取契约用例，另加内存/HTTP 各 1 个活跃运行清空后继续记录用例；与现有脚本协议和消费合计 44 项通过。后端 7 项合同测试通过。Ruff 初次发现测试 dict 写法，修正后通过；未删除用例或放宽断言。全量前端152文件1821项通过；TypeScript、ESLint、renderer/main/preload构建、21脚本、OpenAPI、Ruff、mypy通过，日志见证据目录。

尚未闭合：此兼容端点仍按 workflowId 返回完整记录，没有独立 runId/分页/服务端筛选。导出仍是已加载记录 JSON，不能宣称完成大规模诊断及固定截止序号导出。Mock 记录仅驻留内存；未验收真实自动化后端或正式 Electron/其他平台。
