# 批次取消、新批次入口与并发取消保护

- 日期：2026-09-24；状态：confirmed（本轮软件门禁与真实HTTP），整体验收 partial / 桌面 blocked。基线 `aaa67b97`；[候选源码 SHA-256](2026-09-24-bulk-actions/candidate-hashes.json)绑定本次验证范围。
- 需求：规格 AM-R11、T13/T14。后端现有 cancelPending 契约不变，取消仅针对未准入项；确认终态才允许重新选择和提交新批次；未知结果、在途批次及动作响应丢失继续冻结原请求。
- 真实桌面入口验收 `blocked`：Mac 锁屏且 CUA 无法解锁，已请求用户手动解锁。没有拿组件测试代替真实 UI。

## 已实现

1. 复用 cancelPending 接口，展示“取消未开始项”，已开始项目继续报告；动作响应丢失后按原 action/requestId 重试，不再错误重提原批次。
2. 仅所有项为已确认终态才可“开始新批次”；新请求使用当前 revision 和新 requestId。提交后冻结目标控件，未提交时按当前有效目标 1–20 项准入，空筛选不能冻结空请求。
3. ManagementOverview 不因筛选结果变空卸载批量面板，运行状态变化或手动筛选不会丢失取消/核实/回执。
4. 队列每处理一个批次前重读持久状态。容量 await 前后检查快照；若期间被取消等动作替代，正常/异常/任务取消分支都不能写回旧状态，CancelledError 仍传播。
5. 核实运行时之后重新读取批次，按已检查的 operationId 合入持久 Operation 结果，保留其他项的取消和动作幂等回执。未知结果仍需持久事实证明，未放宽归属或准入。

无新增依赖、API shape、生成类型或数据库 schema；Alembic 唯一 head `am01_management_operations`。三份 Studio 文档 SHA-256 与保护基线完全相同。

## RED → GREEN 与审查

| 行为 | 有效 RED | GREEN |
| --- | --- | --- |
| 取消、取消响应丢失、终态新批次和未知冻结 | [7 failed / 29 skipped](2026-09-24-bulk-actions/actions-red.log) | [3 文件 / 89 passed，6.38s](2026-09-24-bulk-actions/actions-green.log) |
| 已提交的运行中/未知批次筛选至零匹配 | [2 failed / 18 skipped](2026-09-24-bulk-actions/filter-red.log) | [3 文件 / 91 passed，6.36s](2026-09-24-bulk-actions/filter-green.log) |
| 容量挂起期间取消，随后可用/不足/异常/任务取消 | [4 failed](2026-09-24-bulk-actions/cancel-race-red.log) | [44 passed](2026-09-24-bulk-actions/cancel-race-green.log) |
| 核实期间取消另一项，核实成功/断线 | [2 failed](2026-09-24-bulk-actions/verify-race-red.log) | [46 passed](2026-09-24-bulk-actions/verify-race-green.log) |
| 前批容量挂起期间取消后批；未提交选择筛选至零匹配 | [后端 1 failed](2026-09-24-bulk-actions/later-batch-red.log)、[前端 1 failed](2026-09-24-bulk-actions/empty-target-red.log) | 最终定向见下 |

最终定向：Android 域[14 文件 / 160 passed，17.82s](2026-09-24-bulk-actions/focused-frontend.log)；批次单元、HTTP 契约、真实 SQLite 集成和容量预留[47 passed / 1 warning，7.29s](2026-09-24-bulk-actions/focused-backend.log)。warning 为 Starlette anyio 别名弃用。定向集合重叠，计数不相加。

独立只读审查先报告筛选卸载/容量取消覆盖两项 Important；修复后又报告跨批次旧快照/空目标两项 Important，均有有效 RED 后修复。最终复审未发现剩余 Critical/Important；未审查真实 UI，也不保证多服务进程共享同一工作区的并发 CAS。

## 真实 Mac / ReDroid

运行 `uv run --project apps/backend python /private/tmp/autoflow-bulk-final-real.py`，源码保留为[real-cancel-restart.py](2026-09-24-bulk-actions/real-cancel-restart.py)，exit 0；[原始输出](2026-09-24-bulk-actions/real-cancel-restart.log)、[持久回执](2026-09-24-bulk-actions/real-cancel-restart.json)。

专用新工作区创建自有 8192 MiB 配置的**停机**实例，真实容量检查阻止启动并进入 waiting_capacity；取消后连续 10 次读取均 cancelled；重启自有 HTTP 服务后，以原动作 requestId 重试，回执与原结果一致，设备仍 stopped。随后仅删除该自建设备，生产 runtime 核实 missing；没有停止/删除任何外部实例、镜像或卷。此实验验证实际接口和持久性；精确交错竞态由真实 SQLite repository + 可控外部 IO 的集成测试证明，不混称实机注入。

上一切片 fixture 也已清理，见[清理结果](2026-09-24-bulk-stale-snapshot/cleanup.json)。所有自有验收客户端/sidecar 均已退出。

## 验证命令与剩余

```sh
npm exec --offline --yes --package=node@22.23.2 -c 'npm run test --workspace @autoflow/desktop -- src/renderer/domains/android'
uv run --project apps/backend pytest apps/backend/tests/unit/test_android_bulk.py apps/backend/tests/contract/test_android_management_bulk_projection.py apps/backend/tests/integration/test_android_multi_device.py apps/backend/tests/integration/test_android_capacity_reservations.py -q
uv run --project apps/backend pytest -q apps/backend/tests
uv run --project apps/backend ruff check apps/backend/src apps/backend/tests
uv run --project apps/backend python -m compileall -q apps/backend/src
npm exec --offline --yes --package=node@22.23.2 -c 'npm test -w @autoflow/desktop -- --maxWorkers=1 && npm run typecheck && npm run lint && npm run openapi:check && npm run build'
```

- 完整后端已通过：[4048 passed / 26 skipped / 2 warnings，981.16s](2026-09-24-bulk-actions/full-backend.log)，随后Ruff/compileall exit 0。两条warning为依赖弃用和故意重复APK Manifest。[完整前端](2026-09-24-bulk-actions/full-frontend.log)424文件/5650项通过，802.11s；typecheck/lint/OpenAPI/build exit 0，renderer build 37.55s。最终候选6个源码/测试SHA-256与启动门禁时一致。前一轮因第二轮审查后源码改变主动 SIGINT，exit 130，保留[后端](2026-09-24-bulk-actions/superseded-full-backend.log)/[前端](2026-09-24-bulk-actions/superseded-full-frontend.log)中止输出，不能计为通过。所有文本日志仅裁剪行尾空白/多余末尾空行；保留的 QA Python 源码仅经 Ruff 整理 import，无行为改动。
- CLI纠正：根目录 npm test 嵌套脚本未把 --maxWorkers 参数传给 Vitest，输出明确提示 Unknown cli config；该轮主动中止exit130，保留[日志](2026-09-24-bulk-actions/worker-cli-interrupted.log)。最终命令直接指定desktop workspace，启动行已确认 `vitest run --maxWorkers=1`；未提高测试超时。
- 最终 UI 批量自动收敛、取消和开始新批次受 Mac 锁屏阻塞；真实解锁后继续。
- T14/T16 还需前台延迟/隐藏页和后台探测同链；新批次进度的 setTimeout 循环尚需纳入隐藏页暂停检查。T09 桌面镜像删除/中断、T12 向前回退演练、最终全分支回归仍未闭环。
- GApps 候选/账号链、十实例容量外部阻塞保持原记录，历史 RED 缺证不追认。完整 AM1–AM4 目标仍 active/partial。

最终一致性核对：Alembic仍唯一am01_management_operations，无新schema/契约；三份Studio文件哈希与基线相同；候选源码/测试哈希不变。当前所有自建实例已清理，owned Electron/sidecar退出。增量审查无Critical/Important；整体AM目标和最新真实桌面验收未完成。
