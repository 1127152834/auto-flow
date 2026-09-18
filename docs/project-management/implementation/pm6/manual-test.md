# PM6 手动测试方案：Google Sheets 来源与同步闭环

> **状态：** 2026-09-18 交付时编写
> **分支：** `codex/project-management-pm6`
> **工作区：** `/Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm6`

本方案分两栏，**不要混读**：

| 栏 | 含义 |
|---|---|
| **已由我验证** | 我在本机跑过并留下证据的条目 |
| **交给用户执行** | 需要你的 Google 账号、OAuth 客户端 JSON 和授权测试表，我无法代办 |

---

## 1. 启动说明

### 1.1 已验证的环境

```bash
cd /Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm6
npm install                       # 仅首次
uv sync --directory apps/backend --frozen
npm run build                     # 前端产物
```

启动隔离开发工作区（不要用你自己的业务工作区）：

```bash
export AUTOFLOW_WORKSPACE_DIR="$HOME/.autoflow-qa/pm6-$(date +%s)"
npm run dev
```

`AUTOFLOW_WORKSPACE_DIR` 指向一个新建空目录时，应用会把它当作新工作区初始化，**不会读取你日常的数据库**。退出后可以整目录删除。

### 1.2 前置资料

| 资料 | 谁准备 | 说明 |
|---|---|---|
| 一个空白隔离工作区 | 测试者 | 上面 `AUTOFLOW_WORKSPACE_DIR` 已覆盖 |
| Google OAuth **桌面客户端** JSON | 用户 | Google Cloud Console → 凭据 → 创建「桌面应用」OAuth 客户端 → 下载 JSON |
| 一张授权测试 Spreadsheet | 用户 | 需要包含一行表头；建议表头 `编号, 标题`，第一列是文本型 `编号` |
| 该 Spreadsheet 的分享设置 | 用户 | 授予上面客户端对应的 Google 账号**编辑**权限（只读账号无法推送） |

**凭据纪律：** OAuth 客户端 JSON、refresh token、Cookie 只会进入系统凭据库（macOS 钥匙串 / Windows 凭据管理器）。它们不会进入日志、不会进入截图、不会进入 git。测试时不要截图凭据文件或浏览器授权页的地址栏以外的内容。

---

## 2. 已由我验证（自动 + 管理侧）

这些不需要你重跑，但如果你愿意复现，命令如下。

### PM6-A01 后端契约与同步规则

```bash
uv run --directory apps/backend pytest \
  tests/unit/test_project_sheets_rules.py \
  tests/contract/test_project_sheets.py \
  tests/integration/test_project_sheets_identity.py \
  tests/integration/test_project_sheets_sync.py \
  tests/integration/test_project_sheets_recovery.py -q
```

预期：全部通过。这里的 Google REST 层是**受控替身**（`tests/fixtures/sheets.py:FakeSheetsTransport`），HTTP、SQLite、Operation 封套、事务、CAS 都是真的。

### PM6-A02 前端组件与传输

```bash
npm --workspace @autoflow/desktop exec -- vitest run src/renderer/domains/project-data
```

预期：全部通过。覆盖来源页签的账号面板、绑定向导、同步面板与 `sheets-api` 的身份/幂等行为。

### PM6-A03 桌面授权主进程

```bash
npm --workspace @autoflow/desktop exec -- vitest run src/main/google-desktop.test.ts
```

预期：全部通过。覆盖白名单、state 校验、取消、超时后回环服务关闭、日志不含令牌。

---

## 3. 交给用户执行（真实 Google 端到端）

### R1 连接真实 Google 账号

| 步骤 | 操作 | 预期 |
|---|---|---|
| R1.1 | 打开一个项目 → 数据 → 建一张表「邮箱表」，加两个字段：`编号`（文本，必填）、`邮箱`（文本） | 表出现在数据目录 |
| R1.2 | 新增一条记录：编号 `001`，邮箱 `a@example.com` | 记录列表出现 1 条；`编号` 显示 `001` 而不是 `1` |
| R1.3 | 进入「来源设置」页签 | 看到「Google Sheets」区，文案是「把这张表绑定到一张工作表」，**没有**任何假数量、假同步状态 |
| R1.4 | 点「绑定 Google Sheets…」→ 在「Google 账号」区输入账号名称（如 `运营账号`）→ 点「连接 Google 账号」 | 弹出系统文件选择框，要求选择 OAuth 客户端 JSON |
| R1.5 | 选择你下载的桌面客户端 JSON | 打开系统浏览器到 Google 授权页 |
| R1.6 | 完成授权 | 浏览器回到本地回环地址显示成功；应用内账号列表出现 `运营账号`，凭据状态「可用」、权限「可读可写」 |
| R1.7 | 在文件选择框按取消（重新点一次「连接 Google 账号」再取消） | **没有**新建连接，**没有**错误弹窗，账号列表不变 |

**反例（必须做）：**
- R1.8 选一个非 Google 的 JSON 或损坏的 JSON → 明确报错，账号列表不新增条目。
- R1.9 授权完成但**不点**确认，等 10 分钟后重试 → 报「授权结果不存在或已被使用」，需要重新授权。

### R2 绑定工作表与身份校验

| 步骤 | 操作 | 预期 |
|---|---|---|
| R2.1 | 在绑定向导里粘贴 Spreadsheet 链接（含 `#gid=`） | 工作表 gid 自动填入 |
| R2.2 | 点「读取工作表并检查」 | 显示「表头 N 列」，并列出真实列名 |
| R2.3 | 身份列下拉选 `A`（`编号` 映射到的列） | 可提交 |
| R2.4 | 把身份列改成一个**数字**字段所在的列 | 出现「身份字段必须是文本类型」问题，且「确认绑定」被禁用 |
| R2.5 | 改回文本列 → 点「确认绑定」 | 表来源变为 Google Sheets；来源事实里显示 Spreadsheet 标题与工作表名 |
| R2.6 | 回到「数据记录」页签 | 出现来自远端表头的行；`001` 与 `1` 保持不同 |
| R2.7 | 用同一张工作表去绑定**第二张**本地表并共用同一列 | 检查结果里出现重叠提示（列 X 同时被另一张表使用） |

**反例：**
- R2.8 绑定后有人在别处改了这张表的字段（例如改字段名）→ 再点「确认绑定」→ 报 412「表结构已变化，请重新检查来源」，本地数据不被改。
- R2.9 远端第一列有空值 → 身份摘要显示缺失数 > 0，绑定被阻止。

### R3 推送、拉取与公式列

| 步骤 | 操作 | 预期 |
|---|---|---|
| R3.1 | 在「数据记录」里编辑 `邮箱` 字段并保存 | 保存成功；同步状态里「待发送」变成 1 |
| R3.2 | 点「推送本地改动」 | 状态变为已确认；同步记录出现一条「推送 · 已确认 · 远端一致」；打开 Spreadsheet 看到远端单元格已更新 |
| R3.3 | 在 Spreadsheet 里手工改 `邮箱`，点「拉取来源（含公式）」 | 本地记录被刷新 |
| R3.4 | 本地编辑 `邮箱` 但**不要**推送；在 Spreadsheet 里同时改同一个单元格；再点推送 | 同步记录显示冲突，远端不被覆盖，本地值保留 |
| R3.5 | 把某一列在绑定时声明为公式列（重新绑定并把该列方向设为「只读来源」且勾公式），在 Spreadsheet 改公式 | 点拉取后**只有公式列**刷新，同行的普通值保持原样 |
| R3.6 | 点「暂停调度」 | 按钮变为「恢复调度」；暂停期间的本地修改保留为待发送 |
| R3.7 | 点「恢复调度」→ 推送 | 待发送条目被发送并确认 |

**异常复现（不需要你改数据库）：**
- R3.8 **结果未知**：断开网络（关闭 Wi‑Fi）后点推送 → 操作进入「结果未知」；恢复网络后点「核对结果」→ 得到确定结论；**系统不会自动重发**。检查 Spreadsheet 确认没有重复写入。
- R3.9 **提交后响应丢失**：在推送过程中强制退出应用（或杀掉后端进程）→ 重启应用 → 回到来源设置，同步记录仍在，状态可查询。
- R3.10 **服务重连**：在应用内重启服务（设置 → 重启本地服务）→ 刷新页面 → 同步记录与绑定不丢失。
- R3.11 **双工作区隔离**：用另一个 `AUTOFLOW_WORKSPACE_DIR` 启动第二个实例 → 看不到第一个工作区的项目与连接。
- R3.12 **旧引用不串代次**：重新导入/改绑后，旧数据代次的记录查询不到新代次的记录；旧状态的记录标记保留在原代次。

---

## 4. 结果记录

| 用例 | 结果（通过/失败/未执行） | 截图编号 | 备注 |
|---|---|---|---|
| R1.1–R1.7 | | | |
| R1.8–R1.9 | | | |
| R2.1–R2.9 | | | |
| R3.1–R3.7 | | | |
| R3.8–R3.12 | | | |

问题反馈格式：

```
用例编号：
期望：
实际：
复现步骤：
截图：
应用版本（设置 → 关于）：
```

**未执行项必须标「未执行」。** 本机为 macOS；Windows、其他架构与打包版本的验收未执行。

---

## 5. 清理

```bash
# 只删除本方案第 1.1 节创建的隔离工作区
rm -rf "$HOME/.autoflow-qa/pm6-<你启动时的时间戳>"
```

清理前请确认目录名里带 `pm6-` 前缀。**不要**删除 `~/Library/Application Support/autoflow` 或你自己的业务工作区。Google 连接如需移除，目前界面按钮为「解除连接尚未交付」——请在 Google Cloud Console 里撤销该 OAuth 客户端的授权，并在系统凭据库里删除 `autoflow` 相关条目。

---

## 6. 本阶段明确未交付

- 解除 Google 连接 / 解除表绑定（需要共享影响预览支持 `disconnectSheets`，接口目前显式返回 501）
- 系统身份来源初始化（`identityStrategy.kind === 'system'` 显式返回 501）
- Sheets 同步：真实网络上的持续调度（当前为显式推送/拉取）
- 暂停期间漏登记的写入补登策略
