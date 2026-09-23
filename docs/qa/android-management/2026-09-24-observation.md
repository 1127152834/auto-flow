# 隐藏页批次读取与真实后台观察

- 日期：2026-09-24；基线 `33e7f547` 加本轮三份[候选源码](2026-09-24-observation/candidate-hashes.json)。状态：软件与真实后端测量 confirmed；T14/T16 整体验收 partial。
- 规格 AM-R12、T14.4：隐藏页面暂停展示轮询；控制心跳与后台观察继续。BulkActions 的手动计时器此前未检查页面可见性，本轮在读取前增加一行检查；隐藏期间不发起新 GET，可见后在下一轮恢复。已有只读请求可以完成，动作不会自动重放。
- 无新增依赖、API 或 schema；不改变 Mac/Lima/ReDroid、归属校验、控制权或未知结果保护。

## RED → GREEN

真实 React 组件配合假时钟与可见性属性：提交后隐藏 15 秒无状态 GET，恢复可见 3 秒后读到终态，批次只提交一次、没有动作写请求。实现前 [1 failed / 36 skipped，1.21s](2026-09-24-observation/hidden-red.log)；实现后 ManagementTools、ManagementOverview、DevicePreviewVisibility [3 文件 / 69 passed，2.97s](2026-09-24-observation/hidden-green.log)。观察器与聚合契约 [12 passed / 1 warning，0.13s](2026-09-24-observation/focused-backend.log)。假时钟不是桌面验收证据。

独立只读审查未发现 Critical/Important。一个 Minor 限制：真实脚本对间隔只断言下限，不能据此保证所有负载下的刷新上限；下表保留实际最大值。20 次列表读取均断言 ready 且非 stale，但不能推论整个观测窗口每一时刻都新鲜。

## 真实 Mac / Lima / ReDroid 测量

[可复现脚本](scripts/observation-smoke.py)创建独立临时工作区，使用生产 FastAPI、真实 SQLite、真实 Uvicorn 回环 TCP、HTTP 鉴权和实际运行时。计数包装调用原 runtime.inspect，不替代 IO；只计共享 runtime.inspect，不声称统计所有 Docker 命令或其他运行时实例。客户端与服务端处于同一进程，因此下列延迟不是独立进程 sidecar 或桌面渲染基准。

```sh
uv run --project apps/backend python docs/qa/android-management/scripts/observation-smoke.py --allow-device-mutation --output docs/qa/android-management/2026-09-24-observation/real-observation.json
```

实际 exit 0，`status=passed/cleaned=5`：[原始输出](2026-09-24-observation/real-observation.log)、[完整结果](2026-09-24-observation/real-observation.json)。未给授权标志时实际 [exit 2](2026-09-24-observation/cli-guard.log)，不创建实例。

| 指标 | 1 台 | 5 台 |
| --- | --- | --- |
| 每台配置 | 1 CPU / 1024 MiB | 1 CPU / 1024 MiB |
| 列表 API 样本数 | 20 | 20 |
| median / P95 / max | 2.973 / 6.177 / 8.903 ms | 3.507 / 12.495 / 14.554 ms |
| 18 秒窗口后台 inspect | 5 次 | 每台 4 次，共 20 次 |
| 实际开始间隔 | 3.2305–3.3318 秒 | 4.1511–4.2004 秒 |
| 列表路由同步 inspect | 0 | 0 |
| 最后一次客户端读取后后台 inspect | 4 次 | 15 次 |
| Docker 当时内存 | 627.1 MiB | 每台 590.7–623.8 MiB，合计 3006.5 MiB |

P95 为 20 个排序样本的第 19 个。观察器串行真实 IO 使实际间隔大于配置的 3 秒，未将配置值冒充实测。五台停止后观察 45.0013 秒，各台 2–3 次检查，开始间隔 15.7923–15.8359 秒；证明停机后降低探测频率。两台直接并发真实预览均为 PNG、各 654581 bytes，共 0.9104 秒；这不证明前端并发上限，前端上限由独立组件回归覆盖。

五台均由本轮 HTTP 创建，脚本只对记录的 deviceId 且 workspace 归属匹配者调用生产删除；最终 runtime.verify_deleted 全部 missing。没有清理外部实例、镜像或卷；本轮 HTTP 客户端与服务已退出。

## 验证命令与边界

```sh
npm exec --offline --yes --package=node@22.23.2 -c 'npm test -w @autoflow/desktop -- src/renderer/domains/android/tests/ManagementTools.test.tsx src/renderer/domains/android/tests/ManagementOverview.test.tsx src/renderer/domains/android/tests/DevicePreviewVisibility.test.tsx'
uv run --project apps/backend pytest apps/backend/tests/unit/test_android_observations.py apps/backend/tests/contract/test_android_management_devices.py -q
npm exec --offline --yes --package=node@22.23.2 -c 'npm test -w @autoflow/desktop -- --maxWorkers=1 && npm run typecheck && npm run lint && npm run openapi:check && npm run build'
```

结构4/4、脚本95/95均exit 0：[输出](2026-09-24-observation/scripts-structure.log)；迁移回归[6 passed，1.05s](2026-09-24-observation/migrations.log)。脚本测试生成的三份Studio清单已恢复为原字节，[前后SHA-256一致](2026-09-24-observation/protected-files.json)。最终[完整前端门禁](2026-09-24-observation/full-frontend.log)exit 0：424文件/5651项通过，722.44s；类型/lint/OpenAPI/build全部通过，renderer构建32.97s。[两份QA脚本Ruff](2026-09-24-observation/qa-ruff.log)通过。本轮后端产品源码未变，完整后端仍引用上一提交范围内的 [4048 passed / 26 skipped](2026-09-24-bulk-actions/full-backend.log)，不称为本轮重跑。

真实桌面隐藏页、前台交互延迟和新批次入口仍 [blocked：Mac 锁屏](2026-09-24-observation/desktop-blocked.txt)，需要用户手动解锁后继续同链。10 台仍受 Lima 7921 MiB 小于最低 8192 MiB 阻塞；专用 GApps/账号链条件未变。本轮只补足 1/5 台后台计数与本机 API/内存记录，不关闭 T16、AM3 或完整目标。历史 RED 缺证没有追认。
