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

## Task 2：创建与拉取（待Task1后最终校准）

- [ ] 复核单实例、批量、复制快照和备份恢复创建的全部调用者；检查 VM Docker root 与宿主 Lima 数据所在文件系统。
- [ ] 明确可估计量与未知量。不得用任意固定阈值或镜像压缩尺寸伪装实际所需空间；未知时需显式确认或明确阻塞。确认若采用，必须冻结到原请求摘要，UI明确显示未知且默认不勾选。
- [ ] RED→GREEN同步DTO、OpenAPI、单/批创建、拉取服务与provider、前端。已知不足/探测失败不可通过未知确认绕过；已完成回执不重新拉取/创建。
- [ ] 真实Mac验证、增量审查、全量后端/前端/类型/lint/OpenAPI/build和最终阶段证据。

## 验证命令

```sh
uv run --project apps/backend pytest apps/backend/tests/unit/test_android_backup.py apps/backend/tests/unit/test_android_backup_storage.py apps/backend/tests/unit/test_android_runtime.py apps/backend/tests/integration/test_android_backups.py apps/backend/tests/integration/test_android_backup_restore.py apps/backend/tests/contract/test_android_backups.py -q
uv run --project apps/backend ruff check apps/backend/src/autoflow/providers/android apps/backend/src/autoflow/application/android/backups.py
```

最新快速验收时 Mac 已解锁并完成真实桌面快速检查；完整桌面验收尚未执行。创建/拉取磁盘准入仍是软件未完成项，不列为外部条件阻塞。

2026-09-24 用户要求最快检查验收，Task2未实施；当前快速签收结论见 docs/qa/android-management/2026-09-24-final-acceptance.md。
