# PM9 生命周期重启与运行目录清理

- 日期：2026-09-23；状态：confirmed（局部），完整回归/新候选三平台待完成。
- 来源：test_project_sheets_real_cloakbrowser.py::test_real_archive_waits_for_run_save_and_unknown_sheet_outcome 红绿验证；lifecycle-restart-follow-through.json。
- 根因：生命周期删除只枚举环境目录，数据库清理掉任务/产物后，workspace/runs/{runId} 仍残留。统一仓库注入现有 runs 根目录，按 ProjectTaskRow.project_id 收集并复用既有删除/残留/重启重试。
- 联合场景：两次完整服务重建，恢复不重放；定点 PermissionError 保持至 shutdown，下一服务沿原删除幂等键完成；受控远端内容与 Profile/另一项目/外部及无归属文件保留。项目删除结果从 workspace 作用域查询，不从已删除项目路由查询。
- 限制：Google/凭据/权限故障和受管目录内证据文件为 fixture；不等同操作系统原生权限故障或实网、打包 UI、Workspace 切换与用户验收。248/251有范围断言，0 verified，releaseAccepted=false。

- 最终测试移除重建后的手动 advance，只等待 startup coordinator 自行完成（1 passed/15.15秒）；相关21项、Ruff/mypy407、OpenAPI、PyInstaller、原15秒 sidecar smoke通过。独立审查无P1/P2；完整回归仍进行中。

- 后续完整回归：生命周期源码94f8e0a8，3472 passed/74 skipped/2 warnings（796.74秒）。其后Windows O_BINARY一行修复另有16项与真实worker1项证据；最终原生矩阵35816693045@defa1955进行中。
