# PM9 assertion mapping review

日期：2026-09-21。状态：confirmed（映射审查），完整产品验收仍未完成。来源：原始设计各需求编号、现有测试函数断言及本轮运行记录。

251 条全部保留原 id、来源和预定文件；新增 `testMapping` 是当前审查结果。初审 200 条定位到实际测试断言，其余 51 条明确记录未定位到直接场景测试。部分有测试的条目也有未覆盖条件。73 条失效预定路径全部补了映射或缺测说明，没有创建空测试文件来满足路径检查。

`checks.scope` 只说明该函数实际断言的子集；`gaps` 说明未证明的条件。`test_missing` 表示本次未定位到完整场景的直接断言，不证明实现不存在。`implementation_missing` 必须有代码边界支持；`production_evidence_missing` 表示替身/领域/契约断言不能替代真实生产链；`external_acceptance_pending` 需要外部授权或机器。一个需求可同时包含多类缺口。

原有 22 条 verified 也存在未闭合条件，已逐项按记录中的缺口退回 partially_verified，原状态保存在 `statusBeforeReview`。不把历史 PM1/PM2 等阶段报告删除，也不把它们当作整个 PM9 的重新验收。未批量提升任何状态。

静态检查：`node --test scripts/verify-pm9-coverage.test.mjs`、`node scripts/verify-pm9-coverage.mjs`。检查 251 个唯一 id、实际文件/函数、分类与缺口；拒绝不存在函数、非法分类、带缺口的 verified。它不理解业务断言，不能据其通过宣称规格已实现。

补齐真实场景后，203 条具有断言映射，48 条仍未定位直接场景断言；当前 186 partial / 65 planned / 0 verified。新增场景只将直接匹配的 planned 改为 partial，未清除尚未覆盖的原始业务组合。

本轮真实场景复用 `scripts/project-runtime-smoke.mjs`，源码与打包应用调用同一入口。交付中保存对应原始 JSON；只有报告明确出现且断言通过的场景才可增加生产证据。真实 worker 的响应丢失/人工竞争使用 `test_project_batch_real_cloakbrowser.py`，明确记录故障注入边界；不将受控时钟称为实时时序性能测试。

服务账号 Sheets 与系统凭据已有 PM6 历史实网证据；本轮映射中的当前生产证据缺口不撤销该事实。OAuth、当前 PM9 打包全链、签名及实机专项仍单独待验收。`releaseAccepted=false`。
