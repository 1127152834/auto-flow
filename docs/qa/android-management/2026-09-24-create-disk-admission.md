# 创建、复制与恢复磁盘准入验收

本文件保留Task4候选ef0af03f证据；后续最终修复候选78bf8c92的全量与实机结果见[最终验收汇总](2026-09-24-final-acceptance.md)。

2026-09-24，confirmed真实后端及自动化证据，整体partial。最终产品候选ef0af03f（前端b744666d）；[源码哈希](2026-09-24-create-disk-admission/candidate-source-hashes.json)。Task4独立规格与质量审查通过，无Critical/Important；完整分支审查另行执行。真实新UI仍因Mac锁屏blocked，不宣称完整验收通过。

## 真实Mac/Lima结果

`uv run --project apps/backend python docs/qa/android-management/scripts/create-disk-admission-smoke.py --allow-device-mutation --output /private/tmp/android-create-disk-real.json` exit0/statuspassed。

- 单创建未确认：202后持久failed/ANDROID_DISK_ESTIMATE_UNKNOWN；真实查询容器和卷均为空。相同ID显式false回放原操作，改变为true返回409。
- 当前请求显式确认后实例ready，写入自有探针。保留数据删除后，不带当前确认的restore失败，原卷仍存在而容器为空；recover后新编号明确确认可恢复，卷ID相同，探针一致。没有继承最初创建的确认。
- 源停机备份后，未确认恢复返回409/ANDROID_DISK_ESTIMATE_UNKNOWN且父操作failed、目标容器/卷为空；确认后新ID和独立卷恢复，启动读回探针一致，源备份所有文件SHA256未变。
- 模板批量和源快照复制各自验证未确认failed/无运行时对象、确认后succeeded且独立停机实例。复制未继承源确认。
- 最后再次启动源实例读回原探针。8条自建记录逐一真实归属verify，容器/卷均为空；自有备份清理后0。原始JSON含ID与四个批次结果。

证据：[原始JSON](2026-09-24-create-disk-admission/real-create.json)、[stdout](2026-09-24-create-disk-admission/real-create.log)。真实对象查询与自动化写入前调用断言分别记录，不把最终对象为空冒充对每条Docker命令单独计数。

## QA脚本兼容

既有成功smoke路径显式传入allowUnknownDiskEstimate:true，保留原allow-device-mutation开关；新脚本另覆盖默认拒绝，不通过取消断言来适配。相关docs/qa脚本Ruff与编译通过。顶层scripts/smoke-android-management.py只加同一确认字段；该脚本既有Ruff I001/BLE001已在HEAD导出的同内容基线上复现，保留[原始输出](2026-09-24-create-disk-admission/legacy-smoke-baseline-ruff.txt)，不冒称该额外扫描通过。规定后端src/tests Ruff门禁另行执行。

首次候选自审发现失败创建批次重试可能误报成功，已RED→GREEN修复于ef0af03f。已提前启动的全后端旧候选运行由根任务主动SIGINT终止，exit130，不能算通过（[原始日志](2026-09-24-create-disk-admission/old-candidate-full-run-interrupted.log)）；已对最终修复候选启动全量复跑。首次真实QA未覆盖该重试路径，后续脚本已添加拒绝后retry仍failed的检查，最终代码真实复跑已通过，见下文。

## 最终候选后端真实复跑

后端ef0af03f，前端b744666d。补充失败批次retry场景后同命令将output改为 `/private/tmp/android-create-disk-real-v2.json`，再次exit0/statuspassed；首次创建/保留卷恢复/备份恢复/模板批量/源复制/源数据保护仍通过，未确认批次retry继续failed且无容器/卷，8条自建记录全部清理、备份0。见[最终候选JSON](2026-09-24-create-disk-admission/real-create-final.json)和[源码哈希](2026-09-24-create-disk-admission/candidate-source-hashes.json)。

自动化局部：后端515 passed，前端193 passed，分别详见[后端报告](2026-09-24-create-disk-admission/task-4-report.md)和[前端报告](2026-09-24-create-disk-admission/task-4-frontend-report.md)。构建npm run build exit0，renderer32.59秒。本轮宿主Node实际26.7.0，不沿用历史Node22标签；全前端 `npm test -- --maxWorkers=2`（apps/desktop目录）已exit0：424文件、5683测试通过，351.96秒；Node26的localStorage实验警告保留于[输出](2026-09-24-create-disk-admission/frontend-full.log)。全后端 `uv run pytest -x -q` 已exit0：4099 passed、26 skipped、2 warnings，794.17秒；[原始输出](2026-09-24-create-disk-admission/backend-full.log)。以上完整门禁对应ef0af03f，最终全分支审查后若修复产品必须重跑。

真实新前端验收blocked：CUA报告“Mac is locked and automatic unlock could not unlock it”，已请求用户手动解锁。已准备独立workspace，仅登记基础镜像和模板，尚无设备；不把组件测试冒充这四入口的真实桌面验收。此前真实批次与镜像未知核实来自当时解锁的实际运行，证据仍有效，但不代表本次新增确认UI。

## 最终候选工程门禁

[逐命令退出码与耗时](2026-09-24-create-disk-admission/results.json)：后端src/tests Ruff、compileall、类型、lint、OpenAPI、build全部exit0；迁移6项、结构4项、脚本95项通过。测试脚本生成的Studio文档已按运行前字节恢复；三份既有脏文件SHA256与任务前相同，没有纳入本任务提交。

[Task4独立审查](2026-09-24-create-disk-admission/task-review.md)只证明该切片的规格/质量；全部AM1–AM4分支审查尚在进行。
