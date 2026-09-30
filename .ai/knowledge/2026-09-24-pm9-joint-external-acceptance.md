# PM9 联合场景与外部验收

日期：2026-09-24。状态：confirmed（下述本机子范围）。来源：新增真实worker断言、公开HTTP契约、原始日志及当前DMG安装检查；详见docs/project-management/implementation/pm9/joint-external-acceptance.json。

2026-09-24 联合场景及外部验收推进（confirmed，本机子范围）：DATA-E2E-05复用真实worker和生产ASGI HTTP/SQLite，新增pending/unknown两例，串联归档、后端重启、恢复、显式放弃/核验、换源；旧Task/意图不重投，同键新代次不继承旧状态或环境关联，原快照/操作可解释。5项联合/归档检查和52项同步恢复回归、104脚本、Ruff、4映射/251引用通过。首轮1失败为abandon返回200而测试写202，修正测试后通过，无生产修复。仅DATA-E2E-05升partial，251为213partial/38planned/0verified；重叠缺口241生产/19实现/8测试/24外部不变。

实网准备：复用qa-pm6-google-live.mjs，增加--executable和--output-dir，允许现有服务账号实网流程指向隔离安装的PM9包；仅参数检查通过，尚未运行当前实网。需授权测试凭据路径和可写测试表；OAuth另需桌面客户端及交互授权，系统UUID/增列/完整业务联合链也仍待实网。历史PM6服务账号/系统凭据实网证据继续有效。没有采用模拟结果抵扣实网。

当前ee2524af生产输出重新生成ARM DMG，校验、只读挂载、隔离复制、卸载镜像、真实包内sidecar健康和父进程退出清理通过，临时应用副本已删除。asar与backend hash匹配上一轮完整回归，不重复全量；安装镜像hash见joint-external-acceptance.json。本机0有效代码签名身份，仅ad-hoc且TeamIdentifier未设；spctl虽然exit0，但明确override=security disabled，不能算Gatekeeper/签名/公证通过。Apple/Windows签名资源和Windows/Intel实机入口仍需提供；既有Actions继续运行，不重复流水线。当前新增联合测试尚未包含于旧运行。releaseAccepted=false。
