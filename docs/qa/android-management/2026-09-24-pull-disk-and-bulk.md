# 镜像拉取磁盘准入与真实桌面批次验收

日期2026-09-24；状态confirmed局部证据，整体partial。隔离分支codex/android-management-complete；创建/复制/恢复准入仍待Task4，完整仓库最终验证待其集成后执行。不能把本报告视为AM1–AM4整体完成。

## 真实Mac结果

- 镜像固定 `sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b`，Lima ARM64/ReDroid。未确认未知磁盘估计：409、持久failed、`ANDROID_DISK_ESTIMATE_UNKNOWN`、实际Docker pull调用0；原编号重放保持拒绝，改确认位冲突。
- 显式确认后实际pull1次。目录回执后强杀自有服务，HTTP得到RemoteProtocolError；重启后原请求needs_verification，持久列表total1；显式核实后succeeded，列表total0；原编号重放没有第二次pull。原tag未变，仅撤销隔离工作区登记，基础镜像内容保留。
- 原生Electron中，两台自建设备的选择在搜索0/2、清除搜索后保持；启动批次两项succeeded，操作中目标冻结。开始新批次可清空选择并改为停止；立即取消未开始项，第一项继续完成、第二项cancelled，批次partially_failed；终态可再次开始新批次。持久JSON记录与可见UI一致。
- 关闭自己的Electron后清理两台设备，经真实所有权verify查询，容器与卷均不存在。未操作用户设备。

证据：[拉取原始JSON](2026-09-24-pull-disk-and-bulk/real-pull.json)、[桌面逐步观察](2026-09-24-pull-disk-and-bulk/desktop-observations.md)、[持久批次](2026-09-24-pull-disk-and-bulk/real-bulk-durable.json)、[清理结果](2026-09-24-pull-disk-and-bulk/real-bulk-cleanup.json)。

## 命令与实际输出

工作目录为本隔离worktree。

```sh
uv run --project apps/backend python docs/qa/android-management/scripts/image-pull-interruption-smoke.py --allow-image-pull --output /private/tmp/android-pull-disk-real.json
# exit0，status passed；未确认0pull；确认/中断/核实全链1pull。
uv run --project apps/backend python docs/qa/android-management/scripts/desktop-bulk-fixture.py seed --allow-device-mutation --output /private/tmp/android-real-bulk-desktop.json
# exit0，两台seeded_stopped；中间批次操作由真实Electron/CUA执行。
uv run --project apps/backend python docs/qa/android-management/scripts/desktop-bulk-fixture.py cleanup --allow-device-mutation --output /private/tmp/android-real-bulk-desktop.json
# 最终exit0，status cleaned；两台runtimeState missing。
uv run --project apps/backend ruff check docs/qa/android-management/scripts/desktop-bulk-fixture.py docs/qa/android-management/scripts/image-pull-interruption-smoke.py
# exit0，All checks passed!
```

QA脚本首次cleanup对已删除容器调用inspect遇到no such object，已改用现有verify查询容器/卷，重跑通过；产品代码未因该脚本错误修改。最初启动批次在取消前已完成，取消证据来自后续停止批次，未伪造时间线。

## 剩余范围

本轮没有完成创建链磁盘准入、桌面镜像内容删除、下载传输途中断网、完整1/5台桌面交互性能及同版本旧实例升级链。十台受VM容量限制，Google账号/商店/GApps验证缺条件，仍blocked。桌面批次通过不能替代这些项目。Task3产品自动化及审查结果在提交后追加，最终全量结果须对应最终候选源码。

## Task3软件验证（18b75c49）

[实现者报告](2026-09-24-pull-disk-and-bulk/implementation-report.md)保存RED→GREEN与实际命令：Android后端493 passed，最后新增符号链接环边界后受影响四文件142 passed；Android前端14文件184 passed；Ruff、TS类型、lint、OpenAPI及build通过。扩展六文件mypy有22项错误，同命令隔离基线亦22项且错误签名一致；这不是mypy全通过。没有运行最终全仓长套件，统一留到Task4集成后。独立Task3审查进行中。

## 真实桌面持久未知拉取核实

补充真实运行：上述脚本加 `--leave-pending-for-desktop`，执行真实pull并在目录回执后强杀，重启验证needs_verification后退出服务（不篡改数据库）。以该独立workspace启动18b75c49构建的真实Electron：原请求自动显示“待核实”；新引用和确认均填入时“开始拉取”仍禁用；点击原请求“核实拉取”后显示succeeded，待核实总数1→0，新请求重新可提交；修改镜像引用后确认自动重置为未选中。未从UI发起第二次pull。

读取同一持久操作确认 `succeeded/IMAGE_PULL_VERIFIED`；关闭自有Electron后再次启动真实HTTP服务，成功状态保持，撤销本工作区登记，固定基础镜像与tag未改。实际前置worker pull计数1，Electron核实为现有verify路径；没有宣称对Electron全部Docker命令单独做了计数。证据：[中断后](2026-09-24-pull-disk-and-bulk/desktop-pull-pending.json)、[桌面核实与清理](2026-09-24-pull-disk-and-bulk/desktop-pull-verified.json)。此证据关闭未知拉取桌面重启核实项，不覆盖下载进行中断网/内容删除。

独立审查round1指出202/failed重放被UI误报已接受，已由c4b6159d修复；三项有效RED，组件20及Android前端187项、类型/lint通过，等待最小复审。本次真实Electron使用修复前18b75c49构建，只验证其成功核实路径；失败提示修复的证据为组件回归，最终构建由后续统一验证。

独立最小复审已通过，Task3无剩余Critical/Important，见[审查记录](2026-09-24-pull-disk-and-bulk/review.md)。最终全分支审查留到创建链集成后。
