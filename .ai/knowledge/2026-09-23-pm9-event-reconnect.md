# PM9 人工检查点事件补读

日期：2026-09-23。状态：confirmed（定向证据）；完整回归与平台结果以 verification.json 为准。

2026-09-23 XE-C07 最新补证（supersedes 此前 243/8 统计）：真实 TCP/worker 人工等待场景发现 checkpoint 未纳入公开事件投影，导致 JSON/SSE 补读 409；已补最小身份/版本契约及生成类型，内部续跑内容不公开。修复后真实断开/继续/缺口补读、8 次唯一节点访问、3 个输出、日志分页、失败截图摘要和资源回收通过；20 项后端契约/证据与25项相关前端通过，独立审查无 P1/P2。前端 EOF 去重是独立受控测试，尚非安装包 UI 断网联合证据。台账 244 有范围断言/7 未定位、202 partial/49 planned/0 verified；完整回归/新候选 CI 见 verification.json 与 event-reconnect-follow-through.json。releaseAccepted=false。

根因：manual_runtime.wait 写入 checkpoint 后，ProjectRunEvents._public 不认识该 kind。不可跳过事件或重置游标；仅公开 manualItemId/checkpointRevision，保持同一持久序号与访问身份。未知其他 kind 仍拒绝。

验证：真实 TCP 连接断开并关闭 observer，原人工等待 Run 继续后失败；补读无重跑，产物通过 SHA256 与字节数核验。前端 mock stream 的 EOF/重复 checkpoint 单测证明游标去重，但不能声称完整 renderer 网络验收。

来源：tests/integration/test_project_batch_real_cloakbrowser.py::test_real_project_batch_http[manual-evidence-reconnect]、tests/contract/test_project_run_events.py、renderer/domains/project-runs/events.test.ts；精确结果见 docs/project-management/implementation/pm9/event-reconnect-follow-through.json。

2026-09-23 XE-A19 共享核心补证（confirmed）：复用现有真实浏览器持久运行场景，SQL 核验零 Project/仅一 Run；仅 browser 能力准备项目 createRecord 文档被明确拒绝，原文档不变且随后可编辑保存，不隐式建项目。1 passed/3 deselected（11.65 秒）。仅 core/document/worker 子范围由 planned 改 partial；Studio 窗口提示/编辑体验、HTTP 联合和打包验收未完成，新断言不在已启动的14df矩阵中。最新 245 有范围断言/6 未定位、203 partial/48 planned/0 verified；先前计数为历史。
