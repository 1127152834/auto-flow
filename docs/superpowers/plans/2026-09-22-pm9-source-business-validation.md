# PM9 D1 来源业务格式错误保留

日期：2026-09-22。状态：confirmed。用户已批准 D1 按切片实施。
Spec: docs/superpowers/specs/2026-09-22-pm9-source-business-validation.md
Base: 685504ee3b58dff3993f8253c2587f8bb48a24f2。仅现有 PM9 worktree/branch；不合并/发布。C/R 现有矩阵继续，D1 不借其证据。

## Global Constraints

复用 validate_value、validate_record_scalar、现有记录/来源操作与 React 组件；无新执行器/数据库错误账本。身份、unsafe Scalar、人工写入、执行契约严格；字段诊断按权限投影，原操作快照冻结。releaseAccepted=false。

## Task 1: 当前记录诊断和 DTO

Files: domain/project_data/records.py; database/project_data_records.py; database/project_capabilities.py; http/project_data_record_schemas.py; 生成 OpenAPI/客户端；test_project_data_records.py 与 test_project_capability_fencing.py。
Interfaces: 提供 validationIssues 当前字段问题列表；Task 2 保留 raw 值后调用同一快照；Task 3 读取同一 DTO。
1. 写诊断缺失/类型错误/不含原值/修复清除与未授权字段隔离测试，运行观察 RED（缺少 validationIssues）。
2. 增加最小共享诊断函数，当前快照派生、工作流投影过滤，DTO 默认空列表；已保存原操作返回不重算历史。
3. 生成客户端，运行 records/capability/read/query 回归和 Ruff/mypy/OpenAPI，Expected: pass。相关旧快照测试仅在契约新增空字段处调整。
4. 更新证据/.ai 并提交。Gate: uv run --directory apps/backend pytest tests/integration/test_project_data_records.py tests/integration/test_project_capability_fencing.py -q。

## Task 2: Sheets 与 Excel 来源物化

Files: domain/project_data/records.py; database/project_data_records.py; application/project_data/excel_import.py; test_project_sheets_sync.py; test_pm2_excel_imports.py。
Interfaces: 使用 Task 1 DTO；保留来源安全 Scalar，身份继续 strict，手工写不变。
1. 实际 HTTP Sheets 与真实 XLSX 两行一好一坏、公式刷新、必需缺失、身份错误、unsafe Scalar、原键恢复测试 RED。
2. 复用共享源值验证区分安全结构和普通业务格式，来源 create/update 与 Excel 使用同一判定，所有人工路径 strict。
3. 跑来源/Excel/schema/status/capability 与 wire 检查，Expected: pass，无重复记录/云写/错误字段渗透。
4. 记录并提交。Gate: uv run --directory apps/backend pytest tests/integration/test_project_sheets_sync.py tests/contract/test_pm2_excel_imports.py tests/integration/test_project_data_records.py -q。

## Task 3: 界面与执行准入

Files: RecordFieldsView.tsx/test.tsx; RecordDetailPage.test.tsx; 现有真实 worker 测试；必要共享输入校验实现。
Interfaces: 展示 validationIssues 和原值；任务只检其冻结必需字段/授权，不扩大 Studio。
1. 原值和安全说明并列、读取错误区分、修复后清除、状态入口仍可用组件测试 RED。
2. 最小 UI 变更；实际 worker 未使用坏值继续执行，使用坏值阻断无半 Task/lease。定位真实缺陷才改共享准入。
3. 组件和真实 worker 针对性回归、类型/lint/build，Expected: pass。记录 C/R 原生运行结果为独立候选。
4. 记录并提交。Gate: 相关两组件文件和选定实际 worker 场景，命令/结果保存报告。

## Task 4: D1 候选验证和交付

1. 235 有断言/16 未定位的当前台账逐项追加证据，只关闭已证条件。保留外部实网/签名/物理环境，禁止批量 verified。
2. 完整后端、前端、Ruff/mypy/win32、OpenAPI/scripts/build；候选稳定推送后单次三平台。Expected: 所有可执行门禁通过；不推断实网验收。
3. D1 从 Base 起做一次全切片独立 review；C/R 整批 review 已完成，不重复历史审查。Important/Critical 一次修复 RED→GREEN，全部裁定记录。
4. 收集 commit-scoped 六报告/worker/负载/安装包证据，更新 PR 与 .ai；不得合并或发布。

## Review Focus

检查 source origin 能否被非可信 RPC/HTTP伪造；身份业务格式、未知字段、unsafe Scalar 与普通格式区别；只读投影诊断泄露；原操作历史/current-schema 混淆；Excel 隐藏代次原子发布；formula 错误与读取失败分离；Task 按冻结必要字段校验与未使用字段隔离；当前 UI 和旧快照兼容。
