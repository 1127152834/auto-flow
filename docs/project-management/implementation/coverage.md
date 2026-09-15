# 项目管理里程碑覆盖表

- 日期：2026-09-15；状态：PM3 当前授权的管理范围已通过机器与真实 macOS 应用验收，原 PM3 合同整体为 partially verified，用户验收 pending。Windows 与 packaged 未执行；PM4–PM9 保持 planned。
- 依据：已确认设计 `906deda`；[里程碑正文](../../superpowers/plans/2026-09-13-project-management-milestones.md)。
- [逐条规则/测试目标映射](coverage.json)包含48项功能、178条验收场景、18项执行契约和7项能力门槛。
- “首次可用”只代表当阶段已接通的真实子范围；“完整验收”覆盖该条全部约束。PM9对所有功能做平台与真实应用回归。

## 功能逐项映射

| 功能ID | 功能 | 首次可用 | 完整验收 |
|---|---|---|---|
| PM-01 | 项目目录与最近访问 | PM1 | PM8 |
| PM-02 | 新建与编辑项目 | PM1 | PM1 |
| PM-03 | 项目上下文与六页签 | PM1 | PM7 |
| PM-04 | 归档与恢复 | PM8 | PM8 |
| PM-05 | 永久删除与残留处置 | PM8 | PM8 |
| OV-01 | 项目摘要与继续工作 | PM1 | PM7 |
| OV-02 | 当前活动与需要关注 | PM3 | PM7 |
| OV-03 | 最近活动与业务变化摘要 | PM2 | PM7 |
| AU-01 | 自动化目录及基本生命周期 | PM3 | PM8 |
| AU-02 | 基本信息页签与管理保存 | PM3 | PM4 |
| AU-03 | 输入数据页签 | PM3 | PM4 |
| AU-04 | 参数配置页签 | PM3 | PM3 |
| AU-05 | 运行设置页签 | PM3 | PM5 |
| AU-06 | 编辑工作流及返回 | PM3 | PM5 |
| AU-07 | 启动确认与启动结果 | PM3 | PM5 |
| AU-08 | 独立流程关联与删除影响（proposed 范围细化） | PM3 | PM8 |
| RUN-01 | 批次、任务与等待人工列表 | PM3 | PM7 |
| RUN-02 | 批次详情 | PM3 | PM7 |
| RUN-03 | 任务详情与节点记录 | PM3 | PM7 |
| RUN-04 | 停止与强制停止 | PM3 | PM8 |
| RUN-05 | 失联、结果不明与核对 | PM3 | PM8 |
| RUN-06 | 失败后的业务继续处理（基础目标 confirmed，快捷入口 proposed） | PM4 | PM7 |
| ST-01 | 统计范围与刷新 | PM7 | PM7 |
| ST-02 | 指标与趋势 | PM7 | PM7 |
| ST-03 | 从统计查看对应运行 | PM7 | PM7 |
| DT-01 | 数据表目录与创建 | PM2 | PM6 |
| DT-02 | 数据记录查询与显示 | PM2 | PM6 |
| DT-03 | 新增、编辑与删除记录 | PM2 | PM6 |
| DT-04 | 单条记录业务状态维护 | PM2 | PM4 |
| DT-05 | 字段与校验页签 | PM2 | PM6 |
| DT-06 | 数据状态页签 | PM2 | PM4 |
| DT-07 | Excel 来源检查、导入与重新导入 | PM2 | PM4 |
| DT-08 | Sheets 连接、绑定与来源调整 | PM6 | PM6 |
| DT-09 | 拉取、推送、核验与同步失败恢复 | PM6 | PM8 |
| DT-10 | 数据表设置与表删除 | PM2 | PM8 |
| DT-11 | 数据与自动化/运行的互查 | PM3 | PM7 |
| DT-12 | 新建空白本地表（proposed 范围） | PM2 | PM2 |
| DT-13 | 结果数据导出（proposed 范围） | PM2 | PM8 |
| DT-14 | 工作流中的表、字段与记录操作（confirmed 目标） | PM4 | PM6 |
| ENV-01 | 环境入口与分区 | PM5 | PM5 |
| ENV-02 | 运行环境列表与详情 | PM3 | PM8 |
| ENV-03 | 等待人工列表与共用处理详情 | PM5 | PM8 |
| ENV-04 | 已保存环境目录与详情 | PM5 | PM8 |
| ENV-05 | 环境来源选择与持续使用 | PM5 | PM5 |
| ENV-06 | 人工打开与维护已保存环境 | PM5 | PM8 |
| ENV-07 | 从任务保存环境与后续选择 | PM5 | PM8 |
| ENV-08 | 项目默认资源 | PM3 | PM5 |
| ENV-09 | 环境清理、删除与异常恢复 | PM3 | PM8 |

PM3的自动化输入可保存/预览，实际数据型执行在PM4开放；ENV-02/09在PM3仅覆盖参数型任务临时实例的真实状态/清理，完整环境页面在PM5开放。DT-07在PM2完成Excel闭环，PM4补足运行占用影响；DT-14在PM4完成本地节点，PM6完成Sheets结构/来源行为。DT-13在PM2导出本地表，PM6加入公式来源，PM8验收归档只读导出。

## 规则组归属

| 规则组 | 数量 | 主要实现阶段 | 完整验收阶段 |
|---|---:|---|---|
| DATA-OBJ | 2 | PM2 | PM3 |
| DATA-ID | 6 | PM2/PM6 | PM2/PM6 |
| DATA-VER | 2 | PM2 | PM4 |
| DATA-STATE | 13 | PM2/PM4/PM6 | PM2/PM4/PM5/PM6/PM7/PM8 |
| DATA-TABLE | 8 | PM2 | PM2/PM6/PM8 |
| DATA-XLS | 7 | PM2 | PM4 |
| DATA-IN | 12 | PM3 | PM4 |
| DATA-CLAIM | 17 | PM4 | PM4/PM6 |
| DATA-WRITE | 13 | PM2/PM4/PM5 | PM4/PM5/PM6/PM8 |
| DATA-SCHEMA | 9 | PM4/PM6 | PM6 |
| DATA-LINK | 6 | PM5 | PM5 |
| DATA-SH | 14 | PM6 | PM6 |
| DATA-SYNC | 10 | PM6 | PM6 |
| DATA-LIFE | 12 | PM6/PM8 | PM6/PM8 |
| DATA-E2E | 6 | PM9 | PM9 |
| FLOW-A | 16 | PM3/PM4/PM5/PM6/PM7 | PM3/PM4/PM5/PM6/PM7 |
| XE-A | 25 | PM3/PM4/PM5/PM7/PM8 | PM3/PM4/PM5/PM7/PM8 |

## 契约与能力门槛

| ID | 首次实现 | 完整验收 |
|---|---|---|
| XE-C01 | PM3 | PM3 |
| XE-C02 | PM3 | PM4 |
| XE-C03 | PM3 | PM5 |
| XE-C04 | PM4 | PM6 |
| XE-C05 | PM3 | PM4 |
| XE-C06 | PM3 | PM8 |
| XE-C07 | PM3 | PM7 |
| XE-C08 | PM4 | PM4 |
| XE-C09 | PM4 | PM6 |
| XE-C10 | PM5 | PM5 |
| XE-C11 | PM3 | PM5 |
| XE-C12 | PM5 | PM5 |
| XE-C13 | PM5 | PM5 |
| XE-C14 | PM5 | PM5 |
| XE-C15 | PM5 | PM8 |
| XE-C16 | PM3 | PM8 |
| XE-C17 | PM3 | PM8 |
| XE-C18 | PM5 | PM5 |
| XE-G01 | PM3 | PM3 |
| XE-G02 | PM3 | PM3 |
| XE-G03 | PM6 | PM6 |
| XE-G04 | PM5 | PM5 |
| XE-G05 | PM5 | PM5 |
| XE-G06 | PM8 | PM8 |
| XE-G07 | PM9 | PM9 |

XE-G03包含全部数据来源、项目写入及关联契约，因此完整门槛在PM6关闭；PM4的本地数据型闭环不被误称为全部来源已验收。XE-G07检查项目实际消费的双窗口/平台能力；完整Studio其他核心能力仍由其独立计划验收。

## 证据填写规则

- 实施者在 `execution-ledger.md` 记录提交、OS/架构、测试命令/退出码、真实页面步骤、Task/Run/Operation与脱敏结果；本文件映射和JSON的planned状态不自动转绿。
- 自动测试、模拟Provider、真实浏览器、真实Sheets及安装包证据分别标记，不能互相抵扣。
- 一条ID涉及多个阶段，早期已通过的局部测试须保留；完整验收阶段补来源/竞争/恢复场景，PM9做最终回归。
- 增加或修改规则必须同步规格、映射和测试；删除范围需有用户依据，不能通过删ID制造100%覆盖。

## PM0 补充：执行责任与开始条件

逐条映射现在包含primary_package、owner、planned_test_file、acceptance_methods、dependencies及completion_packages；[执行账本](execution-ledger.md)定义责任角色和30包的文件/集成边界。第一次出现的能力、完整阶段验收、PM9发行回归保持独立。

PM3参数型链可在PM2完成前开始，完整退出依赖仍包括PM2；PM7查询可在PM4后开始，完整退出等待PM5/PM6。所有future测试目标是计划路径，不能当作现存测试；PM0静态检查结果不填入业务evidence。

[合成样例](fixtures.json)提供7组固定数据、13个分支场景及3条代表流程。样例只做结构/引用核验；每条场景ID的业务含义经过规格审查，实际行为仍由对应阶段测试证明。

## PM1 交付更新

| 功能 | 实际验证范围 | 当前状态 | 剩余边界 |
|---|---|---|---|
| PM-01 | 创建后的目录、搜索/排序/分页、打开与最近访问、返回位置 | partially_verified | 归档及删除流程 PM8 |
| PM-02 | 管理表单、真实命令、幂等/CAS、冲突与草稿、工作区隔离 | verified / 用户验收 pending | PM9 发行回归 |
| PM-03 | 项目上下文、六页签、非法地址与离开保护 | partially_verified | 后续业务页签 PM3–PM7 |
| OV-01 | 真实资料和最近访问 | partially_verified | 数量/运行摘要/继续工作 PM7 |

证据：[PM1机器核验](pm1-verification.json)、[本机Electron](../../migration/project-management-pm1-qa/built-html.json)。PM1-A/B/C交付完成，不改变其他44项功能、178项未来规则及18契约/7门槛的证据为空。PM0历史plan-verification.json与FX样例保持原内容。

## PM2 目录读取子范围证据（2026-09-13）

DT-01/02/10/12登记部分自动与macOS arm64实际应用证据，详见pm2-directory-deletions-verification.json及coverage.json各项scope；不提升完整验收。48功能、178场景、18执行契约、7能力门槛编号不变。写UI、批状态、文件/Excel、Sheets及后续运行仍保持未验收。

## PM2 修订交付检查点（2026-09-13）

- 后台提交 `32e424e`：批量状态、受控检查、隐藏分段导入/替换、快照导出与核验；[后台核验](pm2-backend-verification.json)记录759项全量测试。
- [前端核验](pm2-frontend-verification.json)：803项全量测试，目录新表导入真实Electron通过；重新导入、导出、批量状态组件与选择工具已准备，尚未接入原任务负责的详情页。
- [一万行测量](pm2-data-volume-verification.json)是后台与真实文件实测，不代表大表界面性能。
- [修订包状态](pm2-revised-delivery.json)保持inProgress，静态核验11项首次可用功能及34项首次实施验收编号；不改变完整规格的48/178/18/7编号集合。
- 原编辑任务仍在进行；六个原WIP文件哈希与起点一致，未由本任务提交。全量lint仅在原任务测试文件的未使用参数处失败。
- [页面接入清单](pm2-page-integration-handoff.md)列出依赖、真实消费者和仍需执行的验收。当前不是PM2完整交付，未进入PM3。


## PM2 最终机器与真实应用验收（2026-09-13）

此前“进行中”“等待详情页接入”的检查点为历史过程记录，现由本节取代。P0–P5均为verified，PM2交付状态passed，用户验收仍pending。[最终机器报告](pm2-verification.json)汇总：pytest 760项、Vitest 833项/112文件、ruff、mypy 195文件、desktop类型检查/lint/build、OpenAPI、脚本21项及结构3项全部通过。

真实macOS arm64证据按实际范围登记：

- [本地数据详情流程](../../migration/project-data-directory-qa/run-3HOD1Y/result.json)：表、字段、状态、记录命令，冲突/丢响应恢复、设置、重启、工作区隔离及200%缩放。
- [Excel与批状态详情流程](../../migration/pm2-detail-qa/run-Z9O6af/result.json)：批量状态设置/清空、筛选选列导出、重复目标拒绝、显式映射重新导入、代次隔离、冷重启和真实10000行分页性能。
- [原生文件面板](../../migration/pm2-native-picker-qa/run-Lr9nj8/result.json)：真实macOS open取消、选择文件及save取消；文件发布由注入面板结果的完整流程覆盖。
- [构建HTML回归](../../migration/project-management-regression-qa/run-4K8zpg/built-html.json)：全局入口与既有模块回归。

coverage.json仅提升PM2首次实施范围。DT-12在PM2完整验收后为verified；其余需要PM4/PM6/PM7/PM8补足运行占用、Sheets公式/来源、摘要或生命周期的功能保持partially_verified。PM3–PM9场景、Windows、packaged及用户验收没有被上述结果替代。

## PM3 管理范围交付更新（2026-09-15）

本节以 [PM3 最终机器报告](pm3/verification.json) 为权威当前记录，保留前文 PM0–PM2 历史事实。用户排除了 Studio demo 联合测试；该排除不等于原 PM3 合同中的 Studio 打开/返回已经通过。

| 状态 | 条目 | 当前证据与边界 |
|---|---|---|
| verified | AU-04、FLOW-A01、XE-A01、XE-A04、XE-G02、PM3-B、PM3-C | 参数配置与参数型真实启动、原子事实、原键恢复、普通停止及强停均通过真实 Electron + FastAPI + SQLite + CloakBrowser 链。 |
| partially_verified | PM-03；AU-01/02/03/05/07/08；RUN-01–05；ENV-02/08/09；XE-A06；XE-C01/02/03/05/06/07/11/16/17；XE-G01；PM3-A | PM3 子范围可用；等待人工、项目数据型执行、持久环境、完整生命周期或 Studio 往返仍属于后续里程碑或用户排除范围。 |
| planned | OV-02、AU-06、DT-11、DATA-IN-01–12、XE-A05 以及 PM4–PM9 项目 | 没有用管理配置、参数任务或终态重启证据冒充未实现业务能力。 |

强停使用明确声明的受控 OS 进程暂停：只定位隔离 Electron 后代树中唯一、命令匹配的真实 workflow worker，记录 PID 与开始时间后暂停；UI 走普通停止、30 秒宽限和真实强停，随后确认同一进程身份退出、旧执行代次撤权、资源清理及新批次可运行。当前 HEAD 证据见 pm3/qa-runs/uuid-runs-1789458500247/result.json。

Windows、其他 CPU 架构、打包应用和用户手动测试均未执行。
