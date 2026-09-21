# 安卓模拟器管理验收证据（2026-09-22）

- 状态：`partial`；代码验证通过，真实 macOS/Lima/ReDroid、网络和测试账号验收 `blocked`。
- worktree：`codex/android-management-complete`，起点 `a92f0688f206d4339ff4468c1871f3ccdd6816dc`。
- 主工作区既有 Studio 未提交改动未复制、未修改。

## 已执行

| 类别 | 命令 | 实际结果 |
| --- | --- | --- |
| 后端 Android/迁移/契约 | `cd apps/backend && uv run pytest ... -q`（Android 聚焦集合，含迁移、操作、诊断、会话、镜像、备份、容量、清理） | `44 passed, 1 warning` |
| 前端 Android | `cd apps/desktop && npm exec vitest run src/renderer/domains/android/tests` | `7 files, 17 passed` |
| 前端类型 | `npm run typecheck` | 通过 |
| OpenAPI | `npm run openapi:generate`、`npm run openapi:check` | 通过 |
| 前端 lint/build | `npm run lint`、`npm run build` | lint 通过；build 完成并有依赖注释 warning |
| 迁移 | Alembic 临时 SQLite 升级及旧 Android 历史回归 | head=`am01_management_operations`，通过 |
| 结构检查 | `npm run test:structure` | `4 passed` |
| 全脚本基线 | `npm run test:scripts` | `92 passed, 3 pre-existing Studio failures` |

## 已覆盖

只读环境诊断、显式 `unknown`、workflow=false；独立 Android operation 表、workspace/request 幂等、摘要冲突 409、状态栅栏、needs_verification、分页和迁移；现有 provider 归属校验、生命周期锁、generation/sequence；控制会话 clientSessionId/generation heartbeat；镜像登记、不可变 imageId、引用阻止删除、模板读取/归档入口；persistent 默认创建并拒绝 temporary；停机备份前置条件、受限目录/权限、格式摘要、exact imageId 恢复边界；诊断脱敏；容量未知阻止准入；APK/应用安全边界；前端诊断面板和会话控制器。

## 阻塞项与风险

- 当前验收主机没有可核实的 Docker/Lima/ReDroid 实例、ADB/scrcpy 联机设备、Google 组件网络和专用测试账号；真实创建、启动、手动窗口、应用安装/中文输入、备份恢复演练、GApps 验证全部 `blocked`，没有用 mock 结果代替。
- 实机探测摘要：`docker info` 无法连接 `/Users/zhangtiancheng/.docker/run/docker.sock`；`limactl list` 显示 `autoflow-redroid Stopped`；`adb devices` 无设备；`scrcpy` 二进制存在但无设备可连接。
- `npm run test:scripts` 的三个 Studio inventory/reference 失败与本模块无关，未扩大范围修复；依赖安装/Node 版本会影响其复现。
- AM3/AM4 完整 UI 批次编排、聚合观察和备份恢复真实演练仍需后续实机验收；应用停止/卸载/清除接口已加保护，但未实机验证。
