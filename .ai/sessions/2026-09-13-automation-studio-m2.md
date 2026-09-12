# Automation Studio M2 实施

- 日期：2026-09-13
- 状态：confirmed；实现与macOS最终验收完成，完整结果见验收记录。
- 工作仓库：`/Users/zhangtiancheng/Documents/projects/autoflow`，分支 `codex/architecture-baseline`。
- 基准：M1 `b2e95b3` 已在当前历史中；参考只读 WebRPA `5ccb900e8dcf1530aae66f676d87593c416c7ebb`。

## 本次工作

- 保持 workflows 领域，增加真实运行契约、0006增量迁移、运行服务、worker、六节点、文件产物和连续持久化事件。
- 接入正式 Studio，使用既有 Profile；不自动保存草稿，运行期间编辑继续，日志与标记按启动快照隔离。
- 原离开协调先保存、后停止清理，再关闭/退出/切区；普通恢复只重连。已知无活跃运行时保留 M1 离线编辑/放弃行为。
- 独立复审修复：数据库失败阻止停止/终态落库责任丢失、隐藏截图 selector 误校验、失败节点显示运行中、旧异步响应清除新运行。
- 真实异常进程测试发现 Chromium 独立 session，需要超出 worker 单个进程组的清理；进一步验证归属、PID复用与重复取消，避免误处理无关进程或中断自己的清理。

## 验证与产物

正式说明：`docs/migration/automation-studio-m2-validation.md`。机器结果位于 `docs/migration/automation-studio-m2-qa/`。

真实脚本使用克隆内核和独立临时工作区，不改用户数据库、配置或登录态。API源码/冻结入口覆盖六节点与八组检查；Electron构建/开发/打包覆盖真实配置、运行、结果和离开保护；M1原脚本覆盖完整13检查。补充worker脚本记录真实PID清理与异常退出。最终通过数量、代码质量门禁和平台限制只维护在验收记录中。

Windows 尚未实机验收；付费内核、真实代理服务、扩展和动态GeoIP组合不作本轮已实测声明。没有实施控制流、Debug、录制、元素拾取、发布或企业管理。

## 工作树边界

本轮开始前已有模型管理、UI研究、redroid等未提交文件及旧automation原型；不将这些内容纳入M2提交，不覆盖`.ai/memory/project-context.md`的既有修改。新增稳定决策在`decisions/2026-09-13-workflows-m2.md`，正式路径索引同步`docs/PROJECT_STRUCTURE.md`。
