# 镜像拉取完成回执窗口中断

- 日期：2026-09-24；状态：confirmed（真实 HTTP/SQLite/Mac 实验），T09 全部交付 partial。
- 来源：[QA 与原始输出](../../docs/qa/android-management/2026-09-24-image-pull-interruption.md)。后端产品基线33e7f547，没有新业务代码、契约、schema 或 migration。
- 授权范围：用户完整 AM1–AM4 验收；仅新临时工作区，使用既有官方固定 RepoDigest；不删除基础镜像，不创建/触碰外部设备。
- 依赖冲突：本轮隐藏页修复的完整前端门禁并行运行，镜像实验只新增 QA 脚本/证据，不修改其候选产品源码；三份 Studio 文件继续保护。
- 实验：真实拉取与目录回执事务完成后注入暂停，杀死自有 sidecar 进程组；实际客户端 RemoteProtocolError，重启 needs_verification，原 requestId 重提仍未知不再拉取，显式核实得到 IMAGE_PULL_VERIFIED；实际 catalog.pull 总数1。
- 首次 QA 脚本误用新核实请求号得到409，已查生产契约并修正；该轮原工作区先按原编号恢复并取消登记，完整修正版从新工作区重跑exit0。保留失败输出，不改产品门禁。
- 独立审查修正 RepoDigests 选择、marker原子发布、失败报告说明；最终无 Critical/Important。38项镜像单元/契约/集成通过，Ruff通过，CLI缺授权标志exit2。
- 清理：两轮只取消各自登记，deleteContent=false；基础tag Id保持，未创建实例/卷，自有服务退出。
- 未覆盖：镜像层下载途中网络中断、真实桌面镜像内容删除；Mac锁屏仍阻塞后者。下一步继续核查页面对未知拉取的显式核实入口，不以HTTP实验推断页面已接齐。
