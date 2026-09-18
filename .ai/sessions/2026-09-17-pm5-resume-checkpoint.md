# PM5 接续检查点 · 2026-09-17 04:06 +08

状态：confirmed（仅本节列出的验证）；PM5 未完成、未提交。来源：当前源码、真实 CloakBrowser 测试、真实 Electron QA 与直接 HTTP 负向查询。唯一工作区 `autoflow-project-management-pm5`，HEAD `fbda6f17`，原任务未提交成果保留。

## 已验证

- 真实登录保存 / 新目录恢复测试通过：官方 persistent API 不支持重复的 executable_path；测试通过 CLOAKBROWSER_BINARY_PATH 选已安装内核。原 fixture 向 Cookies 写占位字节，已替换为空实例，原登录结果断言保留。
- 参数启动与数据领取在同一数据库 Session 预约实例 / 环境占用；预约失败的反例证明 Task/Run/输入/记录占用不残留，参数成功及同键重发已回归。
- 最终限定回归：58 passed；限定 Ruff / diff 检查通过；桌面 build 成功。不是 PM5 退出验收。
- 隔离 Electron 已重新启动，9333；UI 创建真实 profile `2c1fa094-63d8-4bb4-a895-82d48682d6b9`。旧环境引用占位 profile `33333333-3333-3333-3333-333333333333`，因此自动化仍正确被阻断。
- `qa-runs/resume-start-rejection.json`：直接 HTTP 启动返回 422，批次前后 0。截图 `qa-runs/resume-profile-blocked.png` 是当前 UI 阻断，不是 UI 首链成功。

## 接下来

1. 真正接通 instance opener / closer 与 Run 工作副本路径；不能只改变 DB state 当已启动浏览器。文件准备失败需持久查询恢复，旧执行代次不能取得控制权。
2. 完成 End 保存前停止与关闭一致性、幂等/关联保护。当前代码不足以宣称所有保护已完成。
3. 复用真实 profile，通过 UI 调整测试自动化并跑登录保存→账号关联→后续任务恢复；旧占位环境不可算真实登录资料。
4. 最新 mypy 仍有 17 个错误（5 文件），完整工程/视觉验收、独立审查、Windows/打包/用户手测未完成。

早期两个子代理分别遇额度与模型不可用；后续只读审查已返回（覆盖先前未返回的临时状态）。确认阻断：关联 CAS、权威保存代次、真实 close/save 生命周期、opener 和 End 阶段恢复。CAS 现已用两记录并发反例修正并证明全组回滚；其余未闭合。没有修改主工作区或 Studio，没有提交。

Run 工作目录随后通过 bootstrap 注入的进程内解析器接到 acquire；真实 SQLite Run/Task/instance 验证目录传递与停止后拒绝，但不表示生产 worker/完整 UI 链已验收。不要重复新增 userDataDir 到不可变 Run 请求；当前解析通过 run_request_id→Run→Task/instance 取受控现有目录。完整恢复/旧执行代次仍需结合 End 检查。

详细原卡：`docs/superpowers/plans/2026-09-17-project-management-pm5.md` 第 8 节。不要根据旧卡勾选重新实现；也不要把旧管理合同测试通过解释为浏览器生命周期已接通。

最终定向回归：77 passed / 2 warnings。真实浏览器登录→直接 HTTP End 探针失败：End 抛 Error，浏览器未被关闭，恢复未执行。证据 `docs/project-management/implementation/pm5/qa-runs/resume-real-end-probe.json`。下一步只沿真实关闭→保存→关联→恢复修首链，不再通过补充单测或直接改 DB 状态代替实际关闭。探针没有完整异常栈，仅记录异常类型，需要补捕获到受控日志后定位。QA Electron 使用本轮中段代码启动，后续后端改动需要重启后再验。
