# AM1 控制会话与详情入口增量验收

- 日期：2026-09-23；状态：`confirmed`（本增量），AM1 T05–T07 仍 `partial`。
- 来源：规格 AM-R01/R05、AM-AC01/05/06 与隔离分支 `codex/android-management-complete`；本次无 API、OpenAPI 类型或数据库迁移变化。

生产页面原有三处行为与独立管理目标不符：用户返回列表后，慢速 `POST /sessions` 回应仍会写入会话；详情页排队的输入在会话关闭后继续发送，并可能用旧响应覆盖状态；手动详情仍显示“分配给工作流”按钮，尽管点击回调无实际动作。独立 `ConsoleController` 的单测已有旧响应保护，但生产 `AndroidPage`/`DeviceConsole` 没有使用它，因此这些单测不能证明页面安全。独立审查又发现卸载、后端重连、结束结果未知、复制配置及旧 `/runs` 查询的详情边界。

按 RED→GREEN 分别验证：

| 行为 | RED（Node 22.23.2） | GREEN |
| --- | --- | --- |
| 返回列表后的迟到打开响应必须结束其会话 | `AndroidPage.test.tsx`：`1 failed, 14 passed`，缺少 `end` 请求 | 打开请求绑定页面 epoch；返回时使其失效，迟到回应按原会话结束，确认 `closed` 后才丢弃请求 ID；`15 passed`。 |
| 关闭会话后不再发排队输入或发布旧结果 | `DeviceConsoleApps.test.tsx`：`1 failed, 7 passed`，实际发送了第二条旧输入 | 发送前、响应后和错误处理均核对同一会话身份；队列中的旧输入丢弃。 |
| 独立详情不出现退役的工作流分配入口 | `AndroidPage.test.tsx`：`1 failed, 15 passed`，找到禁用的“分配给工作流”按钮 | 删除该区块和无效回调；保留兼容数据展示，不启用旧执行链。 |
| 打开未完成就返回，结束失败需保留核实入口 | 审查增量 `6 failed, 14 passed` 中的可见状态断言失败 | 打开未决时留在详情；迟到响应的 `end` 失败显示 `unknown`，允许重试，确认 `closed` 后才切页。 |
| 卸载或同工作区重连不可接纳旧会话 | 同上：卸载/跨 `instanceId` 的迟到响应无 `end`；已连接会话卸载增量 `1 failed, 20 passed` | 卸载与后端身份变化使 epoch 失效；用原后端客户端尽力结束旧会话；旧响应不能写入新后端状态。 |
| 复制配置不得绕过结束门 | 同上：结束请求未返回时创建表单已显示 | 返回列表与复制配置共用关闭确认门；失败保留详情和未知会话。 |
| 详情不得轮询退役的工作流运行记录 | 同上：仍有“运行记录”标签和 `/devices/{id}/runs` 请求 | 移除旧标签及查询；管理操作历史的可见列表仍待接入，后端查询契约已存在。 |
| 打开被明确拒绝不能困在详情 | `1 failed, 21 passed`：`ANDROID_CONSOLE_BUSY` 后返回仍要求重试 | 只对白名单内、服务端明确未创建会话的错误清除 `pendingOpen`；断线或超时继续复用原请求编号。 |
| 原生窗口留在列表，第二台打开不结束第一台 | native 竞态 `2 failed, 22 passed`；列表归属与重挂载 `2 failed, 32 passed`；双设备 `1 failed, 27 skipped` | 管理快照的 `manualSession/owner.id` 提供查看与显式结束；路由重挂载通过 `GET /sessions/{id}` 取回；打开另一台只收尾旧嵌入式控制。 |
| 页面导航与服务端回收 | 受控路由守卫 `1 failed`；回收后核实 `2 failed, 28 skipped` | 顶栏 hash 导航经现有 guard；嵌入式 `end` 未确认则留详情；服务端回收后，须同 ID 会话 `closed`/明确 `410` 且新管理快照显示旧归属释放，才允许离开。 |

最终三份聚焦测试 `3 files, 47 passed`；详情页测试单独 `30 passed`。指定 Node 22.23.2 下，从仓库根执行最终 `npm test` 为 `424 files, 5613 passed in 248.83s`；`npm run test:scripts` 为 `95 passed`；`npm run test:structure` 为 `4 passed`；`npm run typecheck`、`npm run lint`、`npm run openapi:check` 均 exit 0；`npm run build` 为 `built in 51.57s`。RED 日志分别为 `/tmp/android-am1-late-open-red.log`、`/tmp/android-am1-stale-input-red.log`、`/tmp/android-am1-workflow-detail-red.log`、`/tmp/android-am1-review-red.log`、`/tmp/android-am1-connected-unmount-red.log`、`/tmp/android-am1-known-failure-red.log`、`/tmp/android-am1-native-race-red2.log`、`/tmp/android-am1-native-list-red.log`、`/tmp/android-am1-route-guard-red.log`、`/tmp/android-am1-two-native-red.log`、`/tmp/android-am1-lease-red.log`；GREEN 见 `/tmp/android-am1-lease-current-targeted.log` 与 `/tmp/android-am1-verified-full-frontend.log`。脚本测试会重写三份既有 Studio 目录文档，运行前已备份、退出时已恢复，三份 SHA-256 与本轮开始时一致；另一个脚本改动的 `capabilities.json` 在运行前为 clean，已恢复到 HEAD。均未纳入安卓提交。后端生产代码与 OpenAPI 契约均未改动；前一增量的后端全量 `3964 passed, 26 skipped` 仍适用于后端。独立只读复审本前端增量：Critical 0、Important 0。

现有原生 scrcpy 进程真机证据见[持久数据属性增量](2026-09-23-persistent-metadata-verification.md)；人工输入/页面与原生切换、30 秒失联、完整 AutoFlow 重启和受控中断仍未真机验收。受控顶栏导航遇到结束结果未知会留在详情待核实；强制卸载、工作区切换或应用关闭的端到端链仍未实测，当前没有跨页面的未知会话队列，依赖后端关闭协调和租约回收。软件竞态修复的 mock 网络边界测试不冒充真实输入链。
