## Finding Verdicts

- **I1 — 旧生命周期核实覆盖新代次和控制归属：ADDRESSED。** `apps/backend/src/autoflow/application/android/verification.py:39` 保存核实前副本，`:54`–`:67` 在既有锁下重读并检查当前操作身份、占用、pending app/restore 和副本一致性；`:86` 把 expected_device 传入事务。`apps/backend/src/autoflow/infrastructure/database/android_operations.py:194`–`:197` 在操作写事务中再次校验设备，冲突回滚操作及设备两者。新增真实 SQLite + AndroidManagement + Event 交错测试保留 generation=4、manual 和新 owner；另有事务冲突及隔离测试。中断 restore 的永久删除例外只在 deleteData=true 且实际观察为 missing 时释放为删除墓碑，保留 restore 标记。原缺陷已消除。
- **I2 — 元数据核实复活镜像墓碑并覆盖删除：ADDRESSED。** `apps/backend/src/autoflow/application/android/images.py:349`–`:352` 复用既有 runtime lock，从读取、生命周期准入、探测直到保存保持锁；只允许 registered/verified。已取消登记、已删除、三类待核实删除状态均不再被验证重新激活；Event 控制的验证/删除交错测试证明删除之后 revision=2 和原 deleteRequestId 保留。显式 register 才能重新登记，原缺陷已消除。
- **I3 — 隐藏页面停止心跳：ADDRESSED（原确定软件缺陷）。** `apps/desktop/src/renderer/domains/android/pages/AndroidPage.tsx:157` 仅给会话心跳设置 `refetchIntervalInBackground: true`，展示查询保持原前台轮询。新增真实 AndroidPage/QueryClient、模拟时钟测试覆盖隐藏 35 秒至少六次心跳、零额外设备/应用展示轮询，返回后沿同会话发送输入且没有第二次 claim。该证据证明 TanStack 不再主动跳过心跳，不证明真实 Electron 长时间最小化时的调度周期；后者仍保留为验收证据缺口，不能写成真实通过。
- **I4 — 停机备份和删源恢复入口不可达：ADDRESSED。** `apps/desktop/src/renderer/domains/android/pages/AndroidPage.tsx:458`–`:471`、`:521` 新增独立 maintenance 入口，只选择设备并展示 BackupPanel，不启动或申请控制；`:529` 在首页展示不依赖存活设备的工作区备份目录。`apps/desktop/src/renderer/domains/android/components/BackupPanel.tsx:9` 不提供 deviceId 时显示全部备份；`:14` 仍要求停机、空闲、无会话、状态新鲜且无 pending restore 才能创建。页面级回归覆盖停机备份和空设备目录下恢复孤立备份；根任务真实 Mac HTTP/运行时证据另覆盖永久删源后从目录恢复新 ID/卷、探针一致和归档 SHA 未变。原 UI 入口缺陷已消除，新维护页面真实视觉/鼠标验收仍未执行。
- **I5 — 当前设备核实误接历史回执核实：ADDRESSED。** `apps/desktop/src/renderer/domains/android/components/ManagementOverview.tsx:115` 将卡片 verify 映射为既有 recover；`:116` 历史操作继续传原 operationId/requestId 的 verify。`apps/desktop/src/renderer/domains/android/pages/AndroidPage.tsx:403`–`:417` 分别调用历史核实与设备操作端点，不重写 failed 历史、不重放原动作。页面回归覆盖 failed 生命周期、无历史操作的 unknown 和 pending restore；后者仍禁止启动/备份并保留安全删除。原接线缺陷已消除。

## New Breakage in the Fix Diff

- **None。** 本轮修复 diff 未发现新增 Critical / Important / Minor。
- 检查范围：`ef0af03f..78bf8c92` 的 12 个产品/测试文件，使用 `review-ef0af03f..78bf8c92.diff` 按文件切片复核；`9f9e3ff9` 是根任务 QA 归档，不把历史日志或源头以外 dirty 文档当作产品修复。没有重开全库审计，没有子代理，没有产品修改。

## Checks

- 已核对 `final-fix-brief.md`、`final-fix-report.md` 的逐项要求、测试名称与实际保留日志，不仅接受报告摘要。
- `i1-red.log`：1 failed；`i1-isolation-red.log`：2 failed/3 passed；`i1-disposal-red.log`：1 failed。`i1-final-green.log`：23 passed。diff 中的失败断言针对真实持久代次/owner/操作状态，未以放宽生产栅栏满足旧 fixture。
- `i2-red.log`：11 failed；`i2-green.log`：44 passed。测试覆盖五种禁止生命周期状态和受控 probe/delete 交错。
- `i3-red.log`：1 failed/37 passed（原 npm 转发没有真正限制测试，报告已如实说明）；`i3-green.log`：1 passed/37 skipped。模拟时钟和测试替身边界已明确。
- `i4-red.log`：2 failed；`i4-green.log`：108 passed；`i5-red.log`：3 failed；`i5-green.log`：64 passed。新增页面测试验证真实组件的入口和发出的请求，而非只直接调用 BackupPanel。
- `android-backend.log`：534 passed/2 warnings，37.86s；`android-frontend.log`：14 files/199 passed，7.76s。该软件回归与本次变更范围一致，无未解决疑点需要重复执行测试；本复审未重跑测试套件。
- 已读取 `docs/qa/android-management/2026-09-24-final-review-fixes/real-mac.json`：status=passed，记录永久删源后恢复检查、九个自建 deviceId，清理结果 containersAndVolumes=0、backups=0。证据是 Mac HTTP/运行时链，不宣称新的页面视觉或长期隐藏会话真机验证。
- 根任务通知 type/lint/OpenAPI/build/迁移6/结构4/脚本95/Ruff/compile 均 exit 0；全仓后台仍在运行，本报告不提前把它们写成最终全仓通过。

## Out-of-Scope Observations

- **真实 Electron 长期隐藏/最小化调度仍未测，非本修复新增缺陷。** 主窗口 backgroundThrottling 仍为已有默认 true；模拟时钟不会经过操作系统/Electron 后台节流。原 I3 的 TanStack 确定性跳过已经修复，但不能由此推定长时间最小化一直满足 5 秒心跳/30 秒租约。根任务继续登记 blocked/not_run；若真实测得心跳被节流超过租约，再依据该证据做有界修复，不在本轮凭推测增加全局节流改动。
- 新维护页面真实桌面视觉与操作、GApps/账号网络链、十实例规模等既有验收缺口保持原状态；不由组件测试或上述真实单链替代。
- 未发现需要新增记录的范围外代码问题。

## Verdict

**Fix round: All findings addressed, no new Critical/Important breakage。** I1–I5 均 ADDRESSED；本轮剩余 Critical=0、Important=0。置信度：高，限上述软件缺陷与修复范围；整体验收仍须由根任务汇总最终全仓结果及真实条件缺口。
