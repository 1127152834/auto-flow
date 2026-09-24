# Task 3 镜像拉取磁盘准入报告

- 日期：2026-09-24
- 状态：confirmed（自动化验证）；真实 Mac/Lima 拉取由主任务另行验收。
- 基线：`126ac28b`；范围为 ImagePullCreate → HTTP 持久操作 → AndroidImageService → ImageCatalog → MacAndroidRuntime → ImageManager 与对应测试、生成 OpenAPI 类型。

## 行为

默认请求在 Docker pull 前检查实际 DockerRootDir 和 Lima `autoflow-redroid` VZ `dir/disk` 所在文件系统；已知可用量为零返回 `ANDROID_DISK_SPACE_INSUFFICIENT`，探测、身份或单磁盘布局无法核实时返回 `ANDROID_DISK_PROBE_FAILED`，容量可读但最终占用无法可靠估计且未确认时返回 `ANDROID_DISK_ESTIMATE_UNKNOWN`。确认仅放行最后一种情况。宿主磁盘文件先解析符号链接，再取得所在文件系统可用量；未复用 workspace 统计。受限镜像来源先验证，未引入大小猜测或新依赖。

`allowUnknownDiskEstimate` 是严格布尔值。缺省和 false 保留原 reference-only 幂等摘要；true 进入持久 payload/摘要。已完成、失败和待核实操作按原 requestId 重放，确认值变化由持久操作仓库拒绝。镜像服务回执也保存确认值，兼容缺省为 false 的旧回执。UI 默认不确认，冻结请求包含确认值；引用变化清除确认；三种明确预检 409 显示原文并释放请求编号，其余未知结果仍按原编号核实。

预检协程取消时 provider 抛出显式 `AndroidDiskPreflightCancelled`，HTTP 将持久操作记为 `failed/ANDROID_DISK_PREFLIGHT_CANCELLED` 后继续传播取消；Docker pull 已派发后的普通取消仍为 `needs_verification`。没有共享运行时标志或依据镜像存在性推断取消阶段。

## RED → GREEN 证据

- RED：`uv run pytest tests/unit/test_android_image_catalog.py tests/unit/test_android_runtime.py -q -k 'pull_disk or pull_passes_explicit'`：5 failed，缺确认参数和预检；实现后 5 passed。
- RED：`uv run pytest tests/contract/test_android_management_operations.py -q -k 'pull_disk_confirmation'`：1 failed，HTTP 未识别确认字段；实现后通过。
- RED：`npm exec vitest run src/renderer/domains/android/tests/ImageManager.test.tsx -t 'freezes disk|definitive pull preflight'`：4 failed，确认控件缺失、三种 409 被误报为普通冲突；实现后 ImageManager 17 passed。
- RED：事件驱动 HTTP 取消测试中预检任务等待 `asyncio.Event` 时取消，原状态错误地落为 `needs_verification`；实现后预检取消与已启动 pull 取消两个边界测试通过。
- RED：自环磁盘符号链接使 `Path.resolve(strict=True)` 抛出未包装的 `RuntimeError`；将其纳入 `ANDROID_DISK_PROBE_FAILED` 后该测试通过，Docker pull 保持零调用。
- 独立审查修复 RED：`npm test -- src/renderer/domains/android/tests/ImageManager.test.tsx`：新增三种磁盘错误的“首次响应丢失 → 同编号重试返回 `202/failed`”场景均失败，旧 UI 把失败回执误显示为“拉取操作已接受”；修复后 20 passed。`resultCode` 命中明确磁盘预检错误时，使用持久 `message` 呈现原因并释放旧编号；普通未知结果仍保留原编号核实。

## 验证

- `uv run pytest tests/unit/test_android_* tests/contract/test_android_* tests/integration/test_android_* -q`：493 passed。两条警告原文分别为 Starlette `The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.`，以及 `test_android_apk.py::test_parse_apk_rejects_duplicate_manifest_entries` 触发的 `UserWarning: Duplicate name: 'AndroidManifest.xml'`。随后新增符号链接环拒绝测试并修复，重跑受影响四文件：142 passed；完整 Android 由主任务最终集成后再跑。
- `npm test -- src/renderer/domains/android/tests`：初轮 14 files / 184 passed；独立审查 UI 修复后 14 files / 187 passed。
- 变更文件 `uv run ruff check`、`npm run typecheck`、`npm run lint`、`npm run openapi:check`、`npm run build`、`git diff --check`：通过。
- `uv run mypy src/autoflow/adapters/http/android_management_schemas.py src/autoflow/domain/android/ports.py src/autoflow/providers/android/image_catalog.py src/autoflow/providers/android/mac_runtime.py --follow-imports=silent`：通过。对这 4 文件加上 `android_management.py`、`images.py` 的 6 文件扫描报 22 处类型问题；以 `git archive HEAD apps/backend/src/autoflow apps/backend/pyproject.toml` 导出基线并在隔离临时目录用同一 mypy 命令复跑，亦为同样 22 项（忽略行号后的错误签名与数量相同）。本次新增的两个推断错误已修正。未运行全仓长套件；由主任务集成后统一执行。

## 自审与剩余范围

- 审核了持久重放、false 旧摘要、true 冲突、零空间、额外盘、符号链接与取消阶段，未发现新增数据迁移需求。
- VZ 固定单磁盘布局以本机 `limactl list --json autoflow-redroid` 及 `dir/disk` 观察为准；其他布局会明确拒绝。真实拉取、强杀重启后的回执、实机 UI 由主任务 QA 验证。
- 未修改或提交计划、`.ai`、QA 脚本及历史 Studio 脏文件。
