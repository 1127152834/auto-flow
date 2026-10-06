# Android S1「AI 测试」验收记录

- 日期：2026-10-06
- 分支：`codex/android-s1-ai-testing`（合并基线 `3ea4d314`，HEAD 为 Task 10 提交 `07798095` 之后）
- 状态：软件验证 confirmed；AC-S1-5（全部门禁 exit 0）本机**未满足**，待 CI 复跑；真实设备验收 AC-S1-1/2/3 blocked（见下）
- 规格：`docs/superpowers/specs/2026-10-04-android-module-audit-and-ai-testing-design.md` §6
- 证据位置：命令输出保存在本机临时目录，不入库（整改期规则 7）；无截图。§1、§2、§4 的数字是终审修复前（HEAD `8616abae`）的全量运行结果，修复后的定向验证见 §5

## 1. 门禁汇总（AC-S1-5）

| 门禁 | 命令 | 退出码 | 摘要 |
| --- | --- | --- | --- |
| 后端全量 | `pytest tests`（共享 venv，`--no-sync`） | 1 | 4981 passed、866 failed、228 skipped；其中 864 项失败已在基线逐项复现（见 §4），另 2 项未在基线复跑，原因见 §4 |
| 桌面单测 | `npm test` | 1 | 463 个文件通过、5 个失败；6007 passed、4 failed；失败均为既有环境问题（见 §4） |
| 类型检查 | `npm run typecheck` | 0 | tsc --noEmit 无输出 |
| 代码检查 | `npm run lint` | 0 | eslint 无输出 |
| OpenAPI | `npm run openapi:check`（`PYTHONPATH` 指向本工作树 `apps/backend/src`） | 0 | 生成物与后端一致 |
| 构建 | `npm run build` | 0 | built in 29.87s |
| 结构测试 | `npm run test:structure` | 0 | fail 0 |
| 脚本测试 | `npm run test:scripts` | 1 | 120 项，115 通过、5 失败；5 项均缺冻结源 `reference/WebRPA`（见 §4） |
| 棘轮 | `node scripts/ratchets.mjs` | 0 | unreadConfigKeys=113 paletteClasses=2008 secondIconLibraryFiles=81 docsPng=3247（无新增） |

结论：三项非零退出码都只由既有环境缺失造成，不是本分支回归；因此 AC-S1-5 要求的「全部 exit 0」在本机**未满足**，只能在具备冻结源与符号链接权限的环境（如 CI）复跑确认。

## 2. 密钥检查（AC-S1-4）

方法：用测试密钥跑 Task 7 服务测试（密钥 `sk-very-secret-777`）、Task 3 工具测试与 Task 4 桥接测试（密钥 `sk-super-secret-123`），共 54 项全部通过；然后在该次运行的 pytest 临时目录（含 27 个 db/日志文件）中按字节搜索两个密钥。

| 密钥 | 范围 | 命中文件数 |
| --- | --- | --- |
| `sk-very-secret-777`（服务测试） | 临时目录全部文件（含 sqlite、日志） | 0 |
| `sk-super-secret-123`（工具/桥接测试） | sqlite / 日志文件 | 0 |
| `sk-super-secret-123` | 其余 9 个文件 | 9，均为假桥接进程自己转储的子进程环境（`dump.json`、`env.json`），即测试中对「密钥只出现在子进程环境」的断言对象 |

结论：数据库、日志、产物中未出现密钥；唯一出现处是被测的子进程环境转储，符合预期（预期 0 命中，不含子进程环境断言）。服务层另有断言：仓储写入记录、数据库字节与日志均不含密钥（`test_secret_never_written_to_repository`）。

## 3. 真实设备验收（需用户单独授权）

| 编号 | 场景 | 状态 | 原因 |
| --- | --- | --- | --- |
| AC-S1-1 | Windows + 外接 AVD 完成「打开设置搜索 Wi-Fi，然后打开浏览器访问 example.com」 | blocked | 本机无 adb 设备；真机验收需用户另行授权，未尝试 |
| AC-S1-2 | Mac + 托管 ReDroid 同上 | blocked | 无 Mac 与托管设备；未尝试 |
| AC-S1-3 | 停止、超时、强杀子进程、重启 AutoFlow 后的恢复 | blocked | 依赖真实设备与运行中的 ARTEMIS；单元测试已覆盖取消、超时、重启恢复为「待核实」，但不替代真机 |

以上三项不得记为通过。

## 4. 已知既有失败与证据

判定方法：把合并基线 `3ea4d314` 用 `git archive` 导出到临时目录，用同一环境、同一 `PYTHONPATH` 机制运行同一批用例，对比失败集合。`git diff --stat 3ea4d314 HEAD` 不含 `scripts/`、`reference/`、`apps/desktop/src/main/`、`apps/desktop/src/renderer/domains/workflows/`。

| 类别 | 数量 | 原因 | 证据 |
| --- | --- | --- | --- |
| 后端 `tests/differential/workflows/*` 执行器一致性 | 795 | 缺冻结的 WebRPA 源（工作树无 `reference/WebRPA`） | 基线单独运行同目录：795 failed、261 passed，失败集合与本分支完全相同 |
| 后端其余（符号链接 WinError 1314、真实 worker 子进程、冻结源映射、日志分类等） | 71 | Windows 无创建符号链接权限；缺冻结源；worker 子进程路径 | 基线运行同 71 项：69 failed、2 passed；本分支重跑同样 69 failed、2 passed，失败集合逐项相同。另 2 项（`test_schema_export_cli_outputs_only_json`、`test_pyinstaller_discovers_required_langgraph_modules`）在全量运行时失败，**没有在基线上复跑，不能断言与基线相同**：前者设置 `PYTHONPATH` 指向本工作树后单独运行通过（失败来自共享 venv 的可编辑安装指向主检出，见 common.md）；后者单独运行仍失败，报错为环境未安装 PyInstaller。两者的判断依据是单独运行的报错原因，不是基线对比 |
| 其中 Android 符号链接用例 | 5 | WinError 1314 | `test_android_runtime` 拉取预检 ×2、容量预留 link、备份删除符号链接、备份存储符号链接 |
| 桌面 `kernel-paths`、`project-files/controller`、`settings` 测试 | 3 | `EPERM: symlink` | 失败行均为 `symlink` 调用本身；对应文件未被分支改动 |
| 桌面 `recording-source-parity.test.ts` | 1 个文件 | 缺 `reference/WebRPA` | ENOENT |
| 桌面 `RuntimeDiagnostics.test.tsx:53` | 1 | 日期文案「2026年9月22日」随区域/时区变化 | 文件未被分支改动 |
| `npm run test:scripts` 的 `studio-required-fields` 等 | 5 | 缺 `reference/WebRPA` | ENOENT，`scripts/` 未被分支改动 |

分支本身的 Android/AI 测试：Task 7 服务、Task 3 工具、Task 4 桥接共 54 项通过；其余 AI 测试相关后端与桌面用例（规则、仓储、HTTP、面板、外接设备）在上述全量运行中均无失败。

## 5. 终审修复（2026-10-06）

整分支终审（`.superpowers/sdd/2026-10-04-android-s1-ai-testing/final-review.md`）后的修复，逐项证据见同目录 `final-fix-report.md`：

| 终审项 | 修复 |
| --- | --- |
| #1 托管设备在详情页无法启动测试 | 启动前经 `AndroidConsole.close_for_device` 结束本设备控制台会话；详情页在设备由 AI 测试占用时不再自动建控制台会话 |
| #2 看板没有回到测试的入口 | 看板显示「查看 AI 测试」，进入详情页 AI 测试标签，不建会话 |
| #3 接管/重跑与设备释放赛跑 | 先释放设备再写终态 |
| #4 双迁移 head | 合并最新 `codex/architecture-baseline`，`rm4_android_ai_tests` 接到基线 head，单一 head |
| #5 lint 不通过 | `ruff check src tests` 通过 |
| #6 工作流占用的托管设备出现在外接列表 | 核实：工作流运行已退役（`CurrentAndroidRunBoundary.device_context` 恒为 None），只有控制台与 AI 测试会 `claim`/`connect` 托管设备，二者的序列号都已排除；不改代码 |
| #7 正常关闭记成「已停止」 | 关闭时运行中的测试记为「结果待核实：程序中断，无法确定测试是否完成」 |
| #8 只读实时画面 | 用户裁定：运行中每 2 秒经测试自己的设备连接截图（`GET /runs/{id}/screen`），标注「实时画面（只读）」；不是 scrcpy 视频 |
| #9 产物含密钥 | 桥接对写入或复制的 txt/json/jsonl/html/log/md 产物统一替换模型密钥 |

## 6. 剩余风险

1. 真机未验：ARTEMIS 的步骤事件（IPC）与桥接对真实输出的适配，目前只有无设备探测与假桥接测试；桥接设计了读取 ARTEMIS 数据库的降级路径，但同样未真机验证。
2. 门禁在本机无法全绿：需要具备冻结源与符号链接权限的环境（CI）复跑后端全量、桌面全量与 `test:scripts`，才能满足 AC-S1-5 的「全部 exit 0」。
3. 打包：`apps/backend/autoflow-backend.spec` 已改（纳入桥接），但本机无 PyInstaller，打包产物是否包含桥接与依赖未验证。
4. 迁移：已在合并最新基线后把 `rm4_android_ai_tests` 接到基线 head；若基线在本分支合入前再新增迁移，需要再次调整 `down_revision`。
5. 模型范围：仅 openai / openai-compatible / gemini / anthropic，且 gemini/anthropic 自定义 base_url 会被拒绝（`AI_TEST_MODEL_UNSUPPORTED`）。
6. 前序任务遗留的次要项见 `.superpowers/sdd/2026-10-04-android-s1-ai-testing/progress.md` 中各 Task 的 minor 行（例如历史记录只取首页、离开外接设备页不警告）。
7. AOCI：本次会话无 aoci MCP 工具，未执行 `aoci_maintain` / `aoci_update_entry`，需在有 MCP 的会话补做。
