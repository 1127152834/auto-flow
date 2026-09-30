# M0 实施记录

日期：2026-09-30；状态：in_progress。来源：持续实施授权、r2规格与计划；从文档提交547a0785建立受管worktree，分支codex/remediation-m0。

Task 1 已实现：真实SQLite领取基准、统一数值报告与必填manifest、默认排除benchmark/golden。复用现有项目/表测试工厂；合成行使用确定UUID排序，计时仅覆盖真实select_required。报告记录代码提交、工作树是否有未提交变更、硬件/运行时/场景维度；未知或脏源码报告只供观察，不比较提升。

验证：RED先因新增模块缺失失败；sourceDirty反例先失败再通过。定向12项通过；现有输入选择10项通过，默认命令同时排除11个当时已有基准用例。Ruff检查/格式通过。2000行一次本机观察：记录键141.677ms，字段164.630ms；不是收益结论，正式对照需提交后干净源码重跑及同口径多样本。原计划默认仅跑全被排除目录会退出5，使用既有输入选择测试一起运行以验证排除行为，未把无测试当通过。

范围：本片无生产实现修改、无前端契约变化；未执行全应用回归、浏览器或跨平台验收。M0仍待Task2–10；Task11历史清理不在本轮授权内。进度细节在本计划忽略目录的progress.md；提交和本记录是持久来源。

Task 2 已实现：G4无浏览器执行基准，按实际成功nodeAttempt核对每个循环体节点次数，不用计划次数冒充实际执行。空流程反例、零次输入、真实50×5节点测试通过；全部基准15项通过，Ruff通过。默认1000×5实际5000节点，本机单次0.227ms/节点、5.001事件/节点。该次源码尚有未提交改动，manifest明确不可用于提升比较。

Task 3 已实现：每条日志通过真实SqlAlchemyWorkflowRuntimeRepository.append_event独立事务提交，计时后新Session核对实际持久条数。RED2缺模块→GREEN2，累计17项通过；Ruff通过。默认1000条本机观察p50=1.238ms、p99=1.854ms；非跨平台结论，也未改SQLite配置。

Task 4 已实现：50ms心跳、100ms告警、真实5分钟样本窗口/有界缓存与只读快照；接入sidecar启动/最终关闭，不新增HTTP契约。RED缺模块、RED缺app.state后实现；单元+生命周期+既有settings_dashboard共16 passed/1依赖弃用警告（anyio BlockingPortal），Ruff全src通过，mypy547源文件通过（1条既有annotation-unchecked提示）。首次异常关闭注入在前置shutdown直接抛错，跳过其他服务清理而挂起，7项后人工终止；改为既有gather内服务完成真实清理后抛错，验证监测器仍关闭，未声称修复原先全应用异常关闭链。

Task 5 已实现：仅loopback随机端口的黄金站点、五字段、首次延迟/永久404/提交丢响应、线程安全命中与提交计数。普通CI运行3项HTTP测试通过（RED缺模块→GREEN3），Ruff通过。按规格保留表单查询参数并支持lose=1，同时兼容lose-名字；关闭站点用Event提前结束故障等待，预期客户端断线不输出服务端堆栈。真实浏览器完整链仍待Task6，不把站点测试记成G2/G3通过。

Task 6 进行中（尚未完成）：指标与完整身份覆盖反例5项通过，涵盖同一行30次失败不可算30成功行、空错误不可算原因、成功需输出核验且去重、typed key/代次身份区别、缺行/重复/未终态与零耗时拒绝。golden/conftest.py显式注册现有real_cloak_page。harness目前仅指标部分，真实HTTP/SQLite/worker编排与G2/G3尚未接入，故不标该Task或AC0-05通过。

Task 7 已实现（Task6长运行期间独立推进）：四项文本守门、按键身份防替换绕过、独立回退反例，8项通过。双引号反例RED后扩展扫描，两种引号一致；真实基线127/2008/81/3247，原80漏算DataTableDetailPage.tsx的双引号phosphor导入。指定七个错误/重试债务键保留。全量脚本首次因新工作树缺依赖/冻结reference失败；复用本机node_modules及已核对5ccb900e的reference后119项通过。没有安装新依赖或改动原目录。

Task 8 本地配置完成，远端验证未执行：checks增加守门、离线基准与报告上传；独立golden workflow支持手动/每晚触发、固定真实内核、数值/manifest/逐行证据上传。YAML实际解析及原触发规则+守门9项通过。依据30行黄金203秒实测，将夜间默认改为各101行（推算万行受控批次存在超时风险，未宣称测过万行）；不改M2B原生吞吐目标。未推送或触发远端CI，AC0-07仍待验证。

Task9文档已加入整改硬性规则、目录职责及实际观察表；表明确sourceDirty/并行测量不可作收益基线、CI未执行，未填写计划预期。结构4项通过。Task6定向汇总41 passed/3 deselected/1既有anyio警告；Ruff全后端通过、mypy547通过（既有annotation-unchecked提示）。101行G2已完成99成功/2预期失败，G3和全后端回归仍运行。

Task6真实harness已接通并完成30行验证（202.69s，2 passed/1 strict xfailed/8 deselected）：公开自动化创建后保存其自有工作流，open_page显式profile；真实TCP/SQLite/worker/内核、分页选行、单任务批次并发2、等待任务终态与清理、逐行输出/站点回执核验、manifest及rows证据。初始fixture沿用旧workflowId创建契约触发422，修正为当前API；2秒open超时发生于浏览器初始化，修正15秒仍小于20秒故障延迟。3行冒烟2通过/1预期失败；未配内核3跳过只证明选择正常。101行完整验收仍待G3完成，Task6不标全部完成。
