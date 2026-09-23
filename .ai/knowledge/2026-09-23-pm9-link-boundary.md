# PM9 环境关联跨项目身份与整组原子性

日期：2026-09-23。状态：confirmed（本机 HTTP/SQLite 与真实浏览器既有关联竞争子场景）；同源码三平台 CI 在 Intel 单 job 重跑后 success，ARM 隔离安装 success；完整发行仍 pending。来源：`apps/backend/tests/contract/test_project_environments.py`、`test_real_project_batch_http[data-link-race]`、`docs/project-management/implementation/pm9/link-boundary-follow-through.json`。

DATA-LINK-02 原台账仅有同环境重复关联与未授权替换规则测试，缺跨项目身份与整组断言。本次反例先证明：修复请求可把本地记录的 `recordRef.projectId` 伪造成另一个项目，同时保留本地 table/generation/key；仓库只核对实际行归属，因而旧实现错误完成关联。共享 `load_bind_targets` 与 `bind_records` 均核对引用项目和权威项目一致，拒绝不一致及缺失身份，失败不改变同组记录链接版本。

两项目实例和固定环境 ID 的隔离、保存后混合目标失败保留唯一环境、伪造身份修复拒绝、正确修复仅关联，以及提交前并发版本冲突组回滚已直接测试。本机全后端 3479 passed/77 skipped（2 条依赖弃用警告）、33 项契约/规则、真实 browser worker 的 data-link-race 1 项（包含 End 保存后的伪造项目身份修复拒绝、原环境不重存和正确修复）、Ruff 和 mypy407 通过。此证据只使 DATA-LINK-02 partial；由 worker 直接生成伪造 End 目标及完整业务验收仍缺，`releaseAccepted=false`。历史 dadb24a1 三平台 CI 和 ARM 隔离 DMG 不覆盖新 guard。

2026-09-23 同源码 ARM 打包补证（confirmed，单机范围）：Actions 35846519367 的 macos-15 job success；后端 3479 passed/77 skipped、前端 5471 passed、选定真实 worker 29 passed/11 deselected，包内桌面报告 passed。下载 ARM DMG SHA256 `bde5e6b263c9cb86fadd3e9f1bc9ca5aa66e83bb7f3283c4901226545bdba40f`，`hdiutil verify`、只读挂载、`ditto` 隔离复制、卸载镜像后运行原版完整桌面脚本 passed。来源：`docs/project-management/implementation/pm9/installed-arm-link-guard-candidate.json` 与 `qa-runs/2026-09-23-ci-c165-arm/project-desktop.json`、`qa-runs/2026-09-23-arm-link-guard/project-desktop.json`；Windows 完整 job 成功；Intel 首次 job 的测试和打包 smoke 通过，DMG 临时盘弹出 Resource busy，失败日志及完整产物已留存，同源码单 job 重跑后完整成功；Intel DMG 校验、只读挂载并确认 x86_64 应用，未在 Intel 实机运行。物理发行与 Google/OAuth 未验。
