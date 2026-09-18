# PM5 手动验收方案：登录环境持续使用与人工介入

日期：2026-09-18（Asia/Shanghai）
状态：**自动证据已产生；用户手动用例尚未执行**。本文中"我已验证"与"待用户执行"严格分开，未执行项一律不写成通过。

---

## 0. 交付版本与边界

| 项 | 值 |
|---|---|
| 工作区 | `/Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm5` |
| 分支 | `codex/project-management-pm5` |
| 基线提交 | `fbda6f17`（PM4 管理交付）；本轮改动尚未提交 |
| 验收范围 | PM5-A 保存身份/来源/工作副本、PM5-B End 完整保留与维护、PM5-C 人工/额度/竞争 |
| 迁移 | `pm07_environments.py`（`down_revision=pm06_project_capability_reads`） |

**证据分两栏，请勿混读：**

1. **管理侧及实际浏览器环境存取已验证**：Electron 渲染层真实点击、应用自启 FastAPI、SQLite、环境目录副本、CloakBrowser 真实进程启动/关闭、保存/恢复登录态。
2. **真实执行核心接入待验收**：生产工作流执行核心跑完整节点链（含任务内真实浏览器执行、检查点恢复与 End 编排）。本阶段用隔离测试执行器把任务保持在排队态，避免人工接管与真实执行器抢同一个浏览器 profile。

**本机未执行、不计入通过：** Windows、其他架构（x64/Windows 打包）、打包应用验收、用户手测结果。

---

## 1. 启动说明

### 1.1 一键隔离启动（推荐，本方案所有界面用例都用它）

```bash
cd /Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm5
npm run build                       # 必须先构建，脚本运行的是构建产物
node scripts/qa-project-management-pm5.mjs --manual
```

`--manual` 行为：

- 新建隔离工作区（临时目录 `autoflow-pm5-ui-qa-*`，内含 `.pm5-qa.json` 标记、`workspace/` 数据目录、`.autoflow-workspace.json`）。
- 启动真实 Electron + 应用自启 FastAPI 侧车 + SQLite，逐步建项目/配置/自动化并截图，最后**保持应用打开**，把隔离工作区路径与调试端口打印到终端。
- 终端最后一行形如：`手动模式：应用保持运行，隔离工作区 /var/folders/.../workspace，调试端口 <port>`。**记下这两个值**，后面所有界面用例在这个窗口继续做。

关键约束：

- 不要用主应用的用户数据目录做这些用例；本方案的写入只应发生在上面打印出的隔离工作区。
- 调试端口由脚本随机分配；若你需要人工连 CDP，用打印出来的端口。**不要占用 9222**（那是你自己的 Chrome）。
- 脚本只在带 `.pm5-qa.json` 标记的目录里操作，不会碰你的真实项目数据。

### 1.2 单独复现"真实浏览器登录保存/恢复"（不依赖界面）

```bash
cd /Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm5
python3 scripts/qa-pm5-browser-chain.py \
  --workspace /tmp/pm5-manual-browser \
  --out /tmp/pm5-manual-browser-out \
  --keep-browser          # 想看完浏览器再退出时加上
```

它用生产 `create_app` 装配 + 真实 CloakBrowser 跑：启动 → 登录本地测试站 → End 保留并关联 → 真实关闭原浏览器 → 从保存环境恢复新实例并确认仍是已登录 → 写入新标记 → 再次保存（内容代次 +1）→ 第三次读取新内容。结果 JSON 写到 `--out`。

测试站账号：`demo` / `pass`（本地 `tests/fixtures/login_site.py`，不联网）。

---

## 2. 前置准备

1. 已安装浏览器内核 `chromium-145.0.7632.109.2`：
   `~/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2/Chromium.app/Contents/MacOS/Chromium`
   路径不存在时先在内核管理里安装该版本，否则"进入当前浏览器"和 End 保存都会失败（这是预期阻断，不是缺陷）。
2. 用例资料（**必须由界面创建**，不要用 API 预置，否则不算界面验收）：
   - 一个项目，例如 `PM5 手测项目`
   - 一张表 `账号`，字段 `账号名称`（文本，必填），记录 `主账号`
   - 一个浏览器配置 `PM5 手测配置`（选用上面那个已安装内核）
   - 一个自动化 `PM5 登录环境演示`，环境来源 = **指定浏览器配置** → `PM5 手测配置`
3. 允许作为"明确标注的测试资料准备"：工作流文档、规模数据、竞争修改注入。界面用例只依赖 1–2 里由你亲手建的东西。

---

## 3. 逐步操作与逐步预期

### 第一部分：管理界面基础（我已在本机自动执行，需要你复核）

| 编号 | 操作 | 预期 | 自动证据 |
|---|---|---|---|
| PM5-M00 | 启动后进 `项目` → `新建项目` → 输入 `PM5 手测项目` → `创建项目` | 进入项目页；重启应用后从"全部项目"仍能打开它 | `qa-runs/2026-09-18/01-environment-workspace.png` |
| PM5-M01 | 项目页点 `环境` 页签 | 四个分区都在：`保存环境`、`运行环境`、`待人工处理`、`默认资源`；空态说明清楚，没有假的实例数 | `01-environment-workspace.png`、`12-project-defaults.png`、`13-manual-items.png` |
| PM5-M02 | `浏览器配置` → `新建配置` → 填写名称 → `内核与代理` 选到 `145.0.7632.109.2` → `创建配置` | 配置出现在列表；回到项目环境页仍正常渲染，不白屏、不撑宽 | `02-profile-kernel-selected.png`、`02-profile-created.png`、`03-environment-after-profile.png` |
| PM5-M03 | `自动化` → `新建自动化` → 填名称与用途 → `关联工作流` 选测试工作流 → `资源与环境` → `浏览器配置来源` = `指定浏览器配置` → `浏览器配置` = `PM5 手测配置` → `保存配置` | 保存成功；再次打开该自动化时环境来源回显为"指定浏览器配置" | `04-automation-environment-policy.png` |

### 第二部分：启动任务与"进入当前浏览器"

| 编号 | 操作 | 预期 | 自动证据 |
|---|---|---|---|
| PM5-M04 | 自动化详情 → `启动运行` → 启动对话框出现，选任务数 `1 个任务` → 确认 | 启动对话框展示真实额度与来源；确认后提示批次已创建，能在运行页看到任务 | `05-start-dialog.png` |
| PM5-M05 | 项目页 → `环境` → `运行环境` 页签 | 列出该任务预约的真实实例：来源、状态、关联任务可见；历史已结束实例**不**出现在活动列表 | `06-running-environment.png` |
| PM5-M06 | 点该实例行的 `进入当前浏览器` | 真实弹出 CloakBrowser 窗口；实例状态变为活动/已打开；按钮在打开期间不可重复点（或明确给出已打开提示） | `07-enter-current-browser.png` |
| PM5-M07 | 在打开的浏览器里访问项目使用的测试站并登录（或在任务页进入登录步骤后再点该按钮） | 浏览器可正常交互；关闭浏览器窗口后，实例不应永久停在"打开中"，应能再次进入 | `07`、`08-task-end-panel.png` |

**注意（须如实记录）：** 本机自动链使用隔离测试执行器，任务保持 `queued`，因此"任务自己跑起来并走到浏览器节点"这一段在界面里不会自动推进。`05`–`08` 验证的是启动事实、实例预约、真实内核启动与 End 面板，而不是生产执行核心跑完全程。

### 第三部分：End 保留、关联与恢复（PM5 核心）

| 编号 | 操作 | 预期 | 自动证据 |
|---|---|---|---|
| PM5-M08 | 任务页 → 日志/结束面板 → 勾选保留环境 → 选择关联到 `账号 / 主账号` → `结束并保留` | 保存成功后：项目 `保存环境` 页签出现一条真实保存环境；`运行环境` 里对应实例收口为已结束；**被占用的内核进程真实退出**（用活动监视器确认没有该实例目录的 Chromium） | `08-task-end-panel.png`、`09-environment-saved.png`、`10-saved-environment-list.png` |
| PM5-M09 | `保存环境` → 点 `查看环境` | 详情展示来源、内容代次、关联记录、维护入口；不显示内部修订号为标题 | `11-saved-environment-detail.png` |
| PM5-M10 | 关闭应用 → 重新用同一隔离工作区启动 → 打开该项目 → `保存环境` → `查看环境` | 保存环境仍在（持久化），关联记录仍在，状态与关闭前一致 | 见下方"需用户执行" |
| PM5-M11 | 用保存环境再启动一个任务（自动化环境来源改为该保存环境，或把实例固定到该环境） → 再点 `进入当前浏览器` | 打开的浏览器仍带着上次的登录态（本地测试站仍显示已登录） | `qa-runs/2026-09-18/browser-chain.json`（HTTP + 真实浏览器层已通过） |
| PM5-M12 | 在恢复出来的浏览器里修改内容 → 再次 End 保留 | 再次保存生成新的内容代次；第三次恢复读到的是新内容 | `browser-chain.json` 的 `contentGeneration` 递增记录 |

### 第四部分：运行记录的人工链（本轮新增，原型 03-runs/002/003/008/019/020）

前提：这一组需要一个**真实处于等待人工**的任务。隔离测试执行器不会自行到达该检查点，可用交付里的 QA 脚本自动跑完（`node scripts/qa-project-management-pm5.mjs`，脚本内注入的现场在截图后会被删除并还原运行状态）；若要手动复现，请在注入后按下面步骤操作，并在记录里写明「注入资料」。

| 编号 | 操作 | 预期 | 自动证据 |
|---|---|---|---|
| PM5-M15 | 项目 → `运行记录` → `等待人工` 页签 | 四列出现：等待原因 / 所属任务 / 剩余保留时间 / 操作；搜索只在提交后生效；状态与排序下拉可用且不撑宽 | `20-manual-list-tab.png` |
| PM5-M16 | 点某一行的 `查看事项` | 进入**唯一一份**人工详情：返回等待人工、面包屑、剩余保留时间、左侧「当前现场」、右侧「处理方式」三选项 + 提交处理结果 | `21-manual-detail.png` |
| PM5-M17 | 在详情里选 `标记完成` → 点 `提交处理结果` | 弹出确认弹窗；**未勾选「我已了解，本次处理不会继续工作流」时 `确认标记完成` 必须禁用**；勾选后才可提交，提交结果写回原任务、不创建新任务 | `22-manual-complete-confirm.png` |
| PM5-M18 | 取消弹窗 → 选 `标记失败` | 出现必填的「失败说明」；未填写时 `提交处理结果` 禁用；填写后可提交 | `23-manual-failure-required.png` |
| PM5-M19 | 回到 `任务记录` 页签，找状态为「等待人工」的任务行 | 列结构为 任务/自动化 · 所属批次 · 输入标识 · 任务状态 · 当前或结束节点 · 时间（最近状态时间）· 操作；该行操作为 `查看事项`，其它任务行仍是 `查看任务` | `24-task-list-manual-entry.png` |
| PM5-M20 | 把人工事项的保留时间调到已过期（或等它自然过期）后再进入该事项 | 页面变成「处理结果」+「历史现场」：写明保留时间已到、不能再提交人工处理、**不根据倒计时推断清理结果**；**没有** `提交处理结果`，也**没有** `打开环境`；提供 `查看任务日志` 与 `刷新状态` | `25-manual-expired-list.png`、`26-manual-expired-result.png` |
| PM5-M21 | 人工详情里点 `返回等待人工`，再点浏览器返回键 | 返回列表并恢复原来的搜索、状态筛选、排序与滚动位置 | 需你执行 |


### 第五部分：额度与阻断

| 编号 | 操作 | 预期 |
|---|---|---|
| PM5-M13 | 连续打开多个实时实例直到达到现场额度上限（默认 32，手测可先把上限调低或用多个任务逼近） | 超过上限时启动/打开被明确拒绝并说明"现场额度已满"，不是静默失败或假成功 |
| PM5-M14 | 在归档项目（只读）里尝试 End 保留 / 新建配置 | 被拒绝并保持只读，不产生半成品 |

---

## 4. 异常复现工具

这些是**测试注入**，不是产品功能；复现时必须在报告里标注为注入。

| 场景 | 复现方式 | 期望行为 |
|---|---|---|
| 内核缺失 | 把配置指向一个未安装的内核版本再启动/打开 | 明确报"内核未安装"，不创建假的实例，不留下 `running` 操作 |
| 浏览器启动失败 | `mv` 掉内核可执行文件后点 `进入当前浏览器`；随后恢复文件 | 操作收口为 `failed`（含 `INSTANCE_OPEN_FAILED`），**不能永久停在 `running`**——这是本轮修掉的真实缺陷，回归断言见 `tests/contract/test_project_environments.py::test_open_records_an_unexpected_launch_failure_instead_of_leaving_it_running` |
| 保存时执行代次过期 | 保存前让运行代次推进（例如重连/恢复事件先发生），再点 End | 返回 `EXECUTION_GENERATION_REVOKED`(410)，**保留旧数据**，提示重新确认；不得写半份关联 |
| 关联冲突 | 两条记录同时关联同一环境（第二条并发关联） | 整组回滚，不做部分关联；重试后可成功 |
| 服务重启 | 保存前 kill 侧车进程（`ps` 找该隔离工作区的 python 侧车） | 应用重连；操作结果通过原操作身份查询，不盲目重发、不重复保存 |
| 响应丢失 | 提交后立刻断开/重启（或在保存请求进行中关闭渲染层） | 重新查询原操作得到唯一结果；不得出现第二个保存环境或第二次关联 |
| 重复提交 | 连续快速点两次 End | 只产生一份保存事实 |

排查入口：`<隔离工作区上级目录>/desktop.log`、`<隔离工作区>/logs/sidecar.log`、SQLite 的 `project_operations` / `project_end_operations`。QA 报告里已内嵌 `facts.desktopLogTail` 与 `facts.sidecarLogTail`。

---

## 5. 结果记录

每条用例记录：`编号 | 通过/失败/未执行 | 实际现象 | 截图路径 | 运行版本(HEAD) | 证据类型(界面/HTTP注入/自动)`。

建议结果表：

| 编号 | 结果 | 实际现象 | 截图 | 备注 |
|---|---|---|---|---|
| PM5-M00 | 未执行 | | | |
| PM5-M01 | 未执行 | | | |
| … | | | | |

**我已验证（自动证据）**

- `node scripts/qa-project-management-pm5.mjs` 连续两次 `passed`，10 个检查点全过：`docs/project-management/implementation/pm5/qa-runs/2026-09-18/ui-result.json` + 13 张 1440×1024 截图。
- 真实浏览器登录/保存/恢复/内容代次：`docs/project-management/implementation/pm5/qa-runs/2026-09-18/browser-chain.json`。
- 后端定向与全量测试、Ruff、mypy、前端检查结果见 `docs/project-management/implementation/pm5/verification.json`。

**待用户执行**：PM5-M00 至 PM5-M14 中标注"未执行"的全部界面用例，尤其 M08/M10/M11/M12 的"关应用再恢复"与"第二次保存后第三次读取"。

---

## 6. 清理方法

只清理带标记的测试数据，**不要**动真实工作区：

```bash
# 1) 确认目录带 PM5 QA 标记（必须输出 kind 为 pm5-project-management-qa）
cat /var/folders/*/*/*/autoflow-pm5-ui-qa-*/.pm5-qa.json

# 2) 只删除打印过标记的目录
rm -rf /var/folders/<...>/autoflow-pm5-ui-qa-<id>

# 3) 真实浏览器链路的临时目录
rm -rf /tmp/pm5-manual-browser /tmp/pm5-manual-browser-out
```

删除前先确认没有该目录下的 Chromium 进程仍在运行（`ps aux | grep autoflow-pm5-ui-qa`）；有则先优雅关闭应用。

保留：`docs/project-management/implementation/pm5/qa-runs/` 下的截图与 JSON 报告（属于验收证据，不要删）。
