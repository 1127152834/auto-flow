# PM9 D1 输入校验与补证

- 日期：2026-09-23
- 状态：confirmed（本机定向与真实 worker）；完整回归/新三平台以 verification.json 为准
- 来源：test_project_sheets_claims.py、test_project_sheets_real_cloakbrowser.py、test_project_capability_fencing.py、test_project_table_schema_capability.py 的实际断言与运行。

D1 专门真实场景暴露生产缺陷：来源 number 字段保留 `not-a-number` 后，将其声明为输入仍会创建第二个 Task 并启动浏览器。原领取只校验身份/引用，没有按声明字段验证候选值。两个快速用例（类型错误、必填缺失）同样 RED：返回 ready 而非 configurationError。

修复复用 validation_issues，仅检查选中记录声明的字段，在准备选择与提交前重验两条入口共享。未使用坏字段、未选中坏记录不阻断有效任务；错误包含字段 ID/规则，不回显原值。SelectedInput 的嵌套 DateScalar 是冻结 Mapping，复用 _mutable 恢复校验输入；已有日期分页回归捕获并验证这一边界。

本机真实 HTTP/SQLite/worker/CloakBrowser 145 用例通过：有效标题写入成功、坏金额原值和诊断保留、历史输入快照不变；随后声明坏金额的批次失败，taskCount=0，不新增 Task/lease，不再次访问页面，已成功写入保留。Google transport 与凭据为 fixture，不代表 Google 实网、打包或跨平台。整个共享 Sheets 真实 worker 文件 4 passed，包含原 resume/stop/loss 三类交接。

DATA-TABLE-08 前一记录的“映射拒绝”范围过宽，相关叙述由本节 supersede：原映射只命中通用未开放入口，改型/删除只命中权限拒绝。现为权限充分后 FIELD_NOT_FOUND；真实 Sheets 绑定拒绝状态目录 UUID 和 literal statusId，业务 status 字段正常读取，拒绝不改记录/绑定/操作/lease/远端。正式状态写只推进状态版本。

DATA-WRITE-12 新增两任务各持一条动态 lease、并发反向单记录写的直接集成证据：双方返回 LEASE_BUSY，原写入、版本、游标、输入快照和 lease 所有权不变。Task 激活为 fixture；不宣称真实 worker 重试或多记录组原子性。

当前台账 251 条，237 有范围断言/14 未定位，198 partial/53 planned/0 verified。新增生产修复不能沿用 ae347de9 或 1eeeafff 的 CI 作为当前验证；既有推送矩阵 35704062667 全成功，PR 矩阵 35704068537 的 Intel DMG 因 hdiutil Resource busy 失败，其余两平台成功。两次运行分别保留。releaseAccepted=false。

后续本地补证：生产修复 c2d91c5d 已推送，唯一新三平台矩阵 35806853292 运行中。新增 data-loop-partial 真实 worker 场景 1 passed/29 deselected（12.56s）：第二张本地表前两行成功、第三行被规则拒绝，前两行和操作保留、两个 lease 释放、无 End、后续任务取消。只将 DATA-WRITE-13 从 planned 改为 partial，当前 238 有断言/13 未定位、199 partial/52 planned/0 verified；无 Sheets 队列/UI/平台证明。该测试晚于 CI 候选，不能称已在该矩阵运行。独立只读审查确认范围，无重要问题。PyInstaller 本机构建通过。

随后 parameter-isolation 真实场景通过（1 passed/30 deselected，28.56s）：同一有限批次两个参数任务的 taskLocal 初值都为既有 set_variable 语义的 0，前次写入不泄漏；同名输出列存在但无项目写节点，原记录完整 DTO 不变，两个真实网页输出可分别查询，无 DataLease。FLOW-A01 补断言，FLOW-A10 升为 partial。最新 240 有范围断言/11 未定位，200 partial/51 planned/0 verified。一次早期运行在 7 个节点均完成后出现 worker 退出 TimeoutError；后续诊断正常退出 0、最终场景通过，根因尚未确认，不放宽退出超时。测试晚于 c2d91c5d，未包含在其 CI 矩阵。

两项新增场景在完整回归结束后启用 worker diagnostics 联合复验：2 passed / 29 deselected，24.20 秒。此次未复现退出超时；原超时根因仍未确认，不标已修复。

FLOW-A05 追加本机源码真实 worker 证据：同一自动化两个独立批次各一任务，可选记录存在→HTTP 改值后 no_match。第二次快照和两次 capability 读取皆为空引用/空值，零 lease，第一次快照不变且浏览器资源回收。1 passed/31 deselected，37.63 秒；独立复审无 P1/P2。范围不包含同批次、变量表达式读取、打包 UI 或该场景三平台。机器统计 241 有断言/10 未定位、201 partial/50 planned/0 verified。

XE-A01 参数无数据联合场景新增真实 worker 证据：parameter-single 1 passed/32 deselected，38.06 秒；无表、first 网页读回、重放仍唯一 Batch/Task/Run、零 lease、资源清理。现有 partial 状态不升级 verified。最新机器统计 242 有断言/9 未定位、201 partial/50 planned/0 verified；不计入 c2d91c5d CI。
