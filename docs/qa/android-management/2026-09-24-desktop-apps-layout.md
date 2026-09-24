# 桌面应用确认与精确窗口布局验收

- 日期：2026-09-24；状态：`passed`（本轮有界修复及验收）。基线 `b89ea597`，隔离分支 `codex/android-management-complete`；三个 Studio 脏文件保留原哈希。
- 归档文本仅去除行尾空白和文件尾多余空行；截图、结果内容与数值未改。
- 来源：真实 macOS Electron / Lima / ReDroid、只读运行时核实、Vitest 和原生 DevTools 布局断言。未使用 mock 冒充桌面验收。
- 测试设备：`3d819343-8b92-4e66-9db1-4dfd468b54c5`；包 `moe.shizuku.privileged.api`，versionCode 1086。备份 `6bd56bb0-1b06-4b8e-8e61-53618812c183` 已经生产 HTTP 恢复为另一实例并读回应用探针，再删除该恢复目标；见[准备结果](2026-09-24-desktop-apps-layout/preparation.json)。原测试设备、卸载后恢复目标与备份均已完成本轮最终清理。

## 真实失败与修复

1. 创建页 `1440×900`、200%：有效视口 708px，内容 971px，预览右边界 958px；窄屏规则强制最小 580px + 340px 双栏。先新增[真实渲染断言](scripts/create-layout-check.js)，[RED](2026-09-24-desktop-apps-layout/create-layout-red.txt) 与[截图](2026-09-24-desktop-apps-layout/create-1440-200-before.png)一致。创建页在窄视口使用单栏，表单两列，页脚回归文档流并换行。
2. 同一断言继续发现 `1280×800`、100% 预览文字不换行，内容 1280px 超过视口 1268px。修复定义列表最小宽度与文字换行；临时注入 CSS 已移除，最终构建真实四组合全部通过：[创建布局](2026-09-24-desktop-apps-layout/create-layout-final-green.txt)，16 个控件/预览/字段组均无水平越界。
3. 长设备名详情标题的子内容底边 226.09375px，标签顶边 193px，真实重叠。先新增[详情渲染断言](scripts/detail-layout-check.js)，[RED](2026-09-24-desktop-apps-layout/detail-layout-red.txt)；固定高度改最小高度，标题与状态可换行；[最终构建四组合](2026-09-24-desktop-apps-layout/detail-layout-final-green.txt)均通过。坐标为页面滚动位置，不据此代替整页截图。
4. 清除/卸载确认使用内联 `aria-modal`，焦点仍停在背景按钮，Tab 到背景卸载。真实[焦点记录](2026-09-24-desktop-apps-layout/clear-dialog-focus-before.txt)；新增测试先 2 failed/17 skipped，再复用共享 Dialog，取消初始焦点、焦点圈定、Escape 恢复触发器；面板 19 passed。
5. 独立增量审查发现未知结果会禁用原触发器，关闭对话框无法恢复焦点。新测试先失败，增加触发器仍连接且未禁用检查，否则回到应用搜索框。该次面板/控制组件/页面定向 64 passed；审查复核无剩余 Critical/Important。审查未操作设备，真实布局与全量验证由主代理负责。
6. 实际卸载后，异步列表刷新移除原触发器，焦点落回页面根；另有“提交→Escape→请求完成”的变体。分别先得到 [RED](2026-09-24-desktop-apps-layout/uninstall-focus-red.log) 和 [deferred RED](2026-09-24-desktop-apps-layout/uninstall-pending-red.log)。前置校验通过后、卸载请求发出前清空恢复目标，使关闭返回稳定搜索框。未提交取消仍回原按钮；[22 项 GREEN](2026-09-24-desktop-apps-layout/uninstall-pending-green.log)，独立审查最终无 Critical/Important。

## 真实应用动作与恢复

- 搜索、启动、停止真实执行，客体启动进程 PID1242，停止后无进程且探针保留。
- 最终共享 Dialog 初始焦点为取消，Shift+Tab/Tab 圈定在确认框，Escape 回到触发按钮；取消清除后探针未变且无清除回执。
- 实际确认清除后 UI 显示“应用数据已清除”，持久回执 succeeded，包保留而探针 absent；[读回](2026-09-24-desktop-apps-layout/app-clear.json)。
- 实际卸载后 UI 显示“应用已卸载”、列表无匹配，回执 succeeded、客体 pm path 为空；[读回](2026-09-24-desktop-apps-layout/app-uninstall.json)。此轮暴露的焦点缺陷单独记录并修复，不把动作成功扩写为焦点通过。
- 系统 launcher3 显示“受保护应用”，清除/卸载均 disabled。
- 卸载后从原备份经完整 HTTP 恢复新实例 `df7fd086-a8cb-5e14-8ab1-3922db919248`，启动后包与原探针内容均恢复：[恢复读回](2026-09-24-desktop-apps-layout/post-uninstall-recovery.json)。

## 后端不可达与恢复

仅暂停本轮独立 sidecar PID79857，执行前核对 PID/birth/父 PID/数据目录和设备无控制占用；finally 再校验同一进程并 SIGCONT。没有关闭 Mac 网络或其他后端。

首次 55 秒不足以覆盖 20 秒请求加两次查询重试，页面尚未进入终态错误，不计通过。第二次暂停 90 秒，在暂停期间捕获“设备状态无法核实”“快照陈旧”，实例保留，打开/停止/删除禁用；恢复后同一实例快照有效、操作恢复。见[暂停身份与时间](2026-09-24-desktop-apps-layout/backend-pause-90.json)、[旧快照保护](2026-09-24-desktop-apps-layout/backend-paused-90-state.txt)、[恢复状态](2026-09-24-desktop-apps-layout/backend-resumed-state.txt)。全局“本地服务正常”仍未同步显示不可达，Android 页已有明确错误。已读代码确认：`useDesktopSession` 初始连接做HTTP健康检查，之后轮询主进程runtime快照；暂停但未退出的进程仍为ready，普通请求超时也不改变全局status。此为全局健康显示的范围外风险，不据此声称持续HTTP健康监测通过。

最终构建真实复验：恢复目标上确认卸载后立即 Escape，应用仍在列表时焦点已经回搜索框；请求成功、应用行消失后仍聚焦搜索框。[提交时焦点](2026-09-24-desktop-apps-layout/uninstall-final-submit-escape.txt)、[最终焦点](2026-09-24-desktop-apps-layout/uninstall-final-focus-green.txt)、[运行时/回执](2026-09-24-desktop-apps-layout/uninstall-final-readback.json)一致。

## 资源清理

[清理结果](2026-09-24-desktop-apps-layout/cleanup.json)：两个剩余自建实例均通过公开delete操作并核实容器/数据卷missing；备份以预览指纹确认，结果succeeded、目录无该ID。首次恢复目标已在准备阶段清理，合计三个自建设备全部收尾。最终控制会话已结束，Electron和sidecar已退出；Chrome仅删除本轮新增127.0.0.1:60363，原localhost:9222/9229及端口转发设置保持。

## 自动验证记录

- Node22 `npm run test --workspace @autoflow/desktop -- src/renderer/domains/android/tests/ApplicationsPanel.test.tsx src/renderer/domains/android/tests/DeviceConsoleApps.test.tsx src/renderer/domains/android/tests/AndroidPage.test.tsx`：3 files / 64 passed，28.65s，见[GREEN](2026-09-24-desktop-apps-layout/focus-green.log)。
- 最终源码的类型、lint、OpenAPI、构建均 exit0，renderer构建38.60s；[完整日志](2026-09-24-desktop-apps-layout/final-gates.log)。构建产物已核对卸载请求前清除焦点目标，实际Electron复验通过。无新增后端逻辑、依赖或schema；本轮不重复无变更的后端全量。
- 第一次全量前端与构建并行，发生六项失败，后因新修复加入而显式中止，exit130，不能计全量通过。原始[日志](2026-09-24-desktop-apps-layout/superseded-full-run.log)保留：settings integration 60s、DataTableDetailPage conflict reload、navigation-config-entry switch_tab、EnvironmentFields custom input、recorder-review 100 rows、AutomationDetailPage normalized payload。
- 上述六个文件在减少并发后独立重跑：6 files / 83 passed，35.10s。未放宽断言或超时，资源竞争是待验证解释，不能据重跑通过声称已查明所有超时根因。第二次四 worker 全量结果为 423 files passed / 1 failed，5632 passed / 2 failed（617.43s）：DataTableDetailPage 的筛选步骤超过 5000ms，其后的详情按钮查询失败；[原始输出](2026-09-24-desktop-apps-layout/full-parallel-failed.log)。最终使用相同断言与超时、单 worker 完整重跑：424 files / 5636 passed，824.25s，exit0；[原始输出](2026-09-24-desktop-apps-layout/full-serial-green.log)。未修改测试超时或跳过用例。四worker超时的根因仍未完全定位，保留测试稳定性风险，不宣称默认并发配置本轮通过。

## 命令与范围

- `npm exec --offline --yes --package=node@22.23.2 -c 'npm run typecheck && npm run lint && npm run openapi:check && npm run build'`：exit0。
- `npm exec --offline --yes --package=node@22.23.2 -c 'npm run test --workspace @autoflow/desktop -- --maxWorkers=1'`：424 files / 5636 passed，824.25s，exit0。
- 真实UI由CUA操作；窗口尺寸与zoom通过本轮Electron原生DevTools设置，执行两个仓库内只读布局断言；没有mock HTTP或客体状态。
- 真实读取使用项目`MacAndroidRuntime.docker`的`pm path`、`pidof`、`cat`，并只读SQLite原请求回执。准备/恢复/清理均调用生产HTTP，结果JSON附资源ID与摘要。
- [迁移/保护校验](2026-09-24-desktop-apps-layout/baseline-check.json)：唯一head `am01_management_operations`，父`0019_recording_commands`；三个Studio哈希不变。`git diff --check`通过；最终9份文档290个本地链接存在。

## 剩余范围

本报告不关闭整个目标。T06.4已有真实证据，步骤统计85passed/14not_run/3blocked。T09镜像桌面内容删除/拉取中断核实、T12阶段回退、T14/T16后台探测与前台指标、T20最终全分支验证仍待完成。下一增量补查批量面板在父级快照读取失败后是否同步禁写；本轮真实断线仅直接验证单实例操作。历史RED缺证未追认，十台容量与GApps镜像/账号链仍blocked。
