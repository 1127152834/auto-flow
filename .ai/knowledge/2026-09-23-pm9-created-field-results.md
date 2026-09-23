# PM9 新字段结果后续写入核对

日期：2026-09-23。状态：confirmed（缺口和已运行子范围）；FR1–FR3 修复合同为 proposed。
来源：当前 c16532d7 ARM CI DMG 内 sidecar，SHA256 99a262d7c15c95276ed7012a6ae21fb220fc4ddaade735a1a66bcba91cc3fcaa；隔离 HTTP/实际 worker/公开 Chromium 145；报告 `docs/project-management/implementation/pm9/created-field-results-follow-through.json`。

两条独立路径都失败：创建后沿旧字段 grant 写新 fieldId 得 CAPABILITY_SCOPE_DENIED；预先把尚不存在的 fieldId 加进 grant 则批次409 CAPABILITY_FACTS_INCOMPLETE。前者此前 ensure/create/query/旧字段update均成功。它们证明实现缺失，不能归为缺少 Google 授权；失败证据及相对543194dd的复现补丁已保存。两个进程/临时工作区清理均通过。最初 /tmp 脚本因 macOS /private/tmp 主模块路径不匹配未执行，该空调用无证据价值；后续按真实路径运行才产生这两份失败报告。

新增正向打包断言：同键同定义 ensure 返回原 fieldId，created=false且结构版本不变；另一真实任务同键异型明确失败，所有字段和值不变；T2 一直保持原 waiting Run、随后旧字段写入成功。原共享人员链和两条并行浏览器/记录链也通过，脚本测试101项通过。没有证明新字段写回。

原规格明确要求新增返回字段后续写入，但现有 frozen tableGrant 只接受已存在 UUID；modifier 的同Task创建证据没有用于记录写。修复不能直接把整个Task的字段权限扩成通配符，尤其须保留子流程声明边界。FR1–FR3提案扩展显式 fieldResultSources，沿现有 ProjectOperation 和 nodeVisit 事实校验；没有新增执行器/数据库表。具体授权和配置契约待确认，不视为已获L1/M1等其他附录批准。

DATA-SCHEMA-02/09、FLOW-A14新增implementation_missing分类，状态未上调；production source仍c16532d7，releaseAccepted=false。
