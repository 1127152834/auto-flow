# PM9 生产 End 切片验证

日期：2026-09-28；状态：confirmed（有界切片验证，不代表 PM9 全部完成）。

当前源码按 `task-1-brief.md` 实施，业务基线 `faf8fc21`，本轮收尾起点 `c6c18762`；期间主控独立进程诊断提交推进到 `c3213f4c`，不是本切片实现。

- `*.command.json` 保存真实命令参数、cwd、退出码、耗时与相关环境变量；同名前缀 `.log` 是原始输出。各 pytest 均用专属 `/tmp/autoflow-pm9-end.*`，没有清理其他运行的证据。
- `red-boundaries.log`：新增静态目标冻结、generation/attempt 拒 bool、空白名称、磁盘缺失、同长度篡改共 6 项先失败；`green-boundaries.log`：修复后 20 项通过。命令为在 `apps/backend` 执行 `.venv/bin/python -m pytest tests/integration/test_project_end_worker.py -k 'unfrozen or damaged' -q --basetemp="$(mktemp -d /tmp/autoflow-pm9-end.XXXXXX)"`（exit 1），绿测移除 `-k` 并加入 `tests/unit/test_environment_store.py`（exit 0）。
- `expanded.log`：补充控制／错误／输出选择后 32 项通过，使用相同两个测试文件与独立 basetemp，exit 0。
- `regression`：100 项相关后端回归通过，含 dispatcher、环境最终化和迁移 heads。
- `end-pass`：124 项 End、范围预检、required-fields、磁盘兼容测试通过。新增记录用例上一轮因测试把已有返回键 `ref` 写成 `recordRef` 失败；修正测试后通过，没有改变正式创建返回协议。
- `retention-final`：41 项环境相关回归通过；`final-small`：最后旧环境恢复／End 33 项通过；`integrity-final`：最后恢复结果完整性 4 项定向检查通过。该错误详情字段随后暴露一处dict类型推断错误（`strict-final`保留红日志），补显式错误字典类型后`strict-verified`通过。
- `frontend-final`：33 文件 / 212 tests 通过。前一轮仅 required-field-protocol 的 217→218 计数未同步失败，已修正。
- `scripts-pass`：12 项元数据生成、候选清单、教学覆盖脚本通过；候选生成没有改写历史 capabilities/test-cases/component-tools。
- `mypy-final`：全部 22 个修改源码文件通过；`strict-new`：3 个新增源码文件严格检查通过；`strict-verified`：最终全仓严格增量门禁为 1041 baseline / 1041 current / 0 new，不代表全仓 strict 零债务。
- `ruff-complete`、`script-ruff`、`eslint`、`eslint-extra`、`typecheck-final`、`openapi`、`build` 均通过。构建为当前桌面源码构建；不声称冻结 sidecar 包或全部平台重新验收。

## 真实运行与内部故障注入分账

`real-browser` 为 2 个参数化测试：1 条真实正向 + 1 条真实浏览器运行后内部回执故障注入，不能把 2 条都称为真实通信故障验收。

1. `real-positive.json`：专属SQLite与生产worker/已安装CloakBrowser。首任务 `abc29f42-916b-43ee-8fef-31de875e920f`，Run `c975d3bd-b6fb-456f-857f-febf3eee039e`；本地HTTP真实Set-Cookie登录、正式项目写数据与推进状态、End保存关联。第二任务 `9cb14ee9-4805-4f78-8725-f54be6363a8f`，Run `bc63e6ae-b682-4030-bab4-28d34d809434` 从保存环境启动，服务器和页面均确认 signed-in。没有预填cookie，没有替代外部成功。
2. `real-receipt-injection.json`：任务 `5fab1681-b0d0-4e94-a08e-041aabbc96ed` / Run `5f281258-1a85-45da-b9e2-7dcf0cc55bb6`。真实 `worker.run` 已确认清理后，测试把返回 `cleanup_confirmed` 改 false，并使内部 `force_stop` 报错，证明 dispatcher 保持 reconciling、未发布、租约仍持有。**不代表物理浏览器未退出、实际丢失 IPC 回执或进程清理物理故障已验收。** 原始资源目录 `/tmp/autoflow-pm9-end.mrO5ZX`。
3. `prior-stage/` 保留前实施者日志与正向证据，适用其历史现场；不据此声称最终源码所有边界通过，历史完整 shell 包装未还原。

## 验证边界

生产End使用现有worker、Operation/End/save账本、Task/Run/代次与租约，未改人工跨重启续接或进程清理helper。未做全仓pytest／前端全量、正式Electron End配置手测、冻结包、Windows x64/macOS Intel、真实物理关闭未知故障。主控继续独立审查和统一回归。

新保存目录 `.digest-version=2` 对路径、大小、内容做SHA-256；未知版本拒绝。无版本历史目录沿用原路径＋大小摘要，不重签或迁移用户数据，其校验不能证明同长度内容未变。测试覆盖旧目录读回、新版本同长度损坏和未知版本拒绝。

本Run完整 AOCI 5块交付确认与一次语义Attestation通过（9/10）；正式认知治理仍dirty/stale。按明确隔离要求未修改配置／索引、未运行维护工具，业务决策绑定当前源码。

## Fix round 1：End 调度终止与持久关联修复

`FIX_BASE=b16e1715`。完整实现和边界见 task-1-report.md 的 round 1 附录。所有 `fix1-*.command.json` 记录实际 argv/cwd/env/exit，配套 `.log` 保留失败原文。

- 有效控制流红：`fix1-runtime-red-corrected` 4失败/3通过；修复后 `fix1-runtime-green` 7通过。`fix1-runtime-red` 是最初测试事件名写错，不能计产品红。
- SQLite重开修复红绿：`fix1-repair-red` 缺save身份失败，`fix1-repair-green` 通过。
- 聚焦回归：`fix1-backend-green` 100通过；最后锁内闸门后 `fix1-runtime-final` 20通过。`fix1-frontend` 14通过、最终标题调整 `fix1-frontend-final` 5通过（重叠）。
- 真实浏览器：`fix1-real-green` 中 linear/loop/workflow/module 4通过，canvas旧header形状准入拒绝；正式group形状 `fix1-real-canvas` 1通过。对应5份JSON为唯一本轮真实正向，含持久工作区、Task/Run和HTTP观察；每条包含后续登录复用，四种控制流没有End后副作用请求。`fix1-real` 是夹具错误的初次失败。
- 门禁：`fix1-ruff-final`（cwd backend）、`fix1-mypy`、`fix1-eslint`、`fix1-typecheck`、`fix1-openapi`、`fix1-strict-stable` 均exit0。root cwd Ruff/strict错误与被源码编辑交叉的strict诊断保留，不作为最终状态。strict未改baseline，最终1041既有/0新增。
- `AUTOFLOW_TEST_PROJECT_WORKER` 选择冻结worker入口已接线；本轮未设置，未构建冻结包。无Electron手工、Windows/Intel、物理未知关闭证据。以前的关闭回执测试仍只算“实际浏览器运行后内部回执故障注入”。

## Fix round 2：未知关联修复按原键核验

FIX_BASE `1fdda1c8`。`fix2-red` 3新增组件红；`fix2-typecheck` 暴露公共操作kind缺口；`fix2-http-red` 证明真实SQLite修复操作无法通过原公共by-key FastAPI响应校验。修复后 `fix2-final` 29前端、`fix2-http-final` 1 SQLite/ASGI合同、`fix2-contracts` 6项目合同通过；`fix2-typecheck-final`、`fix2-eslint-final`、`fix2-openapi`、`fix2-ruff`、`fix2-mypy` 全exit0。`fix2-green` 18项是更早较小集合，`fix2-http-green` 是补身份断言前的同一场景，不能重复计数。

组件传输模拟服务器提交后丢响应/查询不可用；验证固定持久键、未知禁新提交、重开和连接/workspace资格隔离及仅1次POST。后端通过TestClient实际ASGI路由验证SQLite持久操作的原key/project/operationId，不是物理TCP断连。本轮未再跑真实浏览器或冻结包，没有新外部成功声明。完整说明见task-1-report round2。
