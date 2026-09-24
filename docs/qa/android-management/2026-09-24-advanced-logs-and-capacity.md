# 高级日志与十实例容量验收

- 日期：2026-09-24；状态：`confirmed`（高级日志自动化与真实 ReDroid）、`blocked`（本机十实例）。来源：隔离分支代码、RED→GREEN 测试、Apple Silicon Mac 上的 Lima/ReDroid 实验。

高级日志此前只返回 `ANDROID_DIAGNOSTICS_ADVANCED_LOGS_UNSUPPORTED`。本轮先令后端契约测试在缺少同意时预期 422、有效同意时预期日志摘要而失败，再加入单次请求确认、当前工作区设备归属校验和生产 logcat 采集。前端测试先因缺按钮失败，再补原生确认与最多五台的明确选择。日志读取最近 200 行、最多 64 KiB，按时间戳限制到最近 300 秒；导出只保留时间与级别，应用可控的 tag 和消息正文均丢弃。单次确认仅授权对应的新 requestId，同号重放只读已有结果，不重新采集。诊断仍只在既有受限 Electron 保存能力中下载，五分钟过期，不自动发送。

定向验证：

```text
uv run --project apps/backend pytest -q apps/backend/tests/contract/test_android_management_diagnostics.py apps/backend/tests/unit/test_android_diagnostics_export.py apps/backend/tests/unit/test_android_runtime.py
npm exec --offline --yes --package=node@22.23.2 -c 'npm test -w @autoflow/desktop -- --run src/renderer/domains/android/tests/ManagementTools.test.tsx --maxWorkers=1'
```

实际输出：后端 `64 passed, 1 warning in 1.08s`，前端 `25 passed`。真实命令 `uv run --project apps/backend python /tmp/autoflow-am4-advanced-logs-real-20260924.py`，exit 0，`status=passed`，一台自建 ReDroid 通过认证 HTTP 返回 `windowSeconds=300`、196 条仅含 `at/priority` 的日志元数据；合成的 `secret@example.invalid` 不在 HTTP 结果。运行时前一次实验发现 Android logcat 行首缩进，导致解析为零条；补 RED 单测并修正解析后真实实验通过。HTTP 删除本轮实例后，独立 Docker 标签查询为 `ownedContainers=[]`、`ownedVolumes=[]`。

十实例在本机无法满足容量合同：`limactl shell --workdir=/tmp autoflow-redroid free -m` 实测虚拟机内存总量 7921 MiB；后端 schema 每实例最低 768 MiB，容量规则另保留 512 MiB。十台最低需求 `10 × 768 + 512 = 8192 MiB`，已超过虚拟机总量 271 MiB，即使停止其他容器也无法准入。状态 `blocked`，未伪造十台运行/性能结果；此前五台真实数据仍见[全分支审查修复](2026-09-23-final-review-remediation.md)。十台实测需要至少增加虚拟机内存并重新跑聚合读取、探测、预览和前台交互指标。
