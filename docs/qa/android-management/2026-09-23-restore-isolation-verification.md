# 恢复中断隔离与成功发布验收

- 日期：2026-09-23；状态：confirmed（本增量），完整目标 active/partial。
- 基线：隔离分支 `codex/android-management-complete@be067690`。覆盖 T18/T20、AM-R15/AM-AC20 的失败隔离及恢复发布；不是 AM1–AM4 完整验收。
- 来源：本次实现、下列实际命令、[真实实验脚本](2026-09-23-restore-isolation-smoke.txt)和[原始结果](2026-09-23-restore-isolation-result.json)。

## 完成项

1. 恢复请求/备份/操作关联及 `restoreState=pending` 在首次设备落库、任何运行时 IO 之前保存。原 HTTP 向 config 传入恢复元数据，但真实 Mac `new_device` 不复制未知字段；旧测试运行时展开整个 config，掩盖了幂等重放差异。现在测试使用真实 `new_device` 建模。
2. 共用恢复意图规则覆盖管理操作、Mac 管理/连接、控制 claim、预览和备份入口。普通 recover 只能核实运行时，不能把未发布恢复变成可启动设备。兼容从旧 `creationConfig.restoreRequestId` 识别未发布意图；恢复创建拒绝自动启动。
3. 成功设备投影与操作回执使用同一个 SQLite 事务。事务检查目标 ID、generation、工作区、请求、备份和未删除状态；拒绝旧完成结果覆盖新设备状态。
4. 异常处理重新读取持久事实，不再把本地已改成 restored、但未提交的对象写回。提交前失败/取消/复制中断保持 pending；提交成功但回执丢失能读回成功。数据库无法核实时保持隔离，不自动重放。
5. 成功恢复仍拥有容器，`dataRetained=false`。恢复核实支持实际 runtime workspace hash，且排除已删除目标；成功幂等响应绑定精确目标、请求和备份。
6. 管理契约/OpenAPI 增加可空 `restoreState`，页面显示“恢复数据待核实”、去重阻塞原因，禁止提供启动/打开入口。字段保存在既有设备 JSON 中，不需要新增表或改写历史迁移；唯一 head 仍为 `am01_management_operations`。

## RED → GREEN

| 阶段 | 实际输出摘要 |
| --- | --- |
| 首轮有效隔离 RED | `8 failed, 2 passed`：缺少持久意图、启动/连接/claim/页面策略未拦截，实际适配器幂等重放失败 |
| 发布故障 RED | `6 failed, 11 passed`：generation/请求/备份/删除栅栏未检查；提交前失败保存 restored；提交后回执丢失被降级 |
| 自动启动 RED | `1 failed, 11 passed`：恢复创建允许 start=true |
| 契约/页面 RED | 后端 `1 failed, 11 passed`（缺少 restoreState）；前端 `1 failed, 7 passed`（没有隔离状态标签） |
| 隔离/HTTP 故障 GREEN（含取消） | `19 passed, 1 warning in 4.84s` |
| 最终 Android 后端与迁移 head | `362 passed, 2 warnings in 20.88s` |
| 最终 Node22 Android 前端 | `14 files, 105 passed in 6.53s` |

首轮测试曾使用非法 UUID，纠正后重新取得有效 RED；不把 UUID 校验错误当成隔离功能失败。前端第一次路径筛选写错，Vitest 返回 no test files/code1；按真实 domains/android/tests 路径重跑，未使用 passWithNoTests。

命令（根目录，另行标注除外）：

```text
(cd apps/backend && uv run pytest tests/unit/test_android* tests/integration/test_android* tests/contract/test_android* tests/integration/test_migration_heads.py -q)
# 362 passed, 2 warnings in 20.88s

(cd apps/desktop && npm exec --offline --yes --package=node@22.23.2 -c 'node --version && vitest run src/renderer/domains/android/tests && npm run typecheck && npm run lint && npm run build')
# Node v22.23.2；14 files / 105 passed；typecheck/lint/build exit 0；renderer built in 38.68s
# 仍有既有 zod PURE annotation 与 workflow 静态/动态 import 提示。

npm exec --offline --yes --package=node@22.23.2 -c 'npm run openapi:generate && npm run openapi:check && npm run test:structure'
# exit 0；structure 4 passed

uv run --project apps/backend python -m compileall -q apps/backend/src/autoflow
# exit 0
(cd apps/backend && uv run alembic -c src/autoflow/infrastructure/database/alembic.ini heads)
# am01_management_operations (head)
```

定向 Ruff 对本次变更的 11 个 Python 源文件及 2 个隔离/恢复测试执行，实际输出 `All checks passed!`；`git diff --check` 通过。完整全仓门槛仍沿用未通过状态，不以定向检查替代。

## 真实 macOS / Lima / ReDroid

命令：`uv run --project apps/backend python /tmp/autoflow-restore-isolation-20260923.py > /tmp/android-restore-isolation-real.log 2>&1`，exit 0。HTTP 通过真实 FastAPI 路由与 ASGI transport 调用，运行时实际操作 Docker 数据卷；没有用 mock 数据卷替代。

- 独立测试源 `0ef36cb9-635e-45de-8aad-f34553af4d24`，部分恢复目标 `842e6206-385c-54c6-b530-6eab5a4810b5`，正常恢复目标 `ee9569d6-2b83-5c8f-9ea7-8b4c342151da`。
- 精确镜像：`sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b`。备份 `214514fe-1d4e-4024-901a-9a221fdeeb31`，含 manifest 共 **16,769,264 bytes**。
- 在 restore_volume 故障注入边界，先通过真实 Docker 写入仅含 `data/partial-restore` 的归档，再抛出连接超时。读取真实目标卷确认 `incomplete-target` 存在。此为受控部分写入及连接中断模拟，**不是声称已做 kill -9 或真实断电**。
- 原请求 HTTP 503，操作 needs_verification。普通 recover 后设备 idle 但 restoreState 仍 pending；start/restart/restore/control/backup 均被拒绝；同请求再次 POST 返回409。目标只在明确永久删除后移除。
- 正常 POST 202，重复请求202且同操作、同设备。目标 restoreState=restored、dataRetained=false；UID10001/GID2000/mode0640 和测试内容与源一致。启动后 ADB 读回 `restore-isolation-proof`，源测试条目的内容/属性不变。
- 三个自建实例最终均 deleted=true、容器0、卷0；测试备份已删除。确认无运行中容器后 Lima 停止，保留已有外部资源。
- 最终 restoreState 契约/页面标签在本次真实数据实验之后补充，其证据为契约与 Vitest；未把它当作真实 Electron 点击验收。

## 阻塞项与剩余风险

- 本增量没有外部条件阻塞；尚未完成的源 xattrs 能力探测、归档 formatVersion/manifest 严格校验、直接恢复服务目标身份约束、硬进程中断和完整重启闭环仍是软件/验证待办。
- 对部分恢复目标采取持续隔离、核实运行时后永久删除策略；不将未知部分写入自动视为完成，也未实现断点续写。
- APK 遗留临时文件清理、高级脱敏日志、真实应用操作与1/5/10规模性能、最终全分支审查仍待完成。
- 全后端、全 Ruff、全前端、全脚本此前失败未解决，本增量未重跑这些全仓命令。GApps 候选镜像/网络/账号仍为独立 external blocked。
- 既有三份 Studio 未提交文档完整保留，不纳入本提交。未恢复退役工作流执行链；不把上述软件缺口归为环境阻塞。

本增量证据置信度高；完整开发和验收仍未完成。
