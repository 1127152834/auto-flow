# AM3 持久容量预留（2026-09-23）

状态：本增量完成验证，完整目标 active/partial。基线 `codex/android-management-complete@19755811`；本页与实现同提交。既有 3 个 Studio 文档改动保留，不纳入提交。

## 需求与落点

| 要求 | 实现 | 验证 |
| --- | --- | --- |
| AM-R12 / AM-AC16：待启动预算跨超时、取消、工作区与运行时重建保留 | `providers/android/capacity_reservations.py`；`management.py` 的 mutation/capacity/manage | `tests/integration/test_android_capacity_reservations.py`，真实双工作区容量实验 |
| 停止尚未核实不释放预算；运行实例不重复计费 | 命令返回后保留预留，到生命周期状态核实成功才释放；按完整容器 ID 扣除已计入的运行限额 | stop 状态读取失败、运行预留去重、创建丢响应后名称规范化 |
| CPU 配额、512 MiB 环境保留量、未知资源不按0处理 | 复用 `domain/android/capacity_rules.py`；实际容器限额和配置取较大预算；Memory=0阻止启动 | 既有容量 unit、实际限额漂移与零限额 integration |
| 所有启动经过管理准入 | `MacAndroidRuntime.connect()` 仅连接运行实例；`bootstrap/android_prepare.py` 显式调用 manage/start | connect 绕过启动 RED；真实准备和容量实验通过 |
| 原归属、generation、独占锁和持久操作不退化 | 复用 `AndroidManagement` 与原共享运行时锁，不新增并发执行器 | 外部 workspace 拒绝释放、旧代次拒绝释放、跨工作区锁互斥 |

路径均相对于 `apps/backend/src/autoflow`，测试相对于 `apps/backend`。

共享预算属于同一 Lima VM，不能只放在某个工作区 SQLite。运行时根目录的 `autoflow-redroid-capacity.json` 使用格式版本1，冻结 workspaceId/deviceId/generation/containerId/marker/memoryBytes；写入经过现有生命周期锁、临时文件、文件fsync、原子replace及目录fsync。读取损坏、链接、未知内存或身份冲突均阻止新准入。成功命令不等于已核实停止；unknown 不按 TTL 过期。该文件是预算事实，不能作为普通临时文件删除。

数据库和公开 DTO 形状未变，不需要工作区 DB 增量迁移；唯一 Alembic head 仍为 `am01_management_operations`。OpenAPI重新生成无差异。前端继续显示现有 capacity/unknown 错误与批次等待状态，本轮未修改前端。

## RED → GREEN

- 初始跨运行时 start/restart/stop 未保留预算、未确认恢复提前释放：`4 failed / 1 passed`；修复后 `5 passed`。
- 停止观察失败提前释放、connect直接启动：`2 failed`；修复后相关集合 `73 passed`。
- 容器真实限额高于配置、实际Memory=0被配置代替：`2 failed`；修复后容量集合 `9 passed`。
- 增补取消、共享锁、损坏文件/链接、未知内存、归属变化、原子发布失败、generation边界，容量集合 `16 passed`。
- 设备状态持久失败但未派发命令仍留下预留：`1 failed`；改为设备先持久、预算再持久、最后发送命令。
- 预算发布失败后旧marker阻止设备恢复：`1 failed`；未派发情况下只撤销本次匹配预留和marker，再保存设备；不清除任何已派发的未知操作。
- 创建丢响应后保留容器名称造成预算身份不一致：`1 failed`；归属核验后规范化为完整ID，再操作/记账。

这些集成测试使用真实 SQLite、文件发布与文件锁，只在 Docker/Lima IO 边界替身，不冒充真实实例。

## 最终自动验证

cwd `apps/backend`：

```sh
uv run pytest tests/contract/test_android*.py tests/unit/test_android*.py tests/integration/test_android*.py tests/integration/test_migration_heads.py -q
uv run ruff check src/autoflow/providers/android/capacity_reservations.py src/autoflow/providers/android/management.py src/autoflow/providers/android/mac_runtime.py src/autoflow/bootstrap/android_prepare.py tests/integration/test_android_capacity_reservations.py
uv run python -m compileall -q src/autoflow
uv run alembic -c src/autoflow/infrastructure/database/alembic.ini heads
```

最终聚焦 **289 passed / 2 warnings，52.32s**，其中新增容量集成18项；相关 Ruff/compileall 已通过，唯一 head 为 `am01_management_operations`。

cwd 仓库根，使用规格要求的 Node22.23.2：

```sh
npm exec --offline --yes --package=node@22.23.2 -c 'npm run openapi:generate && npm run openapi:check && npm run test:structure'
```

exit 0，生成无差异；结构 `4 passed`。

本轮未重跑无修改的完整前端/type/lint/build；最近结果见 [前端记录](2026-09-23-frontend-validation.md)。全后端/全Ruff/前端全量/全脚本的既有失败尚未处理，没有声明最终工程门槛通过；输出见 [上一轮记录](2026-09-23-command-verification.md)。最终全分支审查仍未执行。

## 真实 macOS 容量实验

命令 cwd `apps/backend`：

```sh
uv run python /tmp/autoflow-android-capacity-smoke-20260923-final.py > /tmp/android-capacity-real-final-20260923.log 2>&1
```

exit 0。[当次脚本文本](2026-09-23-capacity-smoke.txt)与[实际输出](2026-09-23-capacity-result.json)保留用于审计。文本固定本轮独立工作区，并拒绝复用现存工作区；不是通用 smoke CLI。

- Apple Silicon macOS；Lima ARM64，Docker-in-Lima，原 ReDroid 路线。实际 Docker MemTotal `8306655232` bytes。
- 镜像 `sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b`。
- 1536 MiB源设备 `a160ba69-547c-45f0-938d-57919f880466`；workspace `fac6c6cc52e9fe7d408906247e13634e04807b450bed5eca4acd530c1b85da07`。
- 6144 MiB候选设备 `ff322240-ee7f-4cdc-ab4d-d1cc62da2941`；workspace `66a7273ccbfa2d7c8dbc72d7d5ff68758615a538e7e11c59d4217e9b578a70dd`。
- 第一台实际启动并停止，脚本在真实 stop 完成后主动丢弃响应。实际容器已 exited，设备保持 recovery_required，预留 `1610612736` bytes。
- 在另一工作区创建新的运行时对象后，第二台启动准入返回 `ANDROID_CAPACITY`；原工作区读取真实完成marker并恢复后，同一候选准入通过。
- 第二台仅创建为停止状态并检查准入，没有启动6GiB实例；这不是两台同时运行、1/5/10台压力或性能证据。
- 两个自建容器和卷分别核验为0、deleted=true；共享预算恢复至实验前内容。`docker ps -q`无输出后恢复Lima到原Stopped状态，未删除既有停止容器或外部卷。
- 首轮相同实验亦exit 0，设备为 `9c3c664c-6485-48d2-a510-9a5d973fbe72` 与 `8e5f3948-872f-4506-b6eb-85eeb563ccea`，各自容器/卷清理为0。最终轮在设备先保存的顺序修复后重跑。
- 最终真实运行后新增的“发布失败撤销未派发marker”和“名称规范化”异常路径由自动化验证，未再制造真实磁盘故障或创建丢响应；不将它们写成真实通过。

## 剩余范围

本增量关闭持久容量预算缺口，不关闭整份T13清单或AM3阶段。跨重启应用结果恢复、批量规模/性能、真实APK及破坏性应用动作、AM4属性/链接/临时文件/高级日志、全量失败修复和最终审查仍需继续。无完成marker时保持未知预留，不通过删文件或超时过期来绕过核实。
