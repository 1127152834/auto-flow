# Android 磁盘准入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** AM-R12 创建、拉取和备份在数据写入前检查目标文件系统可用空间；估计未知明确阻塞或由原请求绑定的人工确认继续。

**Architecture:** 保留 Mac/Lima/ReDroid 与操作持久化；磁盘探测留在 provider。先交付可精确计数的备份，后交付无法可靠预估增长量的创建/拉取确认流程。已完成的幂等回执先返回，不重跑写操作。

**Tech Stack:** 现有 Python stdlib、Lima 客体 GNU tar、shutil/statvfs；现有 DTO/React 页面，无新依赖。

## 基线与冲突（2026-09-24）

- 当前 `b51fac4f`，migration head `am01_management_operations`；三份 Studio 脏文件保留。
- AM-R12 缺口已确认：capacity只算CPU/内存，environment中的宿主free>0不是逐操作准入。备份ENOSPC清理保留，不能冒充预检。
- 备份宿主目标目录和 VM Docker 数据文件系统不能混用。预检不能保证期间无其他进程占用空间，原失败清理/未知结果保护必须保留。
- 此计划是已授权规格内的增量；每任务先有效RED，再最小实现和审查。先不并行写 ImageManager/HTTP 共享文件。

## Task 1：备份写入前的空间准入

范围追加（调用链复核）：BackupPanel 对所有409保留原请求，会让明确磁盘预检失败后一直重放已失败编号。增加三种明确预检错误的RED→GREEN，只释放此类已知未写入请求；未知传输仍核实原编号。对应 `BackupPanel.tsx`、`ManagementTools.test.tsx`。

范围：`providers/android/mac_runtime.py` 增加只读 archive 字节估计；`providers/android/backup_storage.py` 检查实际宿主目标；`application/android/backups.py` 在 stage/归档前串联。相关 unit/integration/contract fake runtime 返回受控归档实际长度，不能缺省跳过准入。

- [x] RED：未知估计、探测错误、空间不足（含manifest分块占用）必须不调用归档、不创建staging、不发布目录；允许分支继续一次，原回执重放不再探测。
- [x] RED：Mac估计复用原 `_backup_argv` 的同一 GNU tar 格式/属性/路径选项，在客体内流式计数，不能开启 Android 实例或把归档全部载入宿主内存。异常计数/命令失败明确拒绝。
- [x] GREEN：锁和停机/归属验证之后估计；按目标文件系统分配单位向上取整归档与manifest，检查可用空间。找不到估计接口或有效结果时返回 `ANDROID_DISK_ESTIMATE_UNKNOWN`，探测失败 `ANDROID_DISK_PROBE_FAILED`，已知不足 `ANDROID_DISK_SPACE_INSUFFICIENT`；已有操作记录保留失败原因。
- [x] 验证：备份/runtime/restore/cleanup相关单元、合同、集成；Ruff/compileall；真实自建设备停机卷估计与实际归档尺寸、真实空间探测、备份、传输取消、源数据探针及清理。低磁盘使用自建64MiB磁盘；本轮未重新执行真实恢复，恢复路径仅运行自动化回归。
- [x] 独立审查并修复C/I，记录命令/输出及实际范围，提交此垂直切片。接口响应已有错误契约，无新表，不创建空迁移。

## Task 2a：宿主与 VM 独立磁盘观测（2026-09-24 继续执行）

基线 de0708db，只有三份受保护 Studio 文件未提交。创建/拉取准入需要区分文件系统，先贯通只读观测作为同一需求的垂直切片：provider → HTTP schema → OpenAPI → RuntimeDiagnostics。

- [x] RED：宿主与 DockerRootDir 的可用字节独立；0 为已知不足；任一探测失败只令对应值为 null。契约保留两值；UI分别显示容量/未知。
- [x] GREEN：宿主使用 workspace 文件系统；VM通过只读 statvfs 检查 Docker info 返回的根目录，用 argv 传参；不推断写入所需大小、不改动生命周期或持久状态。
- [x] 验证：真实只读 Mac/Lima 结果、Android 回归、全后端/前端及工程门禁、增量审查、证据与 .ai 同步。无数据库字段，不创建迁移。

## Task 2b：创建与拉取（待Task1后最终校准）

- [x] 复核单实例、批量、复制快照和备份恢复创建的全部调用者；检查 VM Docker root 与宿主 Lima 数据所在文件系统。
- [x] 明确可估计量与未知量。不得用任意固定阈值或镜像压缩尺寸伪装实际所需空间；未知时需显式确认或明确阻塞。确认若采用，必须冻结到原请求摘要，UI明确显示未知且默认不勾选。
- [x] RED→GREEN同步DTO、OpenAPI、单/批创建、拉取服务与provider、前端。已知不足/探测失败不可通过未知确认绕过；已完成回执不重新拉取/创建。
- [ ] 真实Mac验证、增量审查、全量后端/前端/类型/lint/OpenAPI/build和最终阶段证据。


## 验证命令

```sh
uv run --project apps/backend pytest apps/backend/tests/unit/test_android_backup.py apps/backend/tests/unit/test_android_backup_storage.py apps/backend/tests/unit/test_android_runtime.py apps/backend/tests/integration/test_android_backups.py apps/backend/tests/integration/test_android_backup_restore.py apps/backend/tests/contract/test_android_backups.py -q
uv run --project apps/backend ruff check apps/backend/src/autoflow/providers/android apps/backend/src/autoflow/application/android/backups.py
```

最新快速验收时 Mac 已解锁并完成真实桌面快速检查；完整桌面验收尚未执行。创建/拉取磁盘准入仍是软件未完成项，不列为外部条件阻塞。

2026-09-24 用户要求最快检查验收，Task2未实施；当前快速签收结论见 docs/qa/android-management/2026-09-24-final-acceptance.md。


Task2b 调用链校准（2026-09-24，confirmed 源码阅读，尚未实施）：单实例 `AndroidCreate → AndroidManagement.create → provider.management.manage`；批量和配置复制由 `AndroidFleet._device_step` 汇入相同 create；备份恢复 HTTP 创建同样进入该链。拉取由 `ImagePullCreate → AndroidImageService.pull → ImageCatalog.pull → MacAndroidRuntime.pull_image`。准入必须在两条共享写入路径生效，放在所有权/固定镜像校验后、首次 volume/create/pull 前；成功幂等回执不能重新触发探测。无法估计时采用现有规格允许的显式拒绝或原请求绑定确认，不能使用任意固定阈值。数据恢复创建与后续解包应分别校验真实目标文件系统，不把宿主工作区可用量当作 Lima 虚拟磁盘宿主文件可用量。

## Task 3：镜像拉取磁盘准入（Task2b 的完整拉取切片）

基线126ac28b。保持原全目标范围，创建链在下一任务接入同一provider检查。本任务须贯通API/幂等/provider/UI/测试，而非只新增探测函数。

约束：Mac/Lima/ReDroid、设备归属/独占控制、generation/sequence、requestId、needs_verification 与未知结果保护不变；不接入退役工作流。规格 AM-R12 允许无法估计时明确阻塞或人工确认。不能用压缩镜像尺寸或任意常数伪装所需空间。

接口与行为：
- `ImagePullCreate.allow_unknown_disk_estimate: bool = Field(default=False, strict=True)`，JSON `allowUnknownDiskEstimate`。缺省拒绝不能可靠估计的写入；界面默认未勾选，明确说明最终占用未知，用户勾选才允许继续。
- 字段贯通 AndroidImageService.pull、ImageCatalog.pull、MacAndroidRuntime.pull_image，使用默认false的关键字参数。运行时新增共享 `require_vm_disk_space(*, allow_unknown_disk_estimate=False)`，后续创建可复用。
- 执行受限来源校验后、实际docker pull之前，探测Docker实际DockerRootDir可用字节及Lima VM磁盘文件所在宿主文件系统。`limactl list --json autoflow-redroid`实际提供name/status/dir/vmType/config；本机VZ磁盘为dir下`disk`（不是diffdisk）。支持已核实的固定单磁盘布局；不支持/含额外盘/身份不符/探测失败必须明确失败，不能猜路径。宿主使用实际磁盘文件，正确跟随symlink到其文件系统，不能复用workspace可用量。
- 已知可用0返回ANDROID_DISK_SPACE_INSUFFICIENT；无法读取容量返回ANDROID_DISK_PROBE_FAILED；最终占用无可靠估计且未确认返回ANDROID_DISK_ESTIMATE_UNKNOWN，均409且发生在docker pull前。确认仅豁免估计未知，不豁免前两种失败。探测超时/OSError包装为明确预检错误；真正pull启动后的未知/取消保护保持。
- 预检期间取消且docker pull尚未派发时，持久failed并标记明确预检取消原因、零pull，同时继续传播取消。真正pull派发后的取消仍needs_verification。不能靠镜像是否存在推断执行结果，也不能用跨请求共享可变flag；以边界内可证明事实分类。
- HTTP操作payload及digest绑定确认值；缺省/false保留旧reference-only摘要兼容，true写入payload。旧已完成/needs_verification回执重放先返回、不得重新探测或拉取；相同requestId改变确认值必须冲突。
- UI确认进入冻结请求；改变镜像引用重置确认；busy/未知期间不可改请求。三个明确预检错误应显示真实原因，释放已失败请求，让修复条件后用新编号尝试；普通409仍按原规则核实，不能误释放未知结果。组件既有422恢复、A成功/B丢响应、持久未知列表保护不倒退。

执行：
- [x] RED：真实服务/持久仓库覆盖缺省阻塞、已确认放行、已知不足/探测失败仍拒绝、拒绝无pull、回执重放/确认值冲突；provider独立主机/VM探测；UI默认不确认、冻结、引用变化重置、明确拒绝后新请求。
- [x] GREEN：最小实现；更新全部受影响fake签名/调用和生成OpenAPI，不删除旧语义断言。新增无依赖，无DB字段则不建迁移。
- [x] 验证：完整Android后端/前端、Ruff/类型/lint/OpenAPI/build；完整仓库门禁由主任务统一跑一次；实现者不要重复跑全仓长套件。
- [x] 实现者提交仅自身产品/测试/生成类型；写任务报告列有效RED、GREEN命令/实际结果、源码范围和风险。主任务另做真实拉取/未确认零拉取/原回执及实机UI，并独立任务审查。

本任务不要修改docs/qa脚本、共同.ai记录或这份计划；它们由主任务维护。严禁stage任何docs/migration/studio-frontend-completion文件。历史三份脏文件保留。


Task3已完成18b75c49+c4b6159d，独立复审与真实HTTP/桌面核实通过；全仓验证仍留待Task4。

## Task 4：创建、配置复制与恢复磁盘准入（Task2b 剩余切片）

基于Task3独立审查后的HEAD顺序执行，共享provider检查不可另建替代探测。此任务覆盖首次新卷/容器创建、保留数据重建容器，以及备份恢复写入前的磁盘准入。

接口/安全约束：
- 复用 `MacAndroidRuntime.require_vm_disk_space`，不把环境workspace free当实际Lima磁盘free，不使用镜像大小或固定阈值冒充预估。未知最终占用默认拒绝；严格默认false的 `allowUnknownDiskEstimate` 仅允许明确确认未知，零可用量/探测失败仍拒绝。
- 字段贯通单实例AndroidCreate、BatchCreate（含配置复制）、BackupRestore及AndroidDeviceCommand保留数据restore入口；共享management.manage在固定镜像/所有权核对后且首次volume/create之前检查。旧已完成请求重放必须先返回，不重新检查/写入；请求确认改变必须冲突。
- 创建同步返回202后异步预检失败允许持久failed；不能将failed伪装成功，前端必须看到真实错误。受影响成功测试显式确认或注入真实边界fake，拒绝测试必须断言零volume/create。
- false与缺省规范化为历史请求结构，保留原幂等回执兼容；true进入creationConfig、operation payload/digest、batch frozen request、restore payload/digest。不得原地修改调用方dict。
- 一次创建的确认不能被源模板/配置复制/备份配置或后续恢复隐式继承。备份恢复必须剔除来源creationConfig里的确认，以当前恢复请求为准；保留数据重建以当前operate请求为准。无需重建的start/stop等操作不得因新增确认要求被阻止。
- 备份恢复在创建目标后的实际restore_volume写入前再校验当前实际磁盘（复用同一确认，不能认为创建前的检查永久有效），归档路径/摘要/清单/镜像/归属校验及失败后源不可变规则保持。
- 已知预检失败保留明确错误码；取消预检与实际写入取消以可证明边界区分，写入已派发后的needs_verification绝不能降级。特别避免把创建已成功、恢复阶段才取消误标为零副作用。

前端：
- CreateDeviceForm（单/配置副本）、CreateInstances（模板批量/源快照）、BackupPanel恢复新实例、AndroidPage保留数据恢复对话框均提供明确的默认未勾选确认，文案指出最终磁盘占用无法可靠估计。原请求未知/进行中冻结确认与参数；原编号重试使用原值。修改影响写入的配置或目标重置确认。
- 继续使用既有组件/请求ref/错误样式，不引入依赖、不做无关重构。已有控制会话、generation/sequence、idempotency、保护包/恢复源保护及未知结果都不可退化；不接入已退役工作流。

执行与验收：
- [x] RED：共享provider未确认/0/探测失败零写入；确认放行；单/批/副本/保留数据重建/备份恢复字段贯通与拒绝；旧false回放、改变确认冲突；来源确认不继承；恢复写入前再次检查；事件驱动取消边界；前端四入口默认未选、冻结、参数变化重置与原编号重试。
- [x] GREEN：最小跨层实现+受影响fake/调用更新+OpenAPI生成，无数据库结构变化则无需迁移。
- [x] Android后端和前端全套、Ruff、compile、类型、lint、OpenAPI、build；根任务统一执行全仓长套件，不重复。ef0af03f：4099后端/5683前端通过。
- [x] 自有代码提交+task-4-report记录有效RED/GREEN、实际命令输出、风险；主任务真实Mac创建/恢复验收与独立审查。实际新UI仍blocked，不包含在此后端真实结果内。

文件由实现者追踪真实调用链选择，预期涉及backend android.py/android_fleet_schemas.py/android_management_schemas.py/android_management.py、application/android/{management,fleet,backups}.py、providers/android/{management,mac_runtime}.py、上述前端四入口与生成类型/测试。根任务独占docs/qa、.ai与本计划；不得stage Studio脏文件。实现者不得更改任何QA脚本或其他代理提交。

2026-09-24 最终候选校准（supersedes上文“Task2未实施/创建拉取未实现”的历史进度）：18b75c49+c4b6159d完成拉取，b744666d+ef0af03f完成四入口创建/复制/恢复；Task3/Task4规格与质量审查Approved。真实Mac创建/恢复/复制/失败重试及自建资源清理通过。全前端5683项及类型/lint/OpenAPI/build/迁移通过；全后端及完整分支审查正在收尾。新确认UI因Mac锁屏blocked，保留对应最终真实验收复选框未关闭。

Task4实现切片完成：b744666d+ef0af03f，独立审查Approved，完整自动化与真实后端通过。完整分支最终审查发现另外的并发核实与UI可达缺陷，必须作为一次修复批次处理并复验；本计划最终整体验收仍未关闭。
