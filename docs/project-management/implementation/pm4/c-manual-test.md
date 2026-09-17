# PM4-C 有限/不限调度管理链手动验收

日期：2026-09-16。适用分支：`codex/project-management-pm4`。
当前用户手动验收状态：**未执行**。

本手册使用隔离假执行器验证真实管理界面、FastAPI、SQLite、数据领取和项目数据写入。它不会启动 CloakBrowser，不调用 Studio，也不能证明生产工作流执行核心可用。

## 1. 启动方式

先构建，再运行自动 C 场景：

```bash
cd /Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm4
npm run build
node scripts/qa-project-management-pm4.mjs --c
```

需要在自动链通过后保留应用供人工查看时运行：

```bash
cd /Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm4
node scripts/qa-project-management-pm4.mjs --c --manual
```

脚本会在系统临时目录创建唯一的 `autoflow-pm4-v1-qa-*` 所有者目录和隔离工作区，启动真实 Electron、FastAPI 和 SQLite，并在仓库的 `docs/project-management/implementation/pm4/qa-runs/c-*` 保存本轮结果与截图。`--prepare-only` 不执行业务链，不能记为端到端通过。

## 2. 自动建立的测试资料

| 对象 | 测试资料 |
|---|---|
| 项目 | `PM4 三表链验收` |
| 人员表 | 1 条人员记录，字段“姓名” |
| 邮箱表 | 5 条不同邮箱，字段“邮箱地址”；初始业务状态为空；另建“待使用”“已使用”两个状态 |
| 账号表 | 启动前为空，包含人员、邮箱、网页结果字段 |
| 自动化 | `三表资料处理` |
| 输入 | 人员输入、邮箱输入，均为独立且必填；邮箱输入筛选业务状态为空 |
| 有限批次 | 3 个任务，并发 1 |
| 不限批次 | 不限次数，并发 1；QA 屏障在本轮累计 5 个假任务后暂停继续领取，供 UI 主动停止 |

项目、表、字段、记录和自动化均由脚本操作真实 Electron 界面建立。脚本只用只读接口核对最终事实；不会用 API 创建这些业务对象。

## 3. 人工检查步骤

| 编号 | 操作 | 逐步预期 | 用户结果 |
|---|---|---|---|
| PM4-C-U01 | 使用 `--c --manual` 启动；等待终端打印 passed 和证据路径 | 应用保持打开；顶部导航存在；当前是已停止的不限批次详情 | 未执行 |
| PM4-C-U02 | 在批次详情核对摘要和任务列表 | 批次状态为“已停止”；停止原因与脚本填写内容一致；任务数恰好 2，两个任务均成功 | 未执行 |
| PM4-C-U03 | 依次打开两个任务的“输入与输出” | 每个任务有同一个人员 RecordRef、不同邮箱 RecordRef；数据写入同时包含邮箱状态变更和账号新增 | 未执行 |
| PM4-C-U04 | 返回“运行记录”，打开已完成的有限批次 | 批次为 completed，结束原因是达到请求任务数；任务列表恰好 3 条且全部成功 | 未执行 |
| PM4-C-U05 | 打开有限批次任一任务的“输入与输出” | 原始输入显示人员和邮箱两项；输入快照不随表的后续状态改变；写入结果不重复、不丢失 | 未执行 |
| PM4-C-U06 | 打开“数据”并检查人员、邮箱、账号三张表 | 人员仍只有 1 条且状态未改变；5 个邮箱均为“已使用”；账号恰好 5 条且没有重复记录 | 未执行 |
| PM4-C-U07 | 刷新任务页、批次页并在页签间往返 | 持久输入和写入事实仍存在；任务数、终态和结束原因保持一致 | 未执行 |
| PM4-C-U08 | 对照本轮 `result.json`、`c-facts.json` 和 10 张截图 | `status=passed`；边界为 fake/notExecuted/notExecuted；视口 1440×1024，无应用级横向撑宽 | 未执行 |

## 4. 业务事实核对

打开本轮证据目录中的 `c-facts.json`，逐项核对：

1. `finiteTaskIds` 恰好 3 个，`finiteEndReason.status` 为 `limitReached`。
2. `unlimitedTaskIds` 恰好 2 个，`unlimitedStatus` 为 `stopped`。
3. 5 次任务的人员引用都等于 `reusablePersonRef`。
4. `emailRefs` 有 5 个互不相同的带类型记录身份。
5. `usedEmailCount` 为 5，`accountCount` 为 5。
6. `executionBoundary` 明确记录 `executor=fake`、`browser=notExecuted`、`studio=notExecuted`。

这些只读事实核对用于验证 UI 操作后的数据库结果，不替代用户界面步骤。

## 5. 异常与边界

本轮 C 脚本稳定覆盖有限批次达到目标和不限批次 UI 主动停止。暂时占用、真实耗尽、失败策略、旧执行代次与重启恢复尚未通过专用 C 用户界面故障控制执行，不能填写为本手册通过。

相关自动回归可执行：

```bash
cd /Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm4
uv run --directory apps/backend pytest \
  tests/integration/test_project_data_scheduler.py \
  tests/integration/test_pm4_qa_runner.py \
  -q
```

命令通过属于真实服务与临时 SQLite 的自动集成证据，不属于 Electron 用户手测证据。失败时保留完整测试名和输出，不得删除断言或把失败写成未执行。

## 6. 视觉与交互

| 编号 | 操作 | 预期 | 用户结果 |
|---|---|---|---|
| PM4-C-V01 | 以 1440×1024、100% 缩放检查表目录、输入配置、启动预检、批次和任务页 | 顶部导航；统一细网格表格；小圆角；动作位置与原型主体一致 | 未执行 |
| PM4-C-V02 | 调到 200% 缩放检查启动弹窗、停止确认和任务输入输出 | 内容在弹窗或表格内部滚动；应用宽度不被撑开；关键操作仍可见 | 未执行 |
| PM4-C-V03 | 使用 Tab、Shift+Tab、Enter、Escape 操作启动和停止确认 | 焦点顺序明确；Escape 关闭当前浮层并恢复焦点；提交期间不重复触发 | 未执行 |

## 7. 结果记录与清理

每项按以下格式记录：

```text
用例编号｜通过/失败/未执行｜实际操作｜实际业务事实｜证据类型｜截图/result.json 绝对路径｜与预期差异
```

退出 `--manual` 时在终端按 `Ctrl+C`，等待 Electron 和 sidecar 结束。只清理终端输出中本轮 `owner` 指向、且包含 `.pm4-v1-qa.json` 标记的临时目录。不要删除用户工作区、主项目、PM3 工作区或仓库内 `qa-runs/c-*` 证据。

Windows、其他 CPU 架构、打包应用、真实浏览器执行、真实工作流核心接入、Studio 联合运行及本表用户手测均保持“未执行”。
