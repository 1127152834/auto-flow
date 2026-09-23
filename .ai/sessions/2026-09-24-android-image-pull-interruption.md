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

## T12 向前入口回退演练（2026-09-24，in_progress）

- 计划：从5210e388建立一次性隔离checkout，带入当前四份前端候选diff；使用已安装依赖，不修改原worktree。只在一次性checkout移除AM2镜像/模板组件挂载与import，保留AM1实例管理和全部后端/迁移。
- 先用真实AndroidPage组件测试证明“入口已停用”在未打补丁时失败；应用静态发布补丁后通过，并构建。反向恢复该源码补丁后，入口恢复测试及构建通过；对比源码与全部migration字节。无需增加永久运行时开关或破坏性数据库downgrade。
- 这是前向发布源码/构建演练，UI为组件测试，Mac锁屏下不冒称真实桌面点击。已存数据前向迁移与真实旧实例重启/镜像固定由已有独立验收交叉支持。

T12演练结果confirmed：[前端补丁报告](../../docs/qa/android-management/2026-09-24-forward-entry.md)；首次因临时checkout漏desktop局部依赖TS2307，保留失败并清理后重跑。启用GREEN→停用预期RED→源码补丁GREEN/类型/build→恢复源码GREEN/类型/build通过；44份原有migration Python内容、4份候选文件及AndroidPage恢复哈希一致，两次自有checkout均移除。没有DB/设备访问、没有真实Electron，不单独关闭T12.4。

- 2026-09-24 持久拉取恢复（confirmed 软件/真实HTTP，桌面blocked）：重启后按工作区分页发现未知拉取、原编号显式核实、新拉取冻结及422前置拒绝恢复输入已实现；后端34项、Android171项及类型/lint/OpenAPI/build通过，增量审查无C/I。真实强杀重启列表total1→核实→0，pull仅1次，基础镜像保留；未创建用户设备。AM-R12磁盘预检仍待实现，不能归为外部blocked。见[证据](../../docs/qa/android-management/2026-09-24-persistent-pull.md)。
