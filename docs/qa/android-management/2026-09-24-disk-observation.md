# 宿主与 VM 磁盘观测验收

- 日期：2026-09-24；基线：`de0708db`；状态：本切片验证通过（confirmed），完整 AM1–AM4 仍为 partial。
- 候选源码：[SHA-256 清单](2026-09-24-disk-observation/candidate-hashes.json)；保护的三份Studio修改未纳入Android变更。
- 需求：AM-R12 的宿主工作区与 Linux VM 可用空间分别展示；创建/拉取操作前准入仍未实现，不以本切片替代。
- 变更：`MacAndroidRuntime.environment` 分别读取 workspace 文件系统与 Docker info 的实际 `DockerRootDir`，VM 只读 `statvfs` 使用可用块而非总空闲块。通过 argv 传参；任一探测失败仅该侧为 null；已知 0 返回磁盘 fail。HTTP/OpenAPI 与 RuntimeDiagnostics 同步，页面分别显示 GiB，完整字节数置于 title。没有新数据库字段或迁移。

## RED → GREEN 与真实证据

| 验证 | 实际结果 |
| --- | --- |
| runtime + HTTP 契约初始 RED | 9 failed，76 deselected，0.45s；缺失数值字段导致失败。[日志](2026-09-24-disk-observation/backend-red.log) |
| runtime + HTTP 契约 GREEN | 85 passed，1 warning，6.76s；覆盖独立容量、宿主/VM 0、负值、单侧超时/错误和旧 HTTP 兼容。[日志](2026-09-24-disk-observation/backend-focused.log) |
| UI RED → GREEN | 3 failed / 2 passed → 5 passed，1.32s；两侧容量、0 与未知、旧服务省略字段。[RED](2026-09-24-disk-observation/frontend-red.log)、[GREEN及类型](2026-09-24-disk-observation/frontend-focused.log) |
| 真实 Mac/Lima，只读 HTTP 路由 | 宿主 195919953920 字节；VM Docker 33445064704 字节；disk pass，available true。独立临时 workspace；没有设备写入。TestClient 仅承载进程内 HTTP，provider 和 Lima 均为真实调用；不冒称网络服务重启验收。[结果](2026-09-24-disk-observation/real-http.json) |
| 最终构建真实桌面 | 宿主182.34 GiB、VM31.15 GiB；点击重新检查后checkedAt由00:23:08更新至00:23:14 UTC。独立空工作区，自建Electron已退出；只读库核对0台设备、1条check操作且succeeded。[记录](2026-09-24-disk-observation/desktop.json) |
| Android全部后端 | 485 passed，2 warnings，36.57s；[日志](2026-09-24-disk-observation/android-backend.log) |
| Android全部前端 | 14文件 / 180 passed，9.53s；[日志](2026-09-24-disk-observation/android-frontend.log) |
| 迁移 | 6 passed，1.23s；[日志](2026-09-24-disk-observation/migrations.log) |
| 全量后端 | 4069 passed，26 skipped，2 warnings，880.33s，exit0；[日志](2026-09-24-disk-observation/backend-full.log) |
| 全量前端及工程门禁 | 424文件 / 5670 passed，213.55s；类型、lint、OpenAPI、结构4/4、脚本95/95、build全部exit0；renderer35.67s。[完整日志](2026-09-24-disk-observation/frontend-full.log) |
| 独立增量审查 | 无新增 Critical/Important/Minor；只读静态审查。[范围](2026-09-24-disk-observation/review.md) |

## 命令

```sh
uv run --project apps/backend pytest apps/backend/tests/unit/test_android_runtime.py apps/backend/tests/contract/test_android_management_environment.py -q
npm exec --offline --yes --package=node@22.23.2 -c 'npm run openapi:generate && npm test -w @autoflow/desktop -- src/renderer/domains/android/tests/RuntimeDiagnostics.test.tsx && npm run typecheck'
uv run --project apps/backend python docs/qa/android-management/scripts/disk-observation-smoke.py
# 完整前端门禁实际执行命令（根脚本未转发maxWorkers，实际4 workers）
npm exec --offline --yes --package=node@22.23.2 -c 'npm test -- --maxWorkers=1 && npm run typecheck && npm run lint && npm run openapi:check && npm run test:structure && npm run test:scripts && npm run build'
# 在apps/backend目录
uv run pytest tests/contract/test_android*.py tests/unit/test_android*.py tests/integration/test_android*.py -q
uv run pytest -x -q
# 在仓库根目录
npm exec --offline --yes --package=node@22.23.2 -c 'npm test -w @autoflow/desktop -- src/renderer/domains/android'
uv run --project apps/backend pytest apps/backend/tests/integration/test_android_m4_migration.py apps/backend/tests/integration/test_migration_heads.py -q
uv run --project apps/backend ruff check apps/backend/src apps/backend/tests
uv run --project apps/backend python -m compileall -q apps/backend/src/autoflow
```

Ruff/compileall已通过；新增 QA 脚本首次 import 排序错误由 Ruff 修正，复查通过。全仓后端已结束并通过；26项skip按套件条件保留，2项warning为Starlette anyio弃用及故意构造重复APK Manifest。脚本门禁保留已有MODULE_TYPELESS_PACKAGE_JSON提示，不改与Android无关的模块配置。前端实际使用配置的4 workers：从根npm转发的maxWorkers参数未进入vitest；进程argv已核对，不冒称单worker。脚本门禁结束后三份Studio文件逐字节核对/恢复为本轮前原哈希；inventory脚本另生成的capabilities.json差异已恢复本轮开始时的HEAD字节。

剩余：创建/拉取磁盘准入、完整批量/未知拉取桌面链及 T14/T16 等原未验项仍未关闭；十台/GApps外部条件未变。宿主 workspace 容量不是 Lima 虚拟磁盘宿主文件容量，也不是任何操作的所需空间估计。
