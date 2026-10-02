# AutoFlow M0–M6 整改交接

日期：2026-09-30（America/Los_Angeles）。状态：confirmed 交接快照；整改整体 in_progress，不能标记完成。
来源：本地 Git、GitHub Jobs API、已下载的完整 job 日志与基准产物、[实施记录](2026-09-30-remediation-m0-implementation.md)。CI 快照取于 2026-09-30 23:52 左右（UTC 2026-10-01 06:52），接手时必须刷新。

## 1. 接手结论与用户授权

- **文档修订、一致性检查、独立复审已完成；M0 实现及本地验收已完成，远端验收未完全完成。M1–M6 生产实现尚未开始。**
- 完整目标仍是 M0–M6。按依赖推进；M2–M6 前置完成后细化步骤、审查再实现，无须逐阶段询问是否开工。每个切片包含必要的后端契约、实现、前端和测试。
- 本次用户要求：提交全部已写代码、提供交接文档，并**推送到远端 baseline**。这次 baseline 合并/普通推送已有明确授权；它不意味着 M0 验收通过。部署发布、破坏性数据删除、历史改写和外部消息仍未授权。
- 当前 agent 在完成交接推送后停止继续实施，由下一位 agent 接手。不要把交接完成当作整个整改完成。
- **先关闭 M0 的完整 CI 与 AC0-07，再进入 M1。** 不降低门槛，不把 skipped、cancelled、旧提交结果或单项步骤成功算成整阶段通过。

## 2. 仓库、分支与合并范围

| 项目 | 位置 / 状态 |
| --- | --- |
| 主工作区 | `/Users/zhangtiancheng/Documents/projects/autoflow` |
| 本轮实施工作树 | `/Users/zhangtiancheng/.codex/worktrees/remediation-m0/autoflow` |
| 实施分支 | `codex/remediation-m0` |
| 交付目标 | `origin/codex/architecture-baseline`，GitHub 默认分支 |
| 仓库 | `1127152834/auto-flow` |
| 文档修订起点 | `547a0785` |
| 最新代码 / 烟测诊断提交 | `775a1cffaa934b977d898f2a67341edccc65b8a9` |
| 交接前本地 HEAD | `a55fc807`（其后本交接合并提交包含本文；实际最终 SHA 用 `git log -1` 查询） |
| 本次保留的远端新增文档 | `d45e8bc3`、`fb06fe60`：执行环境扩展规格、计划及安卓开源参考 |

远端 baseline 原有两笔新文档与整改分支分叉，本次合并保留双方历史，不强推。唯一文本冲突在 `.ai/plans/2026-09-30-remediation-program.md`：保留整改 r2 状态、依赖与证据，同时保留独立 E1–E6 proposed 计划入口。这些扩展没有自动纳入本轮 M0–M6 已授权实现范围。

本次合并相对原整改代码只增加/合并文档，不修改业务代码。已有工作树和忽略的测试产物保留，不删除其他分支或用户数据。

## 3. 权威文档与里程碑顺序

先读 `AGENTS.md`、`.ai/README.md`、`.ai/memory/project-context.md`、`docs/PROJECT_STRUCTURE.md`，然后按以下入口读取；历史会话中的早期“待实现”描述由后续明确证据替代，不能只读文件开头。

- [阶段索引](../plans/2026-09-30-remediation-program.md)
- [总纲](../../docs/superpowers/specs/2026-09-30-remediation-roadmap.md)
- [整改决策及持续授权](../decisions/2026-09-30-remediation-program.md)
- [本轮文档修订与复审记录](2026-09-30-remediation-plan-revision.md)
- [完整 M0 实施/失败/复验记录](2026-09-30-remediation-m0-implementation.md)
- [实际基准与 M1 诊断](../knowledge/2026-09-30-remediation-baseline.md)

| 阶段 | 当前状态 | 接手要求 |
| --- | --- | --- |
| M0 基准与守门 | Task 1–9 实现、独立复审及本地验证完成；完整远端验收待收口 | [规格](../../docs/superpowers/specs/2026-09-30-remediation-m0-baseline-guardrails.md)、[步骤计划](../../docs/superpowers/plans/2026-09-30-remediation-m0-baseline-guardrails.md) |
| M1 止血 | 未实施；步骤级计划已修订；做过只读测量 | M0 退出后按[计划](../../docs/superpowers/plans/2026-09-30-remediation-m1-stop-silent-failures.md)推进 |
| M2A/B/C | 未实施，任务级计划 | A 可靠性、B 数据契约、C 触发与网页扩展；分片细化、审查 |
| M3 吞吐 | 未实施 | 依赖 M2A/B 与原生基准；M2C 不阻塞 M3；优化以测量为依据 |
| M4 身份 | 未实施 | M3 资源接口稳定后；perIdentity 在此阶段交付 |
| M5A/B/C/D 体验 | 未实施 | 各切片分别依赖 M1、M2A/B、M4；先业务闭环，视觉完善不阻塞 M5B |
| M6 收敛 | 未实施 | 兼容、迁移和剩余执行入口门禁通过后才清理旧实现 |

M2–M6 对应规格和计划均由阶段索引链接。旧 13 周排期已 superseded；历史 QA 截图清理不属于 M0 退出条件。

## 4. 已完成的实现与重要修复

M0 已加入真实 SQLite 领取基准、G4 实际节点/事件基准、持久事件提交基准、数值报告及源码起止 manifest；LoopLagMonitor 接入 sidecar 生命周期；本地故障站点、真实 TCP/SQLite/worker/浏览器黄金链；配置/UI 债务 ratchet；push 离线基准及独立 golden workflow。

CI 揭示的问题按真实调用链修复，关键提交便于追查：

| 提交 | 内容 / 不可丢失的边界 |
| --- | --- |
| `903a0639` | Intel macOS 的 MediaPipe/OpenCV 等平台依赖锁兼容；未删除平台或功能 |
| `1219e824` | Windows 类型与文件系统能力边界；不以虚假默认值绕过安全检查 |
| `5fd51667`、`52ada4e0`、`ba9830f5` | UTF-8 差分夹具、原生 Android 备份边界、模块局部 POSIX 信号模拟；跳过不计通过 |
| `ca5b3704` | 原生场景通过当前 automation 所属 workflow API 创建，保留业务断言 |
| `d9b8b8d6` | worker 动态 End 名称解析、host 准入与 durable payload 校验；禁止覆盖冻结静态名称 |
| `d41ae18d` | 终态 Run 且人工证据已终态后清理工作副本；未知/未保存/保存失败仍受保护 |
| `e251fbe8` | 只有已核验的内部人工完成回调可走 trusted_manual；公共 End 权限不放宽 |
| `e6477b69`、`728cf027` | 信号 EPERM 后进入已有有界退出核验；仍存活/身份未知不释放容量和目录 |
| `d8d3210e` | 严格进程归属瞬时不可读时共享两秒复查；入 owned 集合前复核 birth，禁止 PID 重用污染旧子树 |
| `dc26be2a` | 原生初始化测试使用既有执行器 30 秒预算及 90 秒外层限时；保留失败断言 |
| `03c33c4a`、`c585a7aa` | 桌面/HTTP/业务组合烟测夹具对齐当前 End 与授权契约，保留修复、旧副本冲突、人员不变等断言 |
| `775a1cff` | 基础桌面启动失败时保留状态白名单与现有脱敏 sidecar 日志，再抛原异常；仅增强诊断，不宣称修好未知远端原因 |

独立评审曾发现进程归属中的父 PID 重用 P1，已由反例 RED→GREEN 和复核关闭。详细测试数、初始失败及修复边界均在实施记录，不再重复整套验证。

## 5. CI 快照与接手后第一步

### 最新代码候选 `775a1cff`

[run 36820172667](https://github.com/1127152834/auto-flow/actions/runs/36820172667)

- ARM job `110233924148`：步骤 1–41 中适用检查已通过（包括打包整链、安装器、桌面/浏览器烟测），**最终后端步骤 42 运行中**。
- Intel job `110233924091`：首次完整后端步骤 22 运行中。
- Windows job `110233923924`：首次完整后端步骤 22 运行中。
- 三平台节点浏览器初始化/清理步骤均 success；Windows 平台边界、桌面设置路径和 HTTP 写入预检 success。

### 保留的归属修复候选 `d8d3210e`

[run 36817654197](https://github.com/1127152834/auto-flow/actions/runs/36817654197)

- **ARM job `110226128259` 已 completed/success。** 本次交接已获取终态完整日志：首次后端 5348 passed / 137 skipped / 24 deselected / 2 warnings（1863.17s）；最终后端同计数（1573.09s）；两次前端均 5972 passed / 454 文件；真实 worker 选集 44 passed / 31 deselected / 1 warning（541.65s）；离线基准 21 passed（2.84s）。全部 job 步骤及上传成功，不等于最新候选全矩阵通过。
- Intel job `110226128439`：后端、基准、前端、构建、真实 worker、HTTP/源码桌面通过，backend:build 步骤 30 运行中。
- Windows job `110226128459`：首次完整后端步骤 22 运行中。

### 较早候选

- [run 36800414483](https://github.com/1127152834/auto-flow/actions/runs/36800414483) @ `c585a7aa`：ARM `110173439919` success；Intel `110173439678` 旧 EPERM failure 已有后续修复；Windows `110173439898` 仍运行于步骤 22。Windows 持续时间很长，但 API 仍显示 live；不能凭持续时间宣称失败、完成或擅自重启。终态后优先检查日志。
- run `36808514086` @ `98e95dba` 已退役，不需反复轮询：ARM 最终回归归属读取失败由 `d8d3210e` 修复；Intel 基础源码桌面启动等 60 秒只得到 `health=null`，远端根因**未知**；`775a1cff` 增强后续失败诊断。Windows cancelled，不计通过。

推送 baseline 会产生新的 baseline push CI。接手以新 run 的实际 SHA 为准；旧候选证据保留但不能替代新合并提交的验收。不要为了追加纯证据反复推送整改分支，避免取消尚有价值的运行。

### 接手顺序

1. `git fetch origin`，核对本地 HEAD、工作区和 baseline；查新 baseline push 的 run，再刷新上述仍运行任务。读取失败 job 的完整日志，定位后做最小修复及针对性验证。
2. 若 API 仍是 in_progress，等待该任务；日志尚未上传的 404/BlobNotFound 不是测试失败。GitHub 登录页要求登录时不要声称读到了实时日志。
3. 修复所有实际失败并核对同一候选的跨平台回归、ratchet、离线基准及产物。
4. baseline 已包含 `.github/workflows/golden.yml` 后，**手动触发 rows=30**，记录精确 SHA/run，核对真实内核 G2/G3、逐行证据、数值 JSON 和 manifest。此项目前未运行，AC0-07 仍 pending。可用已认证 GitHub 工具；CLI 可用时命令为：`gh workflow run golden.yml --repo 1127152834/auto-flow --ref codex/architecture-baseline -f rows=30`。
5. 按 M0 规格逐条复核 AC0-01–08、同步计划/知识/会话状态并提交，才进入 M1。M1 从实际调用链与已有步骤计划开始；M2–M6 依赖满足后再细化和独立审查。

## 6. 基准与验证证据的边界

- 本机真实 G2/G3 101 行：G2 99 成功/2 预期故障；G3 100 成功/1 提交丢响应故障，lose 行恰好提交一次。未知结果台账的缺口单独 strict xfail，留给 M2，不能删除 xfail 或包住其他正确性断言。
- 干净 `f60b3cac` 串行五样本/场景：领取 key/field 中位数 726.047/998.982ms；G4 **0.228ms/节点**、5.001 事件/节点；持久事件 p50/p99 中位数 1.177/1.587ms。注意是 0.228，不是 4.228。精确环境和五样本见基准文档。
- `d8d3210e` ARM 基准 artifact `11143900429`，ZIP SHA256 `bef0b7260af5b2f83bcf6976a12c605a4d873249ab3d223b637ceab48c09bac1`。
- `d8d3210e` Intel 基准 artifact `11144222164`，ZIP SHA256 `3c70bab17e33e81d90a32e156bfab912b8e1bfd1fee52f13ad6f95f44c2c0114`。
- `775a1cff` ARM 基准 artifact `11144220276`，ZIP SHA256 `4362a1e4c6afe2eab1c0eed736f824eb0d219f4bd6581afb6ff8c3336d4f36a4`。
- 上述三个小 ZIP 已实际下载、复算哈希、逐对核对报告/manifest 的 sourceBefore/sourceAfter、dirty/comparable、提交身份与规模；**每场景仅一个样本，不用于跨机或跨运行性能提升结论**。
- `d8d3210e` ARM PM9 artifact `11145965448`，日志大小 890808358 字节、上传摘要 `2182acea8531beffe775bfe34c57fca6eafaa8f4cb87dd655979cb3716f88c5f`。未下载、未本地复算、未目视检查其中截图；GitHub 下载连接器 512MiB 上限曾阻止同类大包，避免重复无效尝试。完整 job 日志可获取文字报告。
- 本机未签名 ARM App 的 HTTP/桌面/业务组合整链已通过，26 张本地截图中未保存清理、关联修复刷新已目视检查；不代表 Windows、Intel 或安装器安装验收。SSE 关闭日志中仍有 Uvicorn graceful timeout/CancelledError 警告，脚本退出成功不等于无警告。

## 7. M1–M6 已知缺口，禁止遗失

- **M1 线程领取微基准尚未达标**：五样本 threaded p50 16.072–17.096ms，高于 10ms 目标；max 46.704–56.258ms 满足 250ms；空闲 p50 2.059–2.119ms。不要仅加 `asyncio.to_thread` 就宣布完成。
- 剖析发现万行领取构造 10000 个 Candidate、330032 次递归冻结、46836 次 Python 比较回调、123676 次 JSON 读取；不能仅凭此断言单一 GIL 根因。不能降低候选数漏行或放宽阈值。完整 SQL/台账优化遵循 M3 依赖。
- M1 计划已补 WAL 静止 checkpoint 成功后才复制、busy/error 保留原因、执行名额释放唤醒持久暂停调度、有界 stderr 排空与端到端诊断。不要恢复旧示例。
- 所有领取模式都必须阻止未知结果；自动重试需看整个 Task 已发生的副作用；历史配置不能静默启用新语义。
- **M6 历史 End 兼容缺口真实存在**：历史 `retainEnvironment.recordTargets` 包装项与当前 flat End bare RecordRef 不等价，旧 normalizer 只搬运列表；更新新建测试夹具不等于修好了历史持久数据迁移。保留升级/导入/冻结内容反例，禁止通过放宽 fencing“兼容”。
- M2B 前置稳定输出元数据和后端 previewWrites；M4 新种子唯一但迁移保留历史重复，不合并不同账号身份；代理粘性不等于实际出口固定。
- E1–E6 执行环境扩展是本次保留的独立 proposed 文档，不能挤占或被误记为已完成 M0–M6。历史清理、Android/iOS 扩展遵守各自授权边界。

## 8. 本机运行与工具注意事项

实施工作树共享主工作区的忽略依赖/虚拟环境。最重要的是**显式 PYTHONPATH 指向正在测试的 checkout**，否则子进程可能导入旧主目录源码。

```bash
# 在实施工作树中运行；若换工作区，同步更换所有绝对路径。
cd /Users/zhangtiancheng/.codex/worktrees/remediation-m0/autoflow
export PYTHONPATH="$PWD/apps/backend/src"
export UV_NO_SYNC=1
export UV_PROJECT_ENVIRONMENT=/Users/zhangtiancheng/Documents/projects/autoflow/apps/backend/.venv
export AUTOFLOW_TEST_CLOAKBROWSER='/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2/Chromium.app/Contents/MacOS/Chromium'

node scripts/ratchets.mjs
npm run test:scripts
npm run typecheck
npm run lint
npm run openapi:check
uv run --directory apps/backend ruff check .
uv run --directory apps/backend mypy src
# 仅在改动/未闭合问题要求时运行全量，避免重复消耗：
uv run --directory apps/backend pytest -q
npm test
npm run build
```

- Python 实际解释器：`/Users/zhangtiancheng/Documents/projects/autoflow/apps/backend/.venv/bin/python`。冻结差分 reference 必须为 `5ccb900e`；CI 自行 checkout，不要改冻结代码来让比较通过。
- `gh` 曾因 token 失效不可用，但 Git fetch/push 和 GitHub 连接器可用；接手重新检查，不打印凭据。按 SHA 查 push CI 使用公开 REST `/repos/1127152834/auto-flow/actions/runs?head_sha=<SHA>`；`github_fetch_commit_workflow_runs` 曾只返回 PR 触发运行，空数组不证明没有 push CI。
- 连接器工具：`github_fetch_workflow_run_jobs`、`github_fetch_workflow_job_logs`、`github_fetch_workflow_run_artifacts`、`github_download_workflow_artifact`。job 终态前下载日志可能 404；跳过的 probe job `steps` 可能 null。
- 本机忽略产物在 `.superpowers/sdd/2026-09-30-remediation-m0-baseline-guardrails/` 与 `artifacts/pm9/`。它们**不会随 Git 推送**；Git 中实施记录是持久索引，原始基准也可从远端 artifact 获取。`progress.md` 可能滞后，不覆盖 Git 和正式记录。
- 当前无需要下一位接管的本地 pytest/Electron 构建进程；远端任务继续运行。复用现有工作树，不删除共享依赖或其他历史工作树。

本次交接合并验证：`npm run test:structure` 4/4 通过；`node scripts/ratchets.mjs` 通过（127/2008/81/3247）；32 个本地文档链接存在；`git diff --cached --check` 通过。相对交接前 HEAD 的合并改动仅 Markdown，未重复运行无源码改动的全量回归。最终新 baseline CI 仍需由接手 agent 核对。

## 9. 可直接发送给下一位 agent 的任务

> 从 baseline 最新代码开始，先阅读 `.ai/sessions/2026-09-30-remediation-handoff.md` 和 M0–M6 阶段索引。刷新 Git 与交接表中的 CI 状态，先处理 M0 仍未关闭的跨平台回归，手动运行默认分支 golden rows=30 并核对产物，按规格完成 M0 退出验收。随后依照已授权的 M1–M6 依赖和步骤计划持续实施；M2–M6 在前置完成后细化、审查再执行，不需要逐阶段确认。每个切片按真实证据验证并提交、同步 `.ai`；不得把跳过、旧候选或单项通过当整阶段完成。保留用户数据和已知兼容缺口，不部署、不历史改写、不发送外部消息。

## 最新状态（2026-10-02，换到 Claude Code 继续）
- 默认分支 codex/architecture-baseline 已含 M0 修复与 M1 全部代码；其他分支内容均已合并（仅 diag/windows-ocr-1、diag/windows-strict-1 各有 1 个一次性诊断探针提交，无需合并）。远端旧分支删除被本机权限拦截，需用户执行：`git push origin --delete claude/remediation-specs codex/remediation-m0 codex/remediation-m0-ci-validation codex/remediation-m0-ownership-validation diag/desktop-intel diag/windows-annot-1 diag/windows-annot-2 diag/windows-annot-3 diag/windows-annot-4 diag/windows-focus-android diag/windows-full2 diag/windows-ocr-1 diag/windows-regression diag/windows-strict-1`。
- 用户决定：Intel 不再支持/验证；OCR 节点不投入测试；M1 完成后停止，M2–M6 在 Claude Code 中继续。
- 立即要做：(1) 看 60ff484（或之后）的 CI，确认 ARM+Windows 同一提交全绿；(2) 追 G2 failure_reason_ratio=0.0（见 M1 记录）；(3) Mac 上跑 AC1-09/AC1-10 基准；(4) 以上完成后把程序索引中 M1/M0 标 done。
- CI 注意：`ci.yml` 并发策略会取消同分支上一轮，连续推送会丢失仍在跑的 Windows 第二遍后端回归（约 1 小时 20 分）；Windows 日志无法下载，用 check-run 注解取证。
