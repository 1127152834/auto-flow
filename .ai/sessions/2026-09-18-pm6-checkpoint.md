# PM6 会话检查点：Google Sheets 来源与同步闭环（管理侧交付）

- 日期：2026-09-18
- 工作区：`/Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm6`
- 分支：`codex/project-management-pm6`
- 状态：confirmed（管理侧与本地契约已交付并验证；实网 Google 端到端未执行）

## 交付了什么

真实管理界面可以连接 Google 账号、把一张表绑定到某张工作表（含结构检查、身份与映射核验、重叠报告），
之后按需拉取与推送、刷新只读公式列、暂停与恢复调度、核对未知结果、解除绑定并保留本地副本。
出站意图与同步操作在 SQLite 中持久化，超时进入 `unknown` 后只允许核验，不盲重发。

## 证据

- 机器报告：`docs/project-management/implementation/pm6/verification.json`
- 真实界面：`docs/project-management/implementation/pm6/qa-runs/2026-09-18/`（13 检查点 / 12 张 1440×1024 截图，status=passed）
- 手测方案：`docs/project-management/implementation/pm6/manual-test.md`
- 执行卡：`docs/superpowers/plans/2026-09-16-project-management-pm6.md`

## 关键判断与教训

1. **端到端比定向测试更早抓到真实缺陷。** 四类问题在单元与组件测试全绿时仍然存在：绑定命令用了 POST
   而路由只接受 PUT（真实界面绑定必然 405）、拉取/推送后记录页不重取、来源页把读取失败显示成空事实、
   连接面板列错位。前两项是用户完全无法完成主流程的缺陷。
2. **交接文档里的「704 项基线失败」是环境假象。** 在 `5f07e2ad` 建独立 worktree 实测：缺 `reference/`
   参考检出时 705 failed；补上只读符号链接后 `tests/differential + tests/migration` 956 passed、
   侧车与崩溃回归 39 passed。把环境缺失当成业务回归会掩盖真实失败，反之也会误判工作范围。
3. **计划与契约在「远端增列」上不一致。** PM6-C 要求受控远端增列，但冻结的 HTTP 契约与 OperationKind
   列表都没有对应路由或 kind。按「缺任一项不得加入枚举」的规则，未擅自新增接口，登记为缺口。
4. **系统身份列必须等批准的初始化动作。** `identityStrategy.kind == 'system'` 当前返回 501
   `SYNC_NOT_IMPLEMENTED`，这是明确拒绝，不是静默降级。

## 未执行 / 缺口

- 实网 Google OAuth 与真实 Spreadsheet 读写：需要用户提供 OAuth 桌面客户端 JSON（或服务账号 JSON）与明确授权的测试 Spreadsheet。
- 远端受控增列：等契约决定。
- 系统身份列：等批准的初始化动作。
- 同一远端键在工作表内重复：当前 `setdefault` 取首行，重复键显式报错未做。
- 暂停期间本地写入不补登记出站意图：恢复策略待 PM6-C 明确。
- 真实 Studio、Windows、其他架构、打包应用、用户手测：未执行。

## 测试环境说明（不进提交）

本机为跑通依赖参考检出的测试，在 `reference/` 下创建了指向主项目参考检出的只读符号链接
（`WebRPA`、`RedroidManager`、`redroid-script`、`vphone-aio`、`vphone-cli`）。这些链接被 `.gitignore`
覆盖，未纳入任何提交，也不属于业务改动。
