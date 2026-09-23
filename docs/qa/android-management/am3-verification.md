# AM3 多实例效率验收

审计基线：`3ee61947`；当前聚焦后端 `235 passed, 2 warnings`、前端 Android `13 files, 81 passed`；真实双实例基础证据来自 [总体验收记录](2026-09-22-validation.md)。

| 任务 | 状态 | 证据与限制 |
| --- | --- | --- |
| T13 批次与容量 | `blocked` | bulk/capacity 规则 unit 与 BulkActions 局部测试通过；已有 `tests/unit/test_android_capacity.py`，尚缺计划指定的容量预留 integration；批量 UI 覆盖在 ManagementTools 等测试中；持久预留与 1/5/10 压力未闭环。 |
| T14 观察与预览 | `blocked` | 活跃 3 秒、停止 15 秒、失败退避和陈旧状态 unit 通过；`DevicePreviewVisibility.test.tsx` 自动化已通过，但无聚合延迟、预览并发/隐藏页面/内存实测。 |
| T15 应用管理 | `blocked` | requestId、包名、保护包、版本和真实 102 项 app_info 有证据；APK 字节上限、Manifest/split、安装后版本和丢响应已具备自动化；真实测试 APK 与 stop/uninstall/clearData 仍未验收，完成标记的新增回归见 9 月 23 日记录。 |
| T16 隔离与性能 | `blocked` | 两个真实实例 ADB serial `127.0.0.1:58272`/`127.0.0.1:58287` 不同，分别完成 HOME/截图/app_info；`test_android_multi_device.py` integration 已存在并通过；专门前端多实例 flow 和 1/5/10 台实测指标未完成。 |

## 自动验证命令摘要

```text
cd apps/backend && uv run pytest tests/unit/test_android_bulk.py tests/unit/test_android_capacity_rules.py tests/unit/test_android_observations.py -q
通过（包含在 Android 聚焦集合 235 passed 中）

cd apps/desktop && npm exec vitest run src/renderer/domains/android/tests
13 files, 81 passed（含旧设备列表轮询和 stale/unknown 打开保护回归）
```

硬件不足、破坏性应用操作和批量性能未用 mock 结果替代。

9 月 23 日增量与软件缺口：[最新记录](2026-09-23-validation.md)。本表的整任务 blocked 不表示缺失实现可由外部条件解释。

T14/T15 的前端响应栅栏、核验失败解锁和预览取消已补齐自动化。Node 运行时偏差与重跑结果见 [前端增量记录](2026-09-23-frontend-validation.md)；阶段真实性能验收未完成。
