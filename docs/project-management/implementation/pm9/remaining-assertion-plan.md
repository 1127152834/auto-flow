# PM9 剩余断言与能力补齐计划

日期：2026-09-21。状态：confirmed（现状和已有验证）；新增能力端口的实施设计为 proposed。来源：原始设计、coverage.json、本轮生产候选及本轮直接断言复核。

当前 251 条中 220 条有明确范围的断言，31 条尚无已定位断言；188 partially_verified / 63 planned / 0 verified。这个数量不衡量完成率，任一条的未闭合子条件继续保留。历史 73 条失效预定路径仍保留为原意，实际映射另列，未创建空测试文件冒充交付。

## 本轮已经执行的补证

- DATA-STATE-02：两个已有组件用例分别验证空状态目录的新增入口和 null/失效状态的区分，完整前端 5459 项已覆盖。
- DATA-SCHEMA-09：已有真实并发业务脚本验证 T2 等待人工时 T1 完成兼容加列，T2 保留旧契约后继续写入；不包含新字段写回、异型冲突和删除依赖的所有条件。
- DATA-CLAIM-17：新增无输入、仅可选、有必要输入三个直接规则分支，错误明确归于 maxTasks。
- DATA-SH-06：新增 HTTP/SQLite 与受控网络传输测试，远端普通值变化后本地值、身份、内容/状态版本不变。
- DATA-SH-08：新增远端排序插行后的实际出站重新定位，A/B 分别写回正确行，新增 X 不变，两个原意图 confirmed。
- 后三组同既有相关回归共 34 passed；没有改生产实现，没有把受控网络称作 Google 实网。

- DATA-SH-01 / DATA-SYNC-07：补证复现整行推送覆盖和旧响应确认新版本。已修复为原字段快照、发送登记 CAS 与原快照核验；两项目、发送中编辑和未知后新编辑三个反例 RED→GREEN；相关回归 46 passed。

- DATA-SYNC-01 / DATA-SYNC-06：放弃与发送登记在两个确定性交错下竞争；晚放弃被事务 CAS 拒绝；放弃先胜后再拉取仍保留本地覆盖值。

- DATA-SH-10 / DATA-STATE-12：新增 tombstone 普通/公式列与显式 null/非空状态 × 同步确认/失败/未知 8 个 HTTP/SQLite 场景通过。无新生产源码，不计作实网。

- DATA-XLS-03：真实重复行 XLSX 的系统身份、独立状态和本地 CRUD 不改源字节新增用例通过；相关导入与占用保护 18 passed。

- DATA-ID-03：扩展状态用例，在原行前插入新远端行后直接核对业务状态跟随稳定身份，新行 null/revision 1；6 passed。

## 先分清能力端口与测试缺口

以下不是“已有实现只差测试”，也不能靠新增白名单解决：

1. DATA-SCHEMA-01：工作流查询表/字段结构。现有管理字段列表可复用；需要明确只读命令 DTO、table/dataset/field scope 和返回稳定 fieldId/类型/来源能力/结构修订。先写无授权/错误代次拒绝和读后仍不能写的测试，再接 capability/worker 节点和配置 UI；不赋予隐式写权限。
2. DATA-SCHEMA-06（含 09 的删除子条件）：工作流 deleteField。复用管理删除影响分析；必须设计 Task 结构权限、当前/其他活动依赖和未决同步检查，并在同事务提交前重验影响版本。行 lease 不替代结构独占。先验证身份/映射/其他任务依赖阻断，再测无依赖删除与旧引用失效。
3. DATA-ID-05：Sheets system UUID 初始化仍 501。需独立初始化命令与持久原命令身份，冻结将写入的 UUID/列归属；未知响应先核验原列和原 UUID，不重生成、不占用归属不明同名列。受控 transport 故障可先验证；实网要授权测试表。
4. DATA-SCHEMA-07（含 08 远端子条件）：受控远端增列未有冻结命令。复用本地字段和原同步账本，先规定结构操作与后续值意图的依赖顺序；未确认建列不得推值，失败保留本地字段/数据。对“原列存在但响应丢失”写唯一性验证，不能改为盲重试追加。
5. DATA-SH-06 的剩余子条件：当前 `_ingest` 对普通既有值直接返回 seen，没有记录供查看的远端差异。先设计来源观察记录的键、版本和只读展示契约；观察不推进本地 contentRevision/statusRevision，也不生成出站写。
6. DATA-ID-06 / DATA-SH-13 / DATA-SH-14：实际双绑定生成不同 local leaseKey，缺 Workspace 公共身份排他及异身份列准入门禁，已复现为实现缺失。失败探针与 C1–C4 补充设计见 shared-sheets-claims-gap.json；不计入通过断言。
7. S4 Windows 已存在输出：已测持有拒绝共享目标句柄的 rename 组合不满足安全替换。保持覆盖/追加/读取拒绝；新方案须先给出同一目标身份、原子提交、冲突和取消清理可同时成立的原生实验。不能以松开句柄或字符串路径重开作为实现。

1–5 涉及新增冻结能力/持久协议，不属于已批准 S1–S5 的自动扩展；进入实现前按 AGENTS.md 完成具体 OpenAPI/命令规格、事务约束和垂直切片并确认。已有实现的补测试和缺陷修复继续按当前授权推进。S4 的安全要求已批准，具体 API 组合仍须实验成立，不能降级验收。

## 尚无直接断言的 31 条：下一步的最小场景

每项先读取原规格对应行与所列既有测试/fixture；复用 HTTP、SQLite 和现有 transport/worker。断言包含业务值、稳定身份、版本、lease/操作事实及负面副作用；文件名或测试总数不构成覆盖。纯本地规则先定向运行，真实端到端只用于对应已接通能力。

| ID | 必须增加的直接场景 | 优先复用入口 |
| --- | --- | --- |
| DATA-CLAIM-09 | 未找到把 Sheets 推送失败、本地身份可靠和领取准入一起断言的测试；需组合真实本地领取与受控网络故障 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-ID-05 | 系统 UUID 初始化响应丢失后核验同一批 UUID，且拒绝覆盖归属不明同名列 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-ID-06 | 跨项目同一物理 Sheet 行共享排他，而本地业务状态独立 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-LIFE-01 | 同账号重授权验证主体和目标、先核验未知操作再恢复 | test_project_lifecycle.py + test_project_sheets_recovery.py |
| DATA-LIFE-07 | 永久失权后隔离旧未知写，并确认旧发送进程停止后才允许目标新写 | test_project_lifecycle.py + test_project_sheets_recovery.py |
| DATA-LIFE-09 | 归档保留待推送本地数据且停止新网络写 | test_project_lifecycle.py + test_project_sheets_recovery.py |
| DATA-SCHEMA-01 | 节点返回当前稳定字段和结构修订，读取不增加写权限 | test_project_capability_fencing.py + test_project_data_catalog.py / node_writes.py |
| DATA-SCHEMA-06 | 工作流删字段不能绕过身份、关联、其他任务、未决同步依赖 | test_project_capability_fencing.py + test_project_data_catalog.py / node_writes.py |
| DATA-SCHEMA-07 | 远端新增列响应未知核验原列，字段数据保留且不重复加列 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-SCHEMA-08 | 兼容加列后旧 Patch 仍定位原字段，删本地字段不删远端列 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-SH-02 | 两项目重叠写的历史确认与最终值可解释 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-SH-03 | 同业务键并发新增云端只保留一行 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-SH-13 | P/Q 任务共享物理 lease，释放后按 Q 自己状态领取 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-SH-14 | 未证明共享身份对应时保存第二绑定但阻止相关领取 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-STATE-08 | 格式错误记录仍可人工设状态，占用或未知则明确阻断 | test_project_capability_fencing.py + test_project_data_catalog.py / node_writes.py |
| DATA-STATE-10 | 创建后设置状态失败保留 null 新记录 | test_project_capability_fencing.py + test_project_data_catalog.py / node_writes.py |
| DATA-SYNC-08 | 部分包确认后下一包失败，后续唤醒不丢新变化 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-SYNC-09 | 推送失败仍能拉取且不阻断不相关本地运行 | tests/fixtures/sheets.py + test_project_sheets_sync.py / recovery.py |
| DATA-TABLE-08 | 系统状态不能被字段节点改型/删除/映射，业务 status 字段可共存 | test_project_capability_fencing.py + test_project_data_catalog.py / node_writes.py |
| DATA-WRITE-12 | 两个任务反向请求对方记录时不永久等待或半组写 | test_project_run_data_start.py + test_project_data_scheduler.py |
| DATA-WRITE-13 | 真实循环前两行成功第三行失败，前两行效果与队列保留 | test_project_capability_fencing.py + test_project_data_catalog.py / node_writes.py |
| FLOW-A01 | 两次真实参数任务的变量隔离 | test_project_batch_real_cloakbrowser.py + project-runtime-smoke.mjs |
| FLOW-A05 | 可选输入从有到无不读到上一任务记录 | test_project_run_data_start.py + test_project_data_scheduler.py |
| FLOW-A10 | 结果列存在但无项目写节点时表无变化 | test_project_batch_real_cloakbrowser.py + project-runtime-smoke.mjs |
| XE-A01 | 参数网页真实读取、无 lease、资源回收的同一场景联合断言 | test_project_batch_real_cloakbrowser.py + project-runtime-smoke.mjs |
| XE-A17 | 活动 Run/已接受保存/未知 Sheets 推送同时归档的收尾 | test_project_lifecycle.py + test_project_sheets_recovery.py |
| XE-A19 | 无 Project 的 Studio 通用运行与项目写回文档明确缺能力 | test_project_batch_real_cloakbrowser.py + project-runtime-smoke.mjs |
| XE-C07 | 断线后快照/序号/attempt/产物恢复无重跑无重复追加 | test_project_batch_real_cloakbrowser.py + project-runtime-smoke.mjs |
| XE-G02 | 固定参数真实运行的幂等、取消、退出核验整组门禁 | test_project_batch_real_cloakbrowser.py + project-runtime-smoke.mjs |
| XE-G06 | 真实同步/保存/清理 blocker 与归档恢复删除/Workspace 切换闭环 | test_project_lifecycle.py + test_project_sheets_recovery.py |
| XE-G07 | 尚未将完整 Studio 窗口/平台门禁各子条件映射到单独断言；不能用项目 smoke 一个总通过替代 | electron-cdp.mjs + 当前安装包真实窗口/原生 UI |

## 验证与交付顺序

1. 每个已有能力场景单独完成断言与定向运行；失败先定位根因，禁止把失败改为 skip。新断言只升级其实际证明的 testMapping 子范围，未闭合整项状态不升级。
2. 生产 HTTP/真实 worker 用 `AUTOFLOW_TEST_CLOAKBROWSER=... uv run --directory apps/backend pytest tests/integration/test_project_batch_real_cloakbrowser.py -k <场景>`；离线 Sheets 使用现有 FakeSheetsTransport，报告明确这一边界。
3. 候选生产代码稳定后完整本机回归与默认三平台 CI；仅测试预期或证据工具修正可按源码哈希等价保留已有平台结果，平台受影响时用现有 workflow 的 pm9Platform 选择器重跑该平台完整链。不把跳过的平台视作通过。
4. 当前 PM9 打包 ProjectRun→Sheets 完整链及 OAuth 需要当前授权账号/桌面客户端/可写测试表；签名公证需要相应身份；Windows/Intel 实机与原生交互需要实际环境。历史 PM6 服务账号实网和历史 ARM 安装/Excel 子条件独立保留。
5. 同步 coverage、verification、completion-gaps 和 .ai；现有草稿 PR 提交推送，不合并发布。完整退出条件前 releaseAccepted=false。
