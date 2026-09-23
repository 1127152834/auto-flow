# PM9 人工检查点事件补读

日期：2026-09-23。状态：confirmed（定向证据）；完整回归与平台结果以 verification.json 为准。

2026-09-23 XE-C07 最新补证（supersedes 此前 243/8 统计）：真实 TCP/worker 人工等待场景发现 checkpoint 未纳入公开事件投影，导致 JSON/SSE 补读 409；已补最小身份/版本契约及生成类型，内部续跑内容不公开。修复后真实断开/继续/缺口补读、8 次唯一节点访问、3 个输出、日志分页、失败截图摘要和资源回收通过；20 项后端契约/证据与25项相关前端通过，独立审查无 P1/P2。前端 EOF 去重是独立受控测试，尚非安装包 UI 断网联合证据。台账 244 有范围断言/7 未定位、202 partial/49 planned/0 verified；完整回归/新候选 CI 见 verification.json 与 event-reconnect-follow-through.json。releaseAccepted=false。

根因：manual_runtime.wait 写入 checkpoint 后，ProjectRunEvents._public 不认识该 kind。不可跳过事件或重置游标；仅公开 manualItemId/checkpointRevision，保持同一持久序号与访问身份。未知其他 kind 仍拒绝。

验证：真实 TCP 连接断开并关闭 observer，原人工等待 Run 继续后失败；补读无重跑，产物通过 SHA256 与字节数核验。前端 mock stream 的 EOF/重复 checkpoint 单测证明游标去重，但不能声称完整 renderer 网络验收。

来源：tests/integration/test_project_batch_real_cloakbrowser.py::test_real_project_batch_http[manual-evidence-reconnect]、tests/contract/test_project_run_events.py、renderer/domains/project-runs/events.test.ts；精确结果见 docs/project-management/implementation/pm9/event-reconnect-follow-through.json。

2026-09-23 XE-A19 共享核心补证（confirmed）：复用现有真实浏览器持久运行场景，SQL 核验零 Project/仅一 Run；仅 browser 能力准备项目 createRecord 文档被明确拒绝，原文档不变且随后可编辑保存，不隐式建项目。1 passed/3 deselected（11.65 秒）。仅 core/document/worker 子范围由 planned 改 partial；Studio 窗口提示/编辑体验、HTTP 联合和打包验收未完成，新断言不在已启动的14df矩阵中。最新 245 有范围断言/6 未定位、203 partial/48 planned/0 verified；先前计数为历史。

2026-09-23 XE-G02 子范围复核（confirmed）：本机真实 success/manual-stop 两场景 2 passed/32 deselected（25.21 秒），分别证明有限两次参数运行/日志输出/同键重放/资源回收，以及实际人工等待后的取消和清理；独立通用核心场景证明准备内容不被后续文档编辑替换。强停、归属不明的退出核验与安装包/三平台整组门禁仍未闭合。当前 246 有范围断言/5 未定位、203 partial/48 planned/0 verified，不按数量判断完成率。

2026-09-23 本轮回归收尾（confirmed）：生产候选14dfae7c；本机后端完整3465 passed/73 skipped/2 warnings（966.88秒），前端5471通过，类型/lint/OpenAPI/Ruff/mypy407/前后端构建通过。产物sidecar首次15秒就绪超时；诊断3545ms且健康200，原15秒复测通过，但首发原因未明，不能声称修复。单次新三平台35811305102仍运行，旧c9矩阵因新增checkpoint修复取消。后续aef0f412仅测试/记录，与候选生产源码一致但其新增断言不在该矩阵。releaseAccepted=false。
