# Legacy batch replay：规格与代码质量审查

- 日期：2026-09-24；状态：confirmed（本次有界审查）；置信度：高。
- 范围：`011068cd..0f6f8fac` 的旧批次重放兼容修复；按 `legacy-replay-brief.md`，审查提供的 `legacy-replay-review.diff` 一次，再核对具体调用链与证据。没有重跑测试、修改业务代码或扩大到已完成的整分支审查。
- 当前 HEAD：`0f6f8fac1d0b3bb5567fb7065ea7995b803fa18b`。源码与回归测试 SHA-256 均与实施报告一致。

## Declined to judge

- 整个 Android 管理分支、前端及既有迁移的全面正确性：父任务已完成先前整分支审查，本次只审新缺陷修复；仅沿具体风险核对 HTTP、仓储和 allocation 调用。
- 最终全后端回归是否通过：审查时日志仍在执行，由父任务收集完成结果；没有以历史全量结果代替。
- 父任务正在更新的 QA、验收汇总与继承的 Studio 文档：不属于本次两个文件的兼容修复门禁。

## Spec verdict

**PASS。** 实现满足简报，无规格偏离。

- `apps/backend/src/autoflow/application/android/fleet.py:141–146` 仅在 `kind == "batch"` 时对比较两侧建立新字典，以默认 `None` 补缺失的 `sourceDeviceId`；字典展开保留已有真实源 ID。原请求、已保存 payload 和其他字段不被修改，非空源变化仍触发第 147 行冲突。
- 同文件 `193–203` 保留既有 false 确认归一化和严格 true 确认；原批次先返回，新的临时批次仍被拒绝。修复不会进入模板读取、源设备复制或设备创建路径，也不触发迁移或工作流。
- 同文件 `260–277` 的两个 allocation 调用仍执行原始精确比较，工作流拒绝边界不变。
- `apps/backend/src/autoflow/adapters/http/android_fleet.py:67–72` 确认真实 HTTP 使用完整 `model_dump`；当前 schema 第 46 行注入默认源字段，旧 `a92f0688` schema 确实没有该字段，因此比较归一化落在根因处。

## Strengths

- 修复只增加局部比较映射，没有重写历史记录、增加迁移或引入通用兼容抽象。
- `apps/backend/tests/integration/test_android_images_templates.py:31–74` 六种参数组合覆盖旧缺失、当前 null 和真实源 ID，以及 persistent/temporary；SQLite 关闭重开后经过当前 FastAPI 路由，验证原设备 ID/状态、默认及显式 false、真实源变更、true 确认冲突、新临时批次拒绝和数据库记录保持不变。未设置可供重新创建的模板或设备，能暴露错误走入新建路径。
- 已读取父任务实际旧后端升级原始证据 `/private/tmp/android-legacy-upgrade.json` 与 `/private/tmp/android-legacy-upgrade-green.json`：旧提交 `a92f0688`、SQLite `0019_recording_commands` 升级到 `am01_management_operations`，真实旧 temporary 批次重放由 409 `ANDROID_REQUEST_CONFLICT` 变为 202；同次升级前后设备/容器/卷身份、创建快照与探针保持，新的 temporary 请求被拒绝。

## Issues

- Critical：无。
- Important：无。
- Minor：无。

## Verification and assessment

实施报告记录 RED 为 `2 failed, 4 passed`，GREEN 为 `6 passed`，Android 回归为 `540 passed`，Ruff、compileall、diff check 通过；这些属于已审阅的实施验证记录，本审查未重复执行。真实升级的 RED/GREEN 原始 JSON 已独立阅读。审查时全后端日志仅显示执行进度，尚无最终通过结论。

**Ready to merge（本修复范围）：Yes。** 比较语义只扩大到明确等价的“无源”两种表示，保持真实冲突和历史请求原貌；覆盖与独立升级证据足以支持此缺陷关闭。全分支最终验收仍由父任务汇总运行中的完整后端结果与其他既有门禁。
