# 旧批次幂等重放兼容修复

- 日期：2026-09-24；状态：confirmed（下列已完成验证），全后端运行结果待追加。
- 范围：仅 `application/android/fleet.py`、`integration/test_android_images_templates.py` 和本报告。未修改三份继承的 Studio 迁移文档；未创建真实运行时资源；真实旧版本迁移 QA 由父任务负责。
- 起点：`011068cd`，旧版本依据 `a92f0688f206d4339ff4468c1871f3ccdd6816dc`。

## 根因及最小修复

旧版本 `BatchCreate` 没有 `sourceDeviceId` 和 `allowUnknownDiskEstimate`；旧路由以 `model_dump(by_alias=True, mode="json")` 持久化完整请求。当前模型增加 `sourceDeviceId: null`，`batch()` 已去掉缺省/显式 false 的磁盘确认，但 `_existing()` 仍逐字段精确比较，因此旧持久请求缺失源字段时错误地返回 `ANDROID_REQUEST_CONFLICT`。

只在 `_existing(kind="batch")` 比较两侧临时映射时，为缺失 `sourceDeviceId` 补 `None`。不重写已有 payload，不改变新批次持久结构；真实源 ID、其他请求字段、true 磁盘确认仍参与精确比较；allocation 的比较完全不变。历史临时批次仍在创建拒绝之前返回，新临时批次仍拒绝，不恢复工作流。

## 回归行为与 RED/GREEN

测试先写入真实 SQLite 仓储，关闭并重新打开会话，再经过当前 FastAPI 路由重放。旧 fixture 的字段按 `a92f0688` 的模型和持久路径构造，没有先经过当前 `BatchCreate`，因此保留了缺失字段。参数化覆盖 persistent/temporary 和旧缺失/current null/current 源 ID 三种形状；检查默认/显式 false 重放返回原设备 ID、原状态，源 ID/true 确认变更冲突，新临时批次拒绝，数据库记录完全不变。没有模板或设备可供重新创建。

工作目录：`apps/backend`。

```sh
uv run pytest tests/integration/test_android_images_templates.py -k persisted_batch_request -q --tb=short
```

- RED（产品代码未改）：`2 failed, 4 passed, 15 deselected, 1 warning in 1.75s`。失败仅 `source0-persistent`、`source0-temporary`：预期 202，实际 409，错误 `ANDROID_REQUEST_CONFLICT`。
- GREEN（最小修复后，同命令）：`6 passed, 15 deselected, 1 warning in 1.61s`。

```sh
uv run pytest tests/unit/test_android_*.py tests/integration/test_android_*.py tests/contract/test_android_*.py -q --tb=short
uv run ruff check src/autoflow/application/android/fleet.py tests/integration/test_android_images_templates.py
uv run python -m compileall -q src/autoflow/application/android/fleet.py
```

- Android 回归：`540 passed, 2 warnings in 37.20s`，退出码 0。两条警告为已有 Starlette BlockingPortal 弃用及重复 ZIP 条目测试。
- Ruff：`All checks passed!`；compileall：退出码 0。
- 仓库根 `git diff --check`：退出码 0。

全后端已启动唯一运行：`uv run pytest -q --tb=short > /tmp/autoflow-legacy-replay-full-pytest.log 2>&1`；完成后追加实际输出、退出码及耗时，不以旧报告替代。

修复源码 SHA-256：`6cf1639d249d3e2ebfcfea48a73f1aafe84d02d6bf3716c01d28afca654edeac`。
回归测试 SHA-256：`d2903f2372e8bf2c6de67eae8ec9a8b3bd64ff16c48368f0a2b87c484f7e12bf`。
