# T01–T20 当前证据追踪与计划校准

- 日期：2026-09-24；状态：`confirmed`（当前文件、命令和证据索引核对），完整交付仍 `partial`。
- 基线：`codex/android-management-complete@30eb0926` 加本次备份说明、真实故障脚本及文档增量。三个既有 Studio 文档未纳入本任务。
- 原附件的提交 `edf3906b` 和 101 项 checkbox 是历史数据；当前计划实际有 **102** 项（T14、T15 各含一条后续增量）。本次逐项更新括号状态和勾选，不用旧 `blocked` 推断软件缺失。
- 本表只核对当前实现和测试；历史 RED 只引用已有 QA 中实际记录的失败，不把今天的 GREEN 追认为历史 RED。没有找到独立 RED 输出的步骤保留 `not_run` 并说明。
- 缩写沿用计划：`B/`=`apps/backend/src/autoflow/`，`BT/`=`apps/backend/tests/`，`F/`=`apps/desktop/src/renderer/domains/android/`，`DS/`=`apps/desktop/src/`。测试文件下面按 `U` unit、`C` contract、`I` integration、`FE` 前端列出。

## 代码、契约与数据库

管理契约统一在 `B/adapters/http/android_management{,_schemas}.py`（下表 M），旧设备/会话/模板契约在 `B/adapters/http/android{,_fleet,_fleet_schemas}.py`（下表 D）。生成类型为 `DS/renderer/shared/api/generated.ts`。数据库 M1 是 `B/infrastructure/database/migrations/versions/am01_management_operations.py`，父节点 `0019_recording_commands`；唯一 head 已重新执行确认。R 指复用已有设备/资源表及 M1 持久 Operation，不新增表形状，不凭空新增迁移。

| 任务 | 当前实现与契约 | 数据库 | 当前前端 |
| --- | --- | --- | --- |
| T01 | `BT/fixtures/android_management.py` | 临时库夹具 | `F/tests/management-fixtures.ts` |
| T02 | `B/domain/android/management_{models,rules}.py`；M | R，状态投影 | `F/state/management-state.ts` |
| T03 | `B/application/android/diagnostics.py`、`B/providers/android/mac_runtime.py`；M environment/capabilities | 无写入 | `F/components/RuntimeDiagnostics.tsx` |
| T04 | `B/infrastructure/database/android_operations.py`、`B/application/android/verification.py`；M operations | M1；操作与设备同事务 | `F/components/OperationHistory.tsx` |
| T05 | `B/application/android/console.py`、`B/providers/android/{mac_runtime,stream}.py`；D sessions | R，session/app receipts | `F/state/console-controller.ts`、`F/components/{DeviceConsole,AndroidVideo}.tsx` |
| T06 | `B/application/android/{devices,management,fleet}.py`；M devices、D lifecycle/profiles | R，保留历史 payload | `F/pages/AndroidPage.tsx`、`F/components/{ManagementOverview,CreateDeviceForm,CreateInstances}.tsx` |
| T07 | `scripts/smoke-android-management.py`；D/M 真实调用 | 独立临时库 | 上述管理页和控制面板 |
| T08 | `B/providers/android/image_catalog.py`、`B/domain/android/image_models.py`；M images | R，固定 imageId 与引用 | `F/components/ImageManager.tsx` |
| T09 | `B/application/android/images.py`、`B/providers/android/mac_runtime.py`；M images/actions | R/M1，目录与请求回执同事务 | `F/components/ImageManager.tsx` |
| T10 | `B/application/android/fleet.py`；D profiles/batches | R，模板 revision/创建快照 | `F/components/{TemplateManager,CreateInstances}.tsx` |
| T11 | `B/domain/android/image_verification.py`；M ImageRead.validation | R，独立 GApps 验收字段 | `F/components/ImageManager.tsx` |
| T12 | T08–T10 真实服务集成；D/M | R/M1 | ImageManager、TemplateManager |
| T13 | `B/application/android/{bulk,capacity}.py`、`B/providers/android/capacity_reservations.py`；M bulk | R/M1；运行时共享预留文件 | `F/components/BulkActions.tsx` |
| T14 | `B/application/android/observations.py`、`B/bootstrap/android.py`；M aggregate devices | R，快照 | `F/components/{ManagementOverview,DevicePreview}.tsx` |
| T15 | `B/application/android/{apk,console}.py`、`B/providers/android/mac_runtime.py`；D apps | R，内容摘要、完成标记、应用回执 | `F/components/{ApplicationsPanel,DeviceConsole}.tsx` |
| T16 | T13–T15 真实实例集成 | 独立临时库 | ManagementOverview、BulkActions |
| T17 | `B/application/android/backups.py`、`B/providers/android/backup_storage.py`；M backups | R/M1；文件发布与目录终态 | `F/components/BackupPanel.tsx` |
| T18 | 同上及 M restore route；`B/providers/android/mac_runtime.py` | R/M1，新目标与恢复意图 | `F/components/BackupPanel.tsx` |
| T19 | `B/application/android/{cleanup,diagnostics_export}.py`；M cleanup/diagnostics | R/M1；冻结预览与清理父子结果 | `F/components/DataMaintenance.tsx`；`DS/main/settings/controller.ts`、`DS/preload/index.ts` 受限保存 |
| T20 | 四阶段 QA、最终审查、全量命令 | 新/旧库、单 head、旧迁移摘要 | 全桌面套件和构建 |

## 自动测试到任务的映射

以下文件均已在当前仓库核对存在。2026-09-24 实际运行全部 `test_android*.py` 得 `447 passed, 2 warnings in 29.43s`；全部 Android 前端 `14 files / 135 tests` 通过。随后补备份可访问说明：单项 RED `1 failed/25 skipped`（按钮无说明），GREEN 同文件 `26 passed`；前端全量在该变更后另重跑，结果见本轮故障验收记录。最新未变的后端全量为 `4031 passed/26 skipped`，不能将以下重叠测试数相加。

| 任务 | 单元 / 契约 / 集成 / 前端证据 |
| --- | --- |
| T01 | U `test_android_management_fixtures.py`；FE `management-fixtures.test.ts`；临时库由集成测试实际使用 |
| T02 | U `test_android_management_state.py`；C `test_android_management_devices.py`；FE `ManagementState.test.ts` |
| T03 | U `test_android_runtime.py`；C `test_android_management_environment.py`；FE `RuntimeDiagnostics.test.tsx` |
| T04 | I/C `test_android_management_operations.py`；I `test_android_m4_migration.py`、`test_migration_heads.py`；FE `ManagementOverview.test.tsx` |
| T05 | U `test_android_console_lifecycle.py`、`test_android_handoff.py`；FE `ConsoleController.test.ts`、`AndroidVideo.test.ts`、`AndroidPage.test.tsx` |
| T06 | U `test_android_batch_safety.py`、`test_android_profiles.py`；C `test_android_management_devices.py`；FE `ManagementOverview.test.tsx`、`AndroidPage.test.tsx`、`Management.test.tsx` |
| T07 | U `test_android_management_smoke_args.py`；真实脚本单列，无专门新表 |
| T08 | U `test_android_image_catalog.py`、`test_android_images.py`；C `test_android_images.py`；I `test_android_images_templates.py` |
| T09 | U `test_android_images.py`；C `test_android_images.py`；I `test_android_images_templates.py`；FE `ImageManager.test.tsx` |
| T10 | U `test_android_profiles.py`、`test_android_batch_safety.py`；C `test_android_templates.py`；I `test_android_images_templates.py`；FE `TemplateManager.test.tsx` |
| T11 | U `test_android_image_verification.py`；FE `ImageManager.test.tsx` 的 technical verification/GApps 分离 |
| T12 | I `test_android_images_templates.py`；FE ImageManager/TemplateManager；未创建重复的 ImagesTemplatesFlow 文件 |
| T13 | U `test_android_bulk.py`、`test_android_capacity{,_rules}.py`；C `test_android_management_bulk_projection.py`；I `test_android_capacity_reservations.py`、`test_android_multi_device.py`；FE `ManagementTools.test.tsx` |
| T14 | U `test_android_observations.py`；C `test_android_management_devices.py`；FE `DevicePreviewVisibility.test.tsx`、`ManagementOverview.test.tsx` |
| T15 | U `test_android_apk.py`、`test_android_console_lifecycle.py`；C `test_android_apps.py`；FE `ApplicationsPanel.test.tsx`、`DeviceConsoleApps.test.tsx` |
| T16 | I `test_android_multi_device.py`；FE `ManagementTools.test.tsx`、`DevicePreviewVisibility.test.tsx`；真实规模另列 |
| T17 | U `test_android_backup{,_storage}.py`；C `test_android_backups.py`；I `test_android_backups.py`；FE `ManagementTools.test.tsx` |
| T18 | U `test_android_archive_validation.py`、`test_android_backup.py`；I `test_android_backup_restore.py`、`test_android_restore_isolation.py`；C `test_android_backups.py`；FE `ManagementTools.test.tsx` |
| T19 | U `test_android_cleanup{,_contract}.py`、`test_android_diagnostics_export.py`；C `test_android_cleanup.py`、`test_android_management_diagnostics.py`；I `test_android_cleanup_files.py`；FE `ManagementTools.test.tsx`、`DS/main/settings/settings{,.integration}.test.ts` |
| T20 | 上述集合及完整后端/桌面、Ruff、类型、lint、OpenAPI、结构、脚本、build；[全量输出](2026-09-24-final-full-gates.md) |

## 每任务真实证据与剩余状态

这里的整任务状态使用 `passed / failed / blocked / not_run`；`not_run` 表示仍有明确可执行的剩余项，**不是**抹去已通过的软件或真机部分。每条命令、资源 ID、镜像及实际输出在所链 QA 原记录，未经记录不追认通过。

| 任务 | 状态 | 真实命令/证据及下一缺口 |
| --- | --- | --- |
| <a id="t01"></a>T01 | `passed` | git 状态及保护哈希已核对；普通测试只用临时库。 |
| <a id="t02"></a>T02 | `passed` | 纯状态规则以上述自动化证明；[真实管理状态](2026-09-23-am1-real-control-retention.md)作交叉核对。 |
| <a id="t03"></a>T03 | `passed` | 生产 environment 检查 Mac/Lima/ADB/binder，真实 `available=true`，见 AM1 QA；负向无副作用由契约测试证明。 |
| <a id="t04"></a>T04 | `passed` | [真实 HTTP 重启和历史查询](2026-09-23-operation-history-verification.md)，SQL 事务/幂等/迁移负向由集成测试证明。 |
| <a id="t05"></a>T05 | `not_run` | [控制链](2026-09-23-am1-real-control-retention.md)已验输入/切端/租约/HTTP 重启；尚缺同一桌面链的真实断线、UI 离开保留原生窗口。 |
| <a id="t06"></a>T06 | `not_run` | [桌面链](2026-09-23-desktop-ui-verification.md)已验创建/生命周期/长名/高缩放；精确 200%、指定两窗口尺寸、旧 temporary 同链未验。 |
| <a id="t07"></a>T07 | `not_run` | `scripts/smoke-android-management.py` 与 AM1 QA 已有自建实例、APK/中文输入/数据/双实例删除隔离；进程级受控操作中断仍待完整同链。 |
| <a id="t08"></a>T08 | `passed` | [AM2](am2-verification.md)固定基础 imageId、真实登记与按摘要删除；引用变化自动化有明确保护。 |
| <a id="t09"></a>T09 | `not_run` | [AM2](am2-verification.md)真实固定摘要网络 pull、认证 HTTP 内容删除；桌面内容删除与真实断线核实未验。 |
| <a id="t10"></a>T10 | `passed` | 后端生命周期集成与[桌面标准模板](2026-09-23-desktop-ui-verification.md)；已有实例固定快照由集成测试证明。 |
| <a id="t11"></a>T11 | `blocked` | [GApps](gapps-validation.md)：缺专用镜像/账号/商店下载链；本地 APK 已可用，不能再称测试 APK 缺失。 |
| <a id="t12"></a>T12 | `not_run` | 基础镜像/模板链已验；独立自定义 Android 候选实例链与阶段回退演练尚未运行。 |
| <a id="t13"></a>T13 | `not_run` | [真实批次](2026-09-24-bulk-failure-cancel.md)部分失败、修订冲突重试、容量取消通过；运行时瞬时故障/未知结果后的核实仍待补。 |
| <a id="t14"></a>T14 | `not_run` | [五台/双预览](2026-09-23-final-review-remediation.md)通过；后台探测次数、隐藏页面同链与前台延迟未记录完整。 |
| <a id="t15"></a>T15 | `not_run` | [真实 APK 动作](2026-09-23-am1-real-control-retention.md)及[跨重建版本核实](2026-09-24-final-branch-review.md)通过；桌面破坏性确认同链、真实 ADB 断连未验。 |
| <a id="t16"></a>T16 | `not_run` / 十台 `blocked` | 1/5 台 API、双实例隔离有证据；[7921 MiB < 8192 MiB](2026-09-24-advanced-logs-and-capacity.md)阻塞十台，其他规模缺的前台/探测指标仍可继续。 |
| <a id="t17"></a>T17 | `passed`（已列功能） | [真实磁盘不足与传输取消](2026-09-24-backup-failure-verification.md)补足 AC19；归档/权限/摘要/发布回归通过。宿主硬中断发生在传输中及真实权限拒绝仍作扩展故障 `not_run`，不冒充已验。 |
| <a id="t18"></a>T18 | `not_run` | [新卷属性读回](2026-09-23-persistent-metadata-verification.md)与[写入后硬中断](2026-09-23-restore-hard-interruption-verification.md)通过；[真实解包中 SIGKILL](2026-09-24-restore-transfer-interruption.md)已验；恢复目标磁盘不足和取消恢复仍未验。 |
| <a id="t19"></a>T19 | `not_run` | [真实清理](2026-09-23-cleanup-verification.md)、[高级诊断](2026-09-24-advanced-logs-and-capacity.md)通过；多对象清理硬中断与旧卷文件来源缺失仍有边界需记录。 |
| <a id="t20"></a>T20 | `not_run` | 实际服务/实例/源数据保护和全量门禁有证据；上述具备条件的剩余故障及桌面链未全部运行，不能整体完成。 |

## 校准取舍

- 模板继续使用 AndroidFleet；计划中的 TemplateService 名称映射到已有服务，避免双持久化权威。代价：文件名与原计划示例不同，追踪表必须保持准确。
- BackupPanel、DataMaintenance、多设备页面的前端测试复用 `ManagementTools.test.tsx` 等现有文件，不为计划示例文件名创建重复套件。代价：需按测试名称识别覆盖，不以文件数判断完成。
- 历史任务的提交标题是建议行为描述，实际合并到已有有界提交；勾选“提交”只确认软件切片已入历史，不代表整个阶段真实验收完成。
- 外部不足才写 blocked；缺真实执行记录写 not_run。102 个步骤的全部状态均应可追溯到本表，不能再让旧 blanket blocked 长期作为当前状态。

本轮最终文档核验：102 个勾选与状态逐一一致（81 passed / 18 not_run / 3 blocked），67 个显式实现路径存在，283 个修改文档的本地链接存在；`git diff --check` exit 0。两份真实 QA 脚本 Ruff 通过，`--help` exit 0，缺少 `--allow-device-mutation` 时均 exit 2。三个 Studio 文件 SHA-256 与本轮开始一致。
