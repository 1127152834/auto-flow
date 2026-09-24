# 安卓模拟器管理 24 项验收校准

- 日期：2026-09-23；状态：`partial`；来源：[需求规格第 8 节](../../superpowers/specs/2026-09-19-android-emulator-management-design.md)与本目录实际测试/真机记录。
- 基线：隔离分支 `codex/android-management-complete`。`passed` 仅表示该验收项已有相应自动化或真实证据；`partial` 表示实现/证据尚未覆盖完整场景；`blocked` 仅用于明确缺少外部条件。自动化、真实 Mac 和网络/账号证据分别列出，不互相代替。

| 验收 | 状态 | 已有证据与缺口 |
| --- | --- | --- |
| AM-AC01 | `partial` | Android 管理页已停止旧设备列表和详情 `/runs` 轮询，移除退役分配/运行记录入口；[隔离桌面真机链](2026-09-23-desktop-ui-verification.md)从安卓页创建、启动、停止、恢复实例，页面能力明确不通过工作流执行入口。其他模块未专项验收。 |
| AM-AC02 | `passed`（自动化） | 环境缺失/超时/不支持的只读契约测试；真实 Mac 环境 `available=true`，见 [AM1](am1-verification.md)。 |
| AM-AC03 | `passed`（自动化） | 状态规则和前端状态测试覆盖 stop/delete/recover/unknown，见 [AM1](am1-verification.md)。 |
| AM-AC04 | `passed`（自动化） | 持久操作幂等、冲突、generation、紧凑回执与同事务设备投影测试；[操作历史页面](2026-09-23-operation-history-verification.md)可按设备翻页并用原请求编号核实，见 [AM1](am1-verification.md)。 |
| AM-AC05 | `passed`（真实与自动化） | [真实控制链](2026-09-23-am1-real-control-retention.md)覆盖输入、返回/重进、30 秒无心跳回收、HTTP 重启旧会话 410 与新会话可用；[页面竞态](2026-09-23-control-session-verification.md)覆盖旧队列。[真实桌面控制](2026-09-24-desktop-control.md)补受控SSH/ADB断线、输入锁定、可核实清理、重连与嵌入离页释放。 |
| AM-AC06 | `passed`（真实与自动化） | [真实控制链](2026-09-23-am1-real-control-retention.md)覆盖嵌入式→原生→嵌入式单写端切换，原生窗口实际出画面；[最终桌面构建](2026-09-24-desktop-control.md)实际验证离开安卓模块仍保留原生进程，返回切回嵌入时关闭原生，generation推进且输入可用。 |
| AM-AC07 | `passed`（自动化） | 旧 generation、重复 sequence、跨工作区 heartbeat 拒绝测试，见 [AM1](am1-verification.md)。 |
| AM-AC08 | `passed`（真实与自动化） | [同一自建实例](2026-09-23-am1-real-control-retention.md)写探针→停机/启动读回→移除容器保留卷→明确 `restore` 重建后同卷读回；缺卷回归返回 `ANDROID_DATA_MISSING` 且无新卷写入。 |
| AM-AC09 | `passed`（真实与自动化） | [真实双实例隔离](2026-09-23-am1-real-control-retention.md)已核实第二台自建实例独立容器/卷，永久删除第二台后第一台仍 `ready` 且原容器/卷身份不变；另有不同 ADB serial、资源标签及丢响应 `needs_verification` 自动化。外部资源未纳入删除目标。 |
| AM-AC10 | `passed`（真实与自动化） | 默认单台/模板/空态已有自动化；[精确窗口与焦点](2026-09-24-desktop-apps-layout.md)在1280×800及1440×900、100%/200%完成真实布局断言，修复长名重叠和表单水平溢出；历史面板/应用确认键盘焦点已验。真实sidecar不可达保留旧数据并禁用操作，恢复后重新可用。 |
| AM-AC11 | `partial` | tag 漂移/固定 imageId/引用阻删集成通过；[隔离桌面真机链](2026-09-23-desktop-ui-verification.md)完成固定摘要镜像登记；[AM2 本机实验](am2-verification.md)通过生产 Mac/Lima 和认证 HTTP 对自建 ARM64 镜像登记、按摘要删除和实际不存在确认，固定摘要官方仓库网络拉取返回相同 imageId/sourceDigest 且原 tag 未变。[审查修复](2026-09-23-final-review-remediation.md)补备份引用保护与每次拉取独立持久回执；[可启动候选镜像](2026-09-24-custom-image.md)补固定ID、模板/tag漂移重启、备份恢复与三类引用阻删直接证据；桌面内容删除及真实断线核实仍未验收。 |
| AM-AC12 | `passed`（自动化） | 模板 revision 冲突及已有实例配置快照不变集成，见 [AM2](am2-verification.md)。 |
| AM-AC13 | `passed`（自动化） | [审查修复](2026-09-23-final-review-remediation.md)使镜像元数据核验与 `validation` 谷歌验收单列，缺六项时不报通过，界面也分别标示；见 [GApps](gapps-validation.md)。 |
| AM-AC14 | `blocked` | 无专用候选镜像、测试账号和商店下载链；登录/下载/重启/隔离均 `not_tested`，见 [GApps](gapps-validation.md)。 |
| AM-AC15 | `passed`（真实与自动化） | 批次部分失败/取消/重试规则与 UI 自动化存在；[真实双实例批量链](2026-09-23-am3-real-bulk-verification.md)及[五实例规模链](2026-09-23-final-review-remediation.md)完成 start/stop/delete。[真实失败、重试与取消](2026-09-24-bulk-failure-cancel.md)在最新修订号规则下重跑，两台批次先 `[succeeded, failed]`，对修订冲突项显式 `retryFailed` 后 `[succeeded, succeeded]`，容量等待可 `cancelPending`。[最终审查](2026-09-24-final-branch-review.md)补容量 await 后与持锁版本栅栏、运行时失败重试再冻结；[真实容器消失及回执前 SIGKILL](2026-09-24-bulk-runtime-fault.md)已验证恢复后重试、未知项不得重试、重启后显式核实和数据保留。 新校准：[批次取消与竞态保护](2026-09-24-bulk-actions.md)补前端取消/新批次/空筛选保护与后端并发取消持久性，160项前端/47项后端聚焦通过，真实HTTP取消后重启原编号回执保持cancelled并清理missing；[真实Electron增量](2026-09-24-pull-disk-and-bulk.md)已补筛选保留选择、冻结目标、取消未开始项和终态新批次，真实持久记录一致，自建容器/卷已清理。 |
| AM-AC16 | `passed`（自动化及真实容量实验） | 持久预留、未知预算拒绝、stop 丢响应后核实释放，见 [容量实测](2026-09-23-capacity-verification.md)。 |
| AM-AC17 | `partial`；十台本机 `blocked` | 聚合快照、陈旧规则及可见预览自动化通过；[五实例真实规模链](2026-09-23-final-review-remediation.md)20 次认证 HTTP 快照 `median=2.13ms`、`p95=2.74ms`，两台并发预览返回 PNG，五台 Docker 内存实测并全部清理。[容量实测](2026-09-24-advanced-logs-and-capacity.md)显示本机 Lima 7921 MiB，十台最低配置加安全预留需 8192 MiB；桌面前台交互指标尚未实测。 |
| AM-AC18 | `passed`（真实与自动化） | APK 大小/Manifest/split、未知结果和保护包自动化；[真实自建实例](2026-09-23-am1-real-control-retention.md)已完成安装包/版本核实、启动、停止、清数据、卸载；[最终审查及真实跨重建核实](2026-09-24-final-branch-review.md)用 Shizuku `versionCode=1086` 的完成标记重建控制台，按原回执核实成功并恢复控制，无需旧 ADB tunnel。[真实覆盖安装中断](2026-09-24-app-interruption.md)已验ADB断线/HTTP进程树SIGKILL，重启保持待核实、原应用数据及versionCode1086不变；[桌面确认与备份恢复](2026-09-24-desktop-apps-layout.md)补取消、焦点圈定、保护包禁用、真实清除/卸载及恢复读回，最终卸载列表刷新后焦点仍在搜索框。 |
| AM-AC19 | `passed`（真实与自动化） | 运行中/占用拒绝回归通过；[真实私有磁盘 ENOSPC 与归档传输中取消](2026-09-24-backup-failure-verification.md)分别留下 failed / needs_verification，均无成功备份及 staging，原请求重放被拒，源探针读回一致。此项按规格“运行中禁备份、磁盘不足/取消不发布成功”验收；随后[传输中 SIGKILL、恢复目标 ENOSPC/取消](2026-09-24-restore-cancel-and-disk-full.md)亦通过。 |
| AM-AC20 | `passed`（真实与自动化） | [真实恢复](2026-09-23-persistent-metadata-verification.md)覆盖新 ID/卷、1792 持久条目及启动读回；[写入后发布前 SIGKILL](2026-09-23-restore-hard-interruption-verification.md)后隔离与新请求恢复通过。[审查修复](2026-09-23-final-review-remediation.md)加入自定义镜像固定 ID 核实和文件流真实读回。[真实解包在途中 SIGKILL](2026-09-24-restore-transfer-interruption.md)已补，重启隔离、拦截和新请求恢复通过；[真实损坏归档](2026-09-24-restore-cancel-and-disk-full.md)也返回409且目标卷为空；镜像不符/越界拒绝为自动化，[真实目标 ENOSPC 和请求任务取消](2026-09-24-restore-cancel-and-disk-full.md)已补，源/目标数据与源备份文件摘要均核对。 |
| AM-AC21 | `passed`（真实与自动化） | 预览后指纹/引用变化 409、外部路径/标签保护及真实 HTTP 清理见[清理验收](2026-09-23-cleanup-verification.md)。[最终审查](2026-09-24-final-branch-review.md)补异步设备删除后的父 Operation 汇合与多候选部分落盘不得假成功；[真实多对象硬中断](2026-09-24-cleanup-interruption.md)后保持待核实，未执行对象不被自动重放删除；显式新预览可继续。 |
| AM-AC22 | `passed`（自动化及真实高级日志） | 默认诊断字段白名单排除输入、账号、原始日志、截图和数据；受限 IPC 本地保存且无自动上传。[高级日志实测](2026-09-24-advanced-logs-and-capacity.md)补单次确认、归属校验、5 分钟/64 KiB/200 行边界；真实 ReDroid 返回 196 条仅含时间与级别的元数据，消息/tag 均不导出。 |
| AM-AC23 | `passed`（软件门禁） | 最新[磁盘观测候选完整门禁](2026-09-24-disk-observation.md)：后端4069passed/26skipped，Node22前端424文件/5670项，类型/lint/OpenAPI/结构4/脚本95/build与迁移6项通过。下列数字为历史快照。 Alembic 唯一 head `am01_management_operations`，未改旧迁移字节；[最终完整门槛](2026-09-24-final-full-gates.md)后端本轮[命令树修复后全量](2026-09-24-restore-cancel-and-disk-full.md) `4035 passed/26 skipped`、Node 22 前端其后在[说明增量](2026-09-24-backup-failure-verification.md)重跑 `424` 文件/`5626` 项通过，Ruff、编译、类型、lint、OpenAPI、构建、脚本和结构均 exit 0。最新[桌面布局/焦点增量](2026-09-24-desktop-apps-layout.md)类型/lint/OpenAPI/构建通过，完整前端单worker 424文件/5636项通过（824.25s）；默认四worker本轮两项失败保留，稳定性风险未抹去。此项仅指软件门禁，不代替其他验收项的真机缺口。 最新[批次增量](2026-09-24-bulk-actions.md)完整后端4048passed/26skipped/2warnings（981.16s），Node22前端424文件/5650项（802.11s）及Ruff/compileall/类型/lint/OpenAPI/build均exit0。 |
| AM-AC24 | `partial` | 四阶段 QA 与真机/自动化/外部条件分列；[最终只读全分支审查](2026-09-24-final-branch-review.md)已修复当时报告的问题；最新快速验收发现 AM-R12 创建/拉取磁盘准入仍为 Important，尚未关闭；[最终完整软件门槛](2026-09-24-final-full-gates.md)通过。十台规模、完整故障矩阵及外部 GApps 条件尚未完成。 |

当前软件或验证缺口是 隐藏页实测（暂停读取软件已补）、旧temporary历史实例真实兼容同链（契约已验）、T09镜像内容删除桌面链和拉取断线核实、T12阶段停用与向前回退演练，T14/T16 的桌面隐藏页与前台交互（1/5台后台计数已补），T20 的完整真实负向矩阵；无持久归属标记的旧卷文件继续按安全边界排除，不能把它们视作可自动删除对象。十台实测因本机 Lima 内存预算不足标记 `blocked`，不计软件通过。外部阻塞主要为 AM-AC14 的专用谷歌镜像与账号/网络条件；本地测试 APK 已用于自建实例，不代表商店下载链。真实备份与恢复实验只清理本轮自建资源，已有外部卷和实例不纳入删除范围。

2026-09-24 磁盘观测校准：[增量证据](2026-09-24-disk-observation.md)补宿主工作区与VM Docker容量的HTTP和真实桌面展示。此项只完成AM-R12观测，创建/拉取准入仍未实现；历史全分支审查结果不能覆盖该已知Important缺口，AM-AC24继续partial。

2026-09-24后续校准：拉取磁盘准入18b75c49已完成实现与真实零pull拒绝/确认后中断核实，独立审查进行中；创建/复制/恢复准入待Task4，AM-AC24继续partial。见[当前证据](2026-09-24-pull-disk-and-bulk.md)。
