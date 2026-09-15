# PM4 V1 与 B 显式数据能力手动验收

日期：2026-09-15。适用分支：`codex/project-management-pm4`。

本手册只验收 PM4 V1 管理闭环：通过真实 Electron 界面维护项目、三张数据表、业务状态、记录和自动化，使用真实 FastAPI、SQLite、数据领取和项目数据操作查看运行事实。执行步骤由隔离的确定性假执行器触发，不执行网页，不调用 Studio，也不能据此认定生产工作流执行核心已经可用。

当前用户手动验收状态：**未执行**。

## 1. 一条命令启动隔离版本

在终端执行：

```bash
cd /Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm4 && npm run build && node scripts/qa-project-management-pm4.mjs --manual
```

命令会完成以下准备并保持应用打开：

- 在系统临时目录新建唯一的 `autoflow-pm4-v1-qa-*` 所有者目录和 `workspace`；
- 写入 `.pm4-v1-qa.json` 和 `.autoflow-workspace.json` 标记；
- 启动真实 Electron、FastAPI 和独立 SQLite；
- 准备名为“PM4 V1 隔离执行器资料”的工作流夹具和“PM4 V1 隔离执行器资源”的浏览器配置夹具；
- 通过真实界面自动跑一遍基准三表链，再保持应用打开，供人工核对和重复操作；
- 在终端打印本轮 `owner`、`workspace`、`evidence` 和 `result.json` 路径。

运行前要求本机已安装一个公开版 CloakBrowser 内核。该内核只用于通过现有资源校验；V1 假执行器不会启动该浏览器。

`--prepare-only` 只检查隔离环境和夹具准备，随后退出；它不执行三表链，不能记录为端到端通过。

## 2. 测试资料

人工重复链使用以下固定资料，便于与自动基准比较：

| 对象 | 名称与内容 |
|---|---|
| 项目 | `PM4 V1 人工验收`；描述 `两个必要输入、显式状态写入和账号新增` |
| 人员表 | 字段 `姓名`，必填；记录 `张三`；业务状态为空 |
| 邮箱表 | 字段 `邮箱地址`，必填；状态 `待使用`、`已使用`；记录 `zhangsan@example.test`，初始状态 `待使用` |
| 账号表 | 必填字段 `人员`、`邮箱`、`网页结果`；启动前无记录 |
| 自动化 | `三表资料处理-人工`；用途 `选择人员和邮箱，写入邮箱状态并新增账号` |
| 工作流夹具 | `PM4 V1 隔离执行器资料` |
| 浏览器配置夹具 | `PM4 V1 隔离执行器资源` |
| 数据输入 | `人员输入`→人员表，`邮箱输入`→邮箱表；两项均选择“独立”和“必填” |
| 启动参数 | 本次任务数 `1` |

## 3. 首条三表链逐步操作

| 编号 | 操作步骤 | 预期结果 | 用户结果 |
|---|---|---|---|
| PM4-V1-U01 | 顶部导航打开“项目”，点击“新建项目”；按测试资料填写名称和描述并保存 | 进入新项目概览；顶部导航保持现状；刷新页面后项目仍存在 | 未执行 |
| PM4-V1-U02 | 进入“数据”，新建“人员”表；打开“字段与校验”，新增必填文本字段“姓名”并统一保存；回到“数据记录”，新增一行“张三” | 字段保存后列表只出现一个“姓名”字段；人员表恰好一条记录，业务状态未设置 | 未执行 |
| PM4-V1-U03 | 返回数据表目录，新建“邮箱”表；新增必填文本字段“邮箱地址”；在“数据状态”创建“待使用”和“已使用”；新增 `zhangsan@example.test`，再把该记录状态设为“待使用” | 邮箱内容与业务状态分别显示；状态修改不改变邮箱字段内容 | 未执行 |
| PM4-V1-U04 | 返回数据表目录，新建“账号”表；新增三个必填文本字段“人员”“邮箱”“网页结果”；不要新增记录 | 账号表结构保存成功，记录数为 0 | 未执行 |
| PM4-V1-U05 | 进入“自动化”，新建“`三表资料处理-人工`”；关联“PM4 V1 隔离执行器资料” | 自动化进入编辑页；四个配置页签可用 | 未执行 |
| PM4-V1-U06 | 在“输入与参数”连续添加两项数据输入：`人员输入` 选择人员表，`邮箱输入` 选择邮箱表；两项均选择“独立”和“必填” | 两项输入分别显示别名、表和必填状态；配置未混成同一输入 | 未执行 |
| PM4-V1-U07 | 在“资源与环境”把浏览器配置来源设为“指定浏览器配置”，选择“PM4 V1 隔离执行器资源”；点击“保存配置” | 只保存一次；重新打开后两个输入及资源选择仍存在 | 未执行 |
| PM4-V1-U08 | 点击“启动运行”，把本次任务数设为 `1`；在输入预检中核对人员和邮箱两项候选，再点击“启动 1 个任务” | 创建一个批次和一个 Task；两项必要输入共同成功后才创建 Task；页面进入批次详情 | 未执行 |
| PM4-V1-U09 | 等待批次完成，打开唯一任务，再打开“输入与输出” | “原始数据输入”显示 `人员输入=张三` 和 `邮箱输入=zhangsan@example.test`；“任务数据写入”显示邮箱状态从“待使用”改为“已使用”，并显示账号新增成功 | 未执行 |
| PM4-V1-U10 | 返回人员、邮箱和账号三张表逐项核对 | 人员记录内容、状态和版本事实保持不变；邮箱内容不变且状态为“已使用”；账号表恰好新增一条，内容来自冻结的人员、邮箱和假执行结果 | 未执行 |
| PM4-V1-U11 | 刷新任务页，并退出、重新执行启动命令后检查本轮 `result.json` 和截图 | 已提交的任务输入和写入证据可读取；不得把重新启动的新隔离工作区误认为旧工作区持久恢复 | 未执行 |

## 4. 正常状态、停止与恢复边界

V1 假执行器执行很快，当前 `--manual` 工具没有提供“在某一步暂停”的用户按钮。因此普通停止和强制停止不能靠手速稳定复现，不能把以下自动专项写成用户端到端通过。

| 编号 | 复现方式 | 应核对的事实 | 证据等级 | 用户结果 |
|---|---|---|---|---|
| PM4-V1-N01 | 正常执行 PM4-V1-U08～U10 | 批次 completed、Task succeeded、lease 在终态确认后释放；人员不变、邮箱只改状态、账号只新增一次 | 真实 Electron UI + FastAPI + SQLite；执行器为 fake | 未执行 |
| PM4-V1-N02 | 在任务输入输出页刷新、切换页签并返回 | 原始输入快照不随后续表数据变化；写入摘要不重复、不消失 | 用户 UI | 未执行 |
| PM4-V1-N03 | 运行 `uv run --directory apps/backend pytest tests/integration/test_pm4_qa_runner.py::test_stop_wins_before_first_step_and_runner_does_not_write -q` | 普通停止先取得权时不发生邮箱/账号写入；Run 与批次进入停止终态并释放可安全释放的 lease；随后重复强停命令保持同一停止事实 | 真实调度与临时 SQLite 的自动集成反例；不是 Electron 人工路径 | 未执行 |
| PM4-V1-N04 | 在 PM3 隔离工具中按既有手册复验普通停止和 30 秒后强停 UI；本 V1 只回归沿用的停止协议 | 普通停止已接受后继续查询；强停只在宽限期满足后出现；旧执行代次撤权且不再写数据 | PM3 已交付链的人工回归；不替代 PM4 数据写入竞争 E2E | 未执行 |

在 PM4 后续调度切片交付带暂停屏障的专用 QA 控制前，N03/N04 只作为边界核验，不填写为“PM4 V1 用户手测通过”。

## 5. ACK 丢失、缺少授权与旧代次反例

这些故障均不得通过直接编辑数据库制造。当前 V1 手动启动器尚未暴露故障控制，使用以下专项自动测试复现，并在结果中标记证据类型。

```bash
cd /Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm4

uv run --directory apps/backend pytest \
  tests/integration/test_pm4_qa_runner.py::test_runner_recovers_lost_create_ack_without_duplicate_account \
  tests/integration/test_pm4_qa_runner.py::test_old_generation_cannot_write_or_finalize_and_keeps_leases_held \
  tests/integration/test_pm4_qa_runner.py::test_missing_qa_write_grant_rejects_start_without_durable_run_facts \
  tests/integration/test_pm4_qa_runner.py::test_missing_qa_status_grant_rejects_start_without_durable_run_facts \
  -q
```

| 编号 | 故障与预期 | 用户结果 |
|---|---|---|
| PM4-V1-E01 | 账号新增已经提交但 ACK 丢失：使用原 operationId 查询并恢复同一结果；账号表仍恰好一条，不产生第二条 | 未执行 |
| PM4-V1-E02 | executionGeneration 已变化：旧执行代次不能再写邮箱、创建账号或提交终态；结果未核实时 lease 保持占用，不能提前释放 | 未执行 |
| PM4-V1-E03 | 缺少账号表 create grant：启动在持久 Task/Run/lease 产生前被拒绝；不能只做邮箱状态写入 | 未执行 |
| PM4-V1-E04 | 缺少邮箱 status grant：启动在持久 Task/Run/lease 产生前被拒绝；不能只新增账号 | 未执行 |
| PM4-V1-E05 | 两个必要输入中任一被占用：整组领取失败，不产生半个 Task、半份快照、孤立 Run 或单边 lease | 未执行 |

自动测试通过只证明相应服务与事务反例，不代表故障已经从 Electron 界面人工操作完成。

## 6. 视觉、键盘和窗口检查

| 编号 | 操作 | 预期 | 用户结果 |
|---|---|---|---|
| PM4-V1-V01 | 以 1440×1024、100% 缩放检查数据表目录、自动化输入、启动预检、批次详情和任务输入输出 | 顶部导航；主体遵循既有 gallery；统一细网格表格和小圆角；页面不出现横向撑宽 | 未执行 |
| PM4-V1-V02 | 调到 200% 缩放并使用长项目名、长邮箱和值 | 页面宽度稳定；长值截断或换行；只有明确的表格容器允许内部滚动 | 未执行 |
| PM4-V1-V03 | 全程使用 Tab、Shift+Tab、Enter、Escape 操作输入配置和启动弹窗 | 焦点顺序明确；Escape 关闭当前浮层并恢复焦点；保存或提交期间不重复触发 | 未执行 |

当前机器证据的独立逐图视觉复审已通过，具体评分见 [v1-verification.md](v1-verification.md)。V01～V03 仍须由用户实际操作后记录用户手测结果，不能用自动截图复审代替。

## 7. 结果记录格式

每个用例按以下格式记录：

```text
用例编号｜通过/失败/未执行｜实际操作｜实际业务事实｜证据类型（UI/自动集成/只读查询）｜截图或 result.json 绝对路径｜与预期差异
```

禁止把以下内容写成用户手测通过：自动 CDP 操作、后端 pytest、`--prepare-only`、只读 API 核对、尚未完成的视觉复审。

## 8. 退出与清理

1. 在运行 `--manual` 的终端按 `Ctrl+C`，等待 Electron 和 sidecar 退出。
2. 从终端输出复制本轮 `owner` 绝对路径。
3. 确认 `owner/.pm4-v1-qa.json` 内容的 `kind` 为 `pm4-v1-project-management-qa`、`version` 为 `1`，且目标 `workspace` 位于该 owner 内。
4. 只清理这一个带上述标记的 `autoflow-pm4-v1-qa-*` 临时目录。不要清理用户工作区、主项目、PM3 工作区或仓库中的 `docs/project-management/implementation/pm4/qa-runs/v1-*` 证据。

## 9. PM4-B 管理页核对

使用第 1 节命令启动时，QA 默认运行 B 模式。完成 U01～U09 后，在任务“输入与输出”页继续核对：

| 编号 | 操作 | 逐步预期 | 用户结果 |
|---|---|---|---|
| PM4-B-U01 | 查看“原始数据输入” | 人员、邮箱两行紧随卡片标题；显示创建 Task 时冻结的字段值；右侧操作较多时左卡片不被等高拉伸 | 未执行 |
| PM4-B-U02 | 从“项目数据操作”表首行滚动到末行 | 依次可看到查询、读取、状态清空/设置、账号新增/编辑/删除、字段新增/确保/修改；每条显示确认状态，记录和字段操作显示稳定引用 | 未执行 |
| PM4-B-U03 | 返回邮箱表和账号表 | 邮箱内容不变、业务状态为“已使用”；账号只保留一条，网页结果为 `PM4-B-UPDATED`；一次性账号不存在 | 未执行 |
| PM4-B-U04 | 刷新任务页并再次打开“输入与输出” | 原始输入与数据操作事实来自持久记录，顺序和结果不丢失、不重复 | 未执行 |

异常反例不要求直接修改数据库。运行：

```bash
cd /Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm4
uv run --directory apps/backend pytest \
  tests/integration/test_project_node_writes.py \
  tests/integration/test_project_capability_fencing.py \
  tests/integration/test_project_capability_review_regressions.py \
  -q
```

重点核对：Task 自写后版本推进、人工修改后旧写冲突、查询动态 lease 失败零残留、跨表同字段 ID 不越权、引用中的记录不能删除、回填超过 1,000 行或 4 MiB 时整笔拒绝。命令通过属于自动集成证据，不能填写为用户界面手测通过。

Windows、其他 CPU 架构、打包应用、真实浏览器执行、真实工作流核心接入、Studio 联合运行及本表用户手测均保持“未执行”。
