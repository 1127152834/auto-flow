# AM3 多实例效率验收

审计基线：`b828daf9`；当前聚焦后端 `159 passed, 1 warning`、前端 Android `13 files, 45 passed`；真实双实例基础证据来自 [总体验收记录](2026-09-22-validation.md)。

| 任务 | 状态 | 证据与限制 |
| --- | --- | --- |
| T13 批次与容量 | `blocked` | bulk/capacity 规则 unit 与 BulkActions 局部测试通过；计划指定 `test_android_capacity.py`、`BulkActions.test.tsx` 缺失；1–20 批量、竞态预留和压力未验收。 |
| T14 观察与预览 | `blocked` | 活跃 3 秒、停止 15 秒、失败退避和陈旧状态 unit 通过；`DevicePreviewVisibility.test.tsx` 自动化已通过，但无聚合延迟、预览并发/隐藏页面/内存实测。 |
| T15 应用管理 | `blocked` | requestId、包名、保护包、版本和真实 102 项 app_info 有证据；APK 过大/损坏/丢响应以及真实 stop/uninstall/clearData 未执行。 |
| T16 隔离与性能 | `blocked` | 两个真实实例 ADB serial `127.0.0.1:58272`/`127.0.0.1:58287` 不同，分别完成 HOME/截图/app_info；计划指定多实例 integration/frontend flow 缺失，1/5/10 台指标未执行。 |

## 自动验证命令摘要

```text
cd apps/backend && uv run pytest tests/unit/test_android_bulk.py tests/unit/test_android_capacity_rules.py tests/unit/test_android_observations.py -q
通过（包含在 Android 聚焦集合 159 passed 中）

cd apps/desktop && npm exec vitest run src/renderer/domains/android/tests
13 files, 45 passed（含旧设备列表轮询和 stale/unknown 打开保护回归）
```

硬件不足、破坏性应用操作和批量性能未用 mock 结果替代。
