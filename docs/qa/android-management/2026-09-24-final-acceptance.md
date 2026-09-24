# 安卓模拟器管理当前验收结果

2026-09-24；状态：**partial，尚不能完整签收**；置信度：高。当前产品候选 `0f6f8fac`（旧批次兼容修复；78bf8c92前端源码与本次完全一致）（修复前候选ef0af03f的结果保留为历史证据），隔离分支 `codex/android-management-complete`。原有三份Studio未提交文件保持原SHA256且不纳入本任务提交；未合并或发布。

## 当前验证结果

| 实际执行命令 | 实际结果 |
| --- | --- |
| `cd apps/backend && uv run pytest -q --tb=short` | exit0；4124 passed、26 skipped、2 warnings；780.28秒；对应0f6f8fac；[完整输出](2026-09-24-legacy-upgrade/backend-full.log) |
| `cd apps/desktop && npm test -- --maxWorkers=2` | exit0；424文件、5689项通过；357.04秒；78bf8c92结果，1050前端文件hash与当前一致；Node26.7.0，localStorage实验警告保留 |
| `uv run --project apps/backend ruff check apps/backend/src apps/backend/tests` | exit0 |
| `uv run --project apps/backend python -m compileall -q apps/backend/src/autoflow` | exit0 |
| `uv run --project apps/backend pytest apps/backend/tests/integration/test_android_m4_migration.py apps/backend/tests/integration/test_migration_heads.py -q` | exit0；6 passed，1.14秒；唯一head仍am01_management_operations |
| `npm run typecheck` / `npm run lint` / `npm run openapi:check` | 全部exit0 |
| `npm run test:structure` / `npm run test:scripts` | exit0；分别4和95项通过；生成的受保护Studio文档已恢复运行前字节 |
| `npm run build` | exit0；0f6f8fac重新构建通过，renderer30.69秒；[输出](2026-09-24-legacy-upgrade/build.log) |
| `uv run --project apps/backend python docs/qa/android-management/scripts/create-disk-admission-smoke.py --allow-device-mutation --output /private/tmp/android-final-review-real.json` | exit0/statuspassed；真实Mac/Lima/ReDroid，9条自建记录对应容器/卷清空，自有备份0 |

本轮补验命令：`uv run --project apps/backend python docs/qa/android-management/scripts/backup-permission-smoke.py --allow-device-mutation --output /private/tmp/android-backup-permission.json`，exit0/passed；`uv run --project apps/backend python docs/qa/android-management/scripts/legacy-upgrade-smoke.py --allow-device-mutation --old-checkout /private/tmp/autoflow-android-legacy-qa --output /private/tmp/android-legacy-upgrade-green.json`，exit0/passed。两次真实链自建容器/卷清理均为0；旧检出目录验收后已移除，重跑先检出a92f0688。

完整输出及逐命令退出码见[最终候选命令结果](2026-09-24-final-review-fixes/results.json)和[实施RED/GREEN](2026-09-24-final-review-fixes/implementation/final-fix-report.md)。新增兼容回归后Android定向后端540项通过（37.20秒），前端199项已通过，包含在各自全套中，不相加。旧候选提前中断的后端运行exit130保留原日志，不计通过。早期Node22和旧测试数属于各自提交历史，不代替当前结果。

## 已完成范围

- AM1基础生命周期、环境诊断、统一状态、持久操作、控制会话、保留卷删除和恢复、永久删除已实现；[AM1证据](am1-verification.md)。归属校验、独占控制、generation/sequence、幂等和未知结果保护保留。
- AM2镜像登记/拉取/删除、固定镜像身份、模板revision和快照已实现；[AM2证据](am2-verification.md)。[真实未知拉取](2026-09-24-pull-disk-and-bulk.md)已验证重启发现、核实前禁新请求、按原编号核实；实际pull仅一次。
- AM3批次、取消未开始项、失败重试和容量准入已实现；[AM3证据](am3-verification.md)。[真实Electron批次](2026-09-24-pull-disk-and-bulk.md)验证筛选保留选择、冻结目标、取消和终态新批次，持久记录一致，自建资源已清理。
- AM4应用、备份、恢复、清理及脱敏诊断已实现；[AM4证据](am4-verification.md)。[真实备份目录权限拒绝](2026-09-24-backup-permission.md)已补：EPERM→持久待核实、同编号不重放、恢复权限后新编号成功、源数据不变且资源清空。真实故障、源数据保护和清理结果按[24项验收矩阵](2026-09-23-acceptance-matrix.md)逐项列明。
- AM-R12原软件缺口已补：宿主/VM观测、备份预检、镜像拉取、单/批创建、配置复制、保留数据重建与备份恢复写前磁盘检查。不能可靠估计时由当前请求显式确认，默认拒绝；已知零空间/探测失败不能绕过，来源确认不能继承。最终真实创建/恢复/复制及未确认失败批次重试均通过；永久删除自建源实例后，工作区备份目录仍可列出其备份，恢复到新ID/卷后原探针一致、源归档摘要不变。

补充真实旧版本升级发现历史批次重放409，已在0f6f8fac修复：缺失来源字段与null仅在批次请求比较时等价，真实来源/磁盘确认变更仍冲突；真实旧SQLite/临时实例升级、数据保留和重放通过。该修复[独立复审](2026-09-24-legacy-upgrade/review.md)通过，Critical/Important/Minor均0；全后端4124passed（780.28秒），exit0。

Task3和Task4独立规格/质量审查通过，无Critical/Important。完整分支 `a92f0688..ef0af03f` [最终审查](2026-09-24-create-disk-admission/final-branch-review.md)确认0 Critical、5 Important。五项已在78bf8c92逐项RED→GREEN：旧核实投影增加运行时锁及事务栅栏；镜像验证尊重生命周期；隐藏页面必要心跳继续；停机维护/全局备份恢复可达；当前设备recover与历史回执verify分离。[独立范围复审](2026-09-24-final-review-fixes/review.md)确认I1–I5全部ADDRESSED，剩余Critical=0、Important=0；该结论不代替真实桌面未执行项。

## 阻塞、未执行与风险

- **blocked：Mac再次锁屏。** 控制工具实际报告无法自动解锁；新增确认、维护和设备恢复入口UI，以及隐藏页/前台性能未完成真实桌面验证。此前解锁期间完成的批次/未知拉取桌面证据仍有效，但不能覆盖新入口。
- **blocked：十实例容量。** 最低配置含预留需要8192MiB，当前Lima实际约7922MiB、6CPU。没有降低规格或占用用户外部实例来伪造通过。
- **blocked：GApps。** 专用镜像、测试账号及商店下载链缺失；没有以普通APK测试代替。
- **not_run：**镜像内容删除的完整桌面链、下载途中真实断网；同一发布停用/重新启用入口的完整组合链；[旧版本数据库与真实temporary实例升级](2026-09-24-legacy-upgrade.md)已通过；部分T14/T16桌面指标和历史缺失的RED原始输出。历史GREEN不能追认RED，后台HTTP耗时不能冒充桌面交互耗时。
- 磁盘预检不能保证其他进程随后占满空间，既有失败清理与needs_verification继续生效。本轮Node26实验警告、两条既有后端警告及旧默认四worker不稳定记录均保留。额外Python mypy扫描有6条既有诊断，已在修复前包布局基线复现，不能声称mypy全绿。顶层旧smoke脚本额外Ruff扫描既有I001/BLE001已在HEAD基线复现；规定的后端src/tests检查通过。

隐藏心跳的35秒fake-clock回归仅证明React/TanStack行为；实际Electron长期最小化仍待验证。[Electron官方文档](https://www.electronjs.org/docs/latest/api/browser-window#page-visibility)说明背景节流会影响计时器和可见性，未为绕过测试而全局关闭节流。

本报告不宣布AM1–AM4完整目标完成；原最终审查五项Critical/Important已修复并独立复审关闭；新增旧批次修复也已独立复审通过；实际环境和证据缺口关闭前，不宣布完整签收。分支与隔离工作区保留，未合并或发布。
