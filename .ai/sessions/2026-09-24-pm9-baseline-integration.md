# PM9 合入 baseline

日期：2026-09-24。状态：confirmed。来源：用户本轮明确要求“代码合并到 baseline 分支”、git fetch/祖先关系/tree 核对、GitHub Actions 最新状态。

用户授权本次合并，覆盖此前仅限 PM9 分支且不合并的限制；不授权发布，也不将 PM9 验收改为完成。

- 源分支：codex/project-management-pm9-runtime@90d77acdd64d20b133aff6ace9eb445fa20e06c6。
- 目标：codex/architecture-baseline，原8e5564e0f5624afd429171de53b5b1039199513a。
- 远端目标无分叉，快进183提交；结果tree与源一致，ed2cb230665f95ecebafb2d27489959e49140fd6。另追加本次记录及CI状态订正，不修改生产代码。
- 在独立pm9-baseline-merge工作区执行；主目录Studio工作、其他分支、PM9原分支与验收产物保留。
- 合并后4项覆盖检查及251引用核对通过；没有冲突解决产生的新实现，不重复既有全量测试。
- 最新Actions35935288512已由in_progress变为failure：Windows/ARM真实worker验收步骤失败，Intel安装包构建步骤失败。日志接口403，不能推断根因。完整本机通过及其他历史证据保留，不拿它抵扣此次原生失败。
- releaseAccepted=false；实网Google/OAuth、签名/公证、Windows/Intel实机及其他已登记缺口仍待完成。
