# Android 批量 UI 续行

- 日期：2026-09-24；状态：partial；来源：生产代码、真实专用 Mac 实例、Vitest 和工程门禁。
- 已完成：断线保留选择但禁用写操作；活跃批次 GET 进度、读取失败重试读取、终态停止、卸载中止；独立复审无 Critical/Important。
- 验证：Android 150 passed，类型/lint/OpenAPI/build exit 0；完整命令及真实证据见[报告](../../docs/qa/android-management/2026-09-24-bulk-stale-snapshot.md)。
- blocked：Mac 锁屏阻塞最终 UI 自动终态，已请求手动解锁；自有客户端/sidecar 已退出，自建设备已由生产 HTTP 删除并核实 missing。没有以 mock 宣称真实通过。
- 下一有界切片：复用 cancelPending 接口，仅取消 queued/waiting_capacity/waiting_device；冻结动作 requestId，传输失败重试原动作，不退回重提原批次；未知/运行中禁止新批次，已确认终态才可重置表单并使用新请求；RED→GREEN、后端现有契约/幂等回归、前端及工程门禁、独立复审、真实桌面验收。
- 依赖冲突：无新 schema/契约依赖；与当前 BulkActions 文件相邻，先提交已验证修复再继续。保留三份 Studio 既有改动，main worktree 不动。

## 取消与新批次续行

- 状态：partial；来源：[本轮代码/测试/真实HTTP报告](../../docs/qa/android-management/2026-09-24-bulk-actions.md)。上方下一切片中的软件工作已实施，不代表真实UI已通过。
- 6个源码/测试文件完成前后端增量；取消动作原编号重试，确认终态后新批次才取新revision；筛选零匹配保留批次，不允许首次提交空目标。
- 审查发现并修复容量异步/跨批次读取/核实异步的取消覆盖，真实SQLite+Event有效RED；最终审查无Critical/Important。
- 前端160项、后端47项聚焦通过；真实8192MiB停机实例容量拒绝、取消、HTTP重启原编号回执一致，资源清理missing。最终全量后端4048passed/26skipped/2warnings、前端424文件/5650项及工程门禁通过，上一轮源码变更后主动中止并保留exit130记录。
- 剩余：解锁后的真实取消/新批次/自动终态；T14隐藏页进度读取暂停与性能/探测指标；T09镜像桌面链；T12向前回退演练；最终全分支回归。目标仍active。

## T14 隐藏页续行（2026-09-24，in_progress）

- 基线33e7f547；上轮为progress，源代码/测试/真实HTTP/完整门禁均有新增证据。Mac锁屏阻塞延续，但存在独立软件工作，不将目标标blocked。
- AM-R12要求隐藏页暂停展示轮询。ManagementOverview由React Query提供默认后台暂停；DevicePreview已有可见性/视口门控；新增BulkActions手写轮询缺少隐藏状态门控。
- 有界计划：真实组件+假时钟先证明hidden期间不发起新GET、visible恢复读取且不重提动作；最小修复仅门控新读取，既有在途只读响应可完成，控制会话心跳与后端观察器不受影响。然后检查后端观察器与1/5台探测计数的真实证据；桌面交互延迟仍需解锁。
- 不改schema/契约、不新增依赖。候选范围仅BulkActions和既有测试；Studio改动不纳入。

- 2026-09-24 隐藏页与观察增量（confirmed 软件/真实后端，整体partial）：批次状态GET隐藏时暂停、可见恢复，一行修复经RED 1 failed→GREEN 69 passed；1/5台真实API P95为6.177/12.495ms，列表内inspect均0，后台间隔3.23–3.34/4.15–4.21秒，停机约15.8秒；5台自建资源均核实missing。Mac锁屏继续阻塞桌面隐藏页/前台/新批次入口，十台及GApps条件未变。完整前端424文件/5651项（722.44s）及类型/lint/OpenAPI/build全部exit0；结构4/脚本95/迁移6项通过，当前102步骤85passed/14not_run/3blocked不虚增。见[完整证据](../../docs/qa/android-management/2026-09-24-observation.md)。

- 2026-09-24 规格复核修复（confirmed软件定向，真实桌面blocked）：原T13.4逐项结果证据范围过宽，本轮直接渲染冻结result.items的全部状态/错误/重试来源，accepted不再误报未知但继续冻结；镜像未知拉取补现有POST核实、原编号重试及A成功/B响应丢失的身份栅栏。4项初始RED加1项连续请求RED后，Android166项/类型/lint通过，最终增量复审无Critical/Important；完整前端424文件/5656项通过（750.46s），类型/lint/OpenAPI/build均exit0，真实UI仍受Mac锁屏阻塞。见[实际证据](../../docs/qa/android-management/2026-09-24-item-results-image-recovery.md)。
