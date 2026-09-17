# PM4-B 显式项目数据能力核验

日期：2026-09-16

分支：`codex/project-management-pm4`

结论：**管理侧通过，真实执行核心接入待验收**
置信度：管理端、HTTP、SQLite、能力事务和界面投影为高；真实生产执行核心为未验证。

## 可操作闭环

隔离 Electron 中通过界面创建项目、人员/邮箱/账号三张表、字段、状态、记录和自动化，配置两个必要输入并启动一个任务。隔离测试执行器随后通过真实项目数据能力完成：查询和读取记录、清空并设置邮箱状态、新增/编辑/删除账号记录、新增/确保/安全修改字段。任务页显示不可变原始输入、稳定记录/字段引用和全部已提交数据事实。

本轮权威证据：

- `qa-runs/v1-tcCGGq/result.json`
- `qa-runs/v1-tcCGGq/05a-task-original-inputs.png`
- `qa-runs/v1-tcCGGq/05b-task-data-operation-tail.png`
- 运行边界：`executor=fake`、`browser=notExecuted`、`studio=notExecuted`
- 视口：1440×1024，DPR 1，macOS arm64

最终事实为：人员记录保持不变；邮箱最终为“已使用”；账号表只保留一条记录且网页结果更新为 `PM4-B-UPDATED`；一次性账号被显式删除；字段新增、ensure 和安全修改均返回稳定字段引用。

## 数据保护核验

| 规则 | 实际证据 |
|---|---|
| 原始输入不可变 | 任务详情继续显示创建 Task 时冻结的两项输入；后续写入只出现在数据操作事实中 |
| Task 自写版本推进 | 查询取得的记录由动态 lease 保护；本 Task 写入后游标推进，随后写入使用新版本 |
| 人工新值优先 | Task 写入后人工再次修改，旧 Task 版本写入返回 `REVISION_CONFLICT` |
| 查询不自动取得写权 | 查询证据只允许在声明 scope 内申请动态 lease；失败不遗留 lease、Operation 或 DataChange |
| 幂等恢复 | 同 operationId、同载荷返回既有结果；异载荷冲突；创建 ACK 丢失后账号不重复新增 |
| 完整身份 | record/field 权限匹配项目、表、数据代次和带类型的键或字段身份；跨表同 fieldId 不越权 |
| 删除保护 | workflow 删除在同一事务执行引用检查；阻断时记录、lease、游标、Operation 和 DataChange 均不提交 |
| 字段回填预算 | add/ensure 在提交前限制最多 1,000 行及完整写后 JSON 合计 4 MiB，超限整笔拒绝 |
| 执行代次 | 旧 executionGeneration 的读写和终态提交均被拒绝，未知结果下 lease 不提前释放 |

四项审查修复经范围复审为 PASS。复审覆盖完整 FieldRef、删除引用及回滚、无初始数据输入的 capability binding，以及字段回填边界。

## 新鲜验证

```text
后端 B 相关集成与合同：127 passed
后端 Ruff：通过
后端 mypy：通过（260 source files）
前端 TaskEvidence/TaskDataWrites：17 passed
前端 typecheck：通过
前端 build：通过
Electron 管理侧 B 链：passed
git diff --check：通过
```

全量前端首次与后端检查并发运行时为 3246/3250 通过，4 项失败中 3 项为 5 秒超时，1 项为认证恢复调用次数偏差；四个失败文件在资源释放后分别单独重跑全部通过。该次全量结果不能记为全绿，最终全量前端串行复验保留到 F。

## 视觉核验

任务输入/输出页继续采用原 gallery 的任务头、页签和双栏主体，顶部导航替代侧栏，统一使用细网格表格和小圆角。发现双栏默认拉伸导致左侧原始输入卡片出现大块空白后，在共享布局根节点改为顶端对齐；`05a-task-original-inputs.png` 显示输入表紧随标题，页面无应用级横向撑宽。

按原 `03-runs/006-task-input-output-approved-7af0aa.png` 人工逐项比较，当前任务输入/输出画面为 88/100，通过 85 分门槛。差异来自 B 增加了真实完整数据操作表，纵向内容多于原型；主体层级、操作位置、表格语言和全局样式符合已批准规则。

## 尚未完成

- PM4-C 调度、恢复和并发策略尚未交付。
- F 的第二自动化读取账号、跨包故障链、完整工程检查和最终视觉验收尚未执行。
- Windows、其他架构、打包应用、真实浏览器执行、真实 Studio、真实生产执行核心和用户手测均未执行。
