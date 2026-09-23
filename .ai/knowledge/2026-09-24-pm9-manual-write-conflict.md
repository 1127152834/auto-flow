# PM9 人工新值保护与后续失败保留

2026-09-24 DATA-E2E-03人工版本/部分失败联合补证（confirmed本机源码子范围）：FX-04初始业务夹具7/3/2，真实TCP HTTP/SQLite/worker/CloakBrowser两链分别证明任务写内容7→8、状态3→4和游标8/4/2，以及人工窗口PATCH到内容8后旧字段/旧内容状态写均REVISION_CONFLICT、游标仍7/3/2且原输入不变；声明人工分支继续不吸收人工新值。两链先前createRecord均保留，后续真实缺失元素超时失败后完整记录快照不变，公开写入摘要只含成功提交，End未执行，两条lease/目录/容量回收。最终2 passed/24.56秒，相关15 passed/4.36秒，Ruff通过；首轮三操作合并grant被422拒绝，修正为各节点精确授权，未改生产。CI选择collect2/53非执行，fresh CLI401；打包UI/Sheets出站联合/新三平台仍待验。仅E2E-03 planned→partial，WRITE-05/08/09补映射；251为210partial/41planned/0verified、249有断言/2未定位，缺口241生产/19实现/8测试/24外部不变。生产仍a7059dc6，不重跑无变化全量/构建；releaseAccepted=false。见manual-write-conflict-follow-through.json。

来源：data-and-state-rules.md §7.1/7.2/FX-04/DATA-E2E-03、真实测试与runtime-evidence.json。既有WRITE-08/09已在project-runtime-smoke.mjs有真实HTTP/worker子范围，本轮补专门的人工内容变化后状态结论拒绝、声明人工分支继续和后续网页失败联合证据；不将旧证据说成从未验证。初始local UUID记录逻辑名W01，内容/状态/关联版本7/3/2为明确种子，不表示公共编辑历史或Sheets实网。任务/占用/游标/结果未伪造。生产无改动，首轮422证明逐节点grant严格契约仍有效。
