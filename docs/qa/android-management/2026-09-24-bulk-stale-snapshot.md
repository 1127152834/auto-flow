# 批量面板断线保护与进度读取

- 日期：2026-09-24；状态：partial。基线 `ddf8e283`。本轮实现和自动化通过；最终构建的批量停止桌面验证被 macOS 锁屏阻塞，未计为通过。
- 根因一：ManagementOverview 查询失败后保留旧快照，单卡动作已禁用，但批量面板未继承 staleSnapshot。改为原生 `fieldset disabled`，保留选择、冻结请求与回执，成功刷新恢复。
- 根因二：BulkActions 只保留提交响应，没有读取后续状态。真实启动已 succeeded 且设备 ready，页面仍 running，见[真实失败现场](2026-09-24-bulk-stale-snapshot/after-start-ui.txt)。复用现有 GET 批次接口，每次读取完成后间隔 3 秒继续；终态停止，离页取消并忽略迟到响应，读取失败仅重试读取。没有隐式重提、核实或失败项重试。
- 没有后端、OpenAPI 或 schema 变更。独立只读复审无 Critical/Important；完整目标仍未完成。

## RED → GREEN

| 验证 | 实际输出 |
| --- | --- |
| 已选目标后查询失败必须禁用批量入口 | [RED](2026-09-24-bulk-stale-snapshot/red.log)：1 failed / 17 skipped；修复后 [GREEN](2026-09-24-bulk-stale-snapshot/green.log)：3 文件 / 79 passed，7.72s |
| 活跃进度读取、未知结果停止、卸载中止 | [RED](2026-09-24-bulk-stale-snapshot/progress-red.log)：3 failed / 26 skipped；[GREEN](2026-09-24-bulk-stale-snapshot/progress-green.log)：3 文件 / 82 passed，6.37s |
| 最终 Android 域与工程门禁 | [输出](2026-09-24-bulk-stale-snapshot/final-gates.log)：150 passed，9.28s；typecheck、lint、OpenAPI、build 全部 exit 0；renderer build 37.76s |

命令（隔离 Node 22.23.2）：

```sh
npm exec --offline --yes --package=node@22.23.2 -c 'npm run test --workspace @autoflow/desktop -- src/renderer/domains/android && npm run typecheck && npm run lint && npm run openapi:check && npm run build'
```

定向 RED/GREEN 使用同一 Node 运行 ManagementOverview、ManagementTools、AndroidPage；RED 以测试名称过滤。最初 fake timers 配合 userEvent 的测试夹具超时在生产改动前修正，随后才获得上述有效断言失败。文本日志仅裁剪行尾空白与多余末尾空行，没有删除失败内容。基线完整前端 424 文件 / 5636 项通过，不冒充本轮源码的全量结果。

## 真实 Mac 证据

1. [准备记录](2026-09-24-bulk-stale-snapshot/preparation.json)：专用 QA profile 自建实例 `34e87958-33c6-4a1f-a787-7693deadaa03`，公开 revision=3 时停止。
2. [已选目标](2026-09-24-bulk-stale-snapshot/selected-before-pause.txt)后，仅暂停身份已核对的自有 sidecar 90 秒。[断线界面](2026-09-24-bulk-stale-snapshot/paused-disabled.txt)和[截图](2026-09-24-bulk-stale-snapshot/paused-disabled.png)显示 checkbox 仍勾选但所有批量入口禁用；[恢复界面](2026-09-24-bulk-stale-snapshot/resumed-enabled.txt)恢复可操作且保留选择。
3. 恢复后点击批量启动，生产持久回执 [submitted-batch.json](2026-09-24-bulk-stale-snapshot/submitted-batch.json) 为 succeeded，expectedRevision=3，设备 ready / revision=4。创建时间晚于 sidecar 恢复，见[时间线](2026-09-24-bulk-stale-snapshot/bulk-timeline.json)。
4. 审计纠正：最初查 legacy kind=`batch` 的 [paused-no-batch.json](2026-09-24-bulk-stale-snapshot/paused-no-batch.json)已标 invalidated，不作为暂停期间无提交证据；实际 kind=`bulk` 的最终时间线替代它。
5. 新进度代码最终构建已启动专用 Electron，但 CUA 返回“The Mac is locked and automatic unlock could not unlock it”。已请求手动解锁。最后的真实 UI 自动收敛仍为 `blocked`；不能以组件测试代替。客户端已按精确命令身份发送 SIGTERM 并正常 exit 0，随后生产 HTTP 完成清理。

## 剩余与资源

- 自建实例已通过生产 HTTP 删除，运行时容器/卷核实为 `missing`，见[清理结果](2026-09-24-bulk-stale-snapshot/cleanup.json)。未打开控制会话、未装 APK、无本轮备份；自有 Electron/sidecar 已退出。专用 profile `/private/tmp/autoflow-android-desktop-qa-20260924` 保留验收记录，解锁后需重建自有 fixture 完成 UI 验证。
- 新发现 AM-R11 的“取消未准入项”已有后端接口但前端缺入口；终态后也缺开始下一批入口，列入下一有界切片。原 T13 的后端验收通过不代表这些 UI 功能已完成。
- 全量分支门禁与审查仍须在所有增量结束后重跑；不追认历史 RED，也不关闭 GApps/十实例阻塞。
