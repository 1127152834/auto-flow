# PM9 Profile 冻结补证与代理资源缺口

日期：2026-09-24。状态：confirmed（Profile 打包 API 子范围与代理诊断）；完整 ARM 桌面已通过，P1–P3 方案状态见专项 JSON。

来源：生产源码69baeeb2的ARM正式sidecar、公开HTTP/真实worker、现有资源类和SQL选择器；`docs/project-management/implementation/pm9/resource-freeze-follow-through.json`记录原始报告路径、哈希和边界。

- 复用现有运行脚本，在首Task人工屏障修改Profile、重置种子和编辑根文档。旧批次第二Task使用原文档变量、UA/en-US/UTC；显式新批次使用新变量、UA/fr-FR/Europe/Paris。macOS既有进程读取器只提取本次隔离实例的主浏览器PID/seed，实际旧/旧/新种子符合冻结。完整argv不输出。
- 首次测试错误地要求Canvas随seed变化而变化，失败报告保留。最终检查实际启动seed，Canvas仍相同，如实报告false；不把它解释为全部指纹保护有效或失效。其他平台argv证据明确pending。
- Profile测试使用显式none代理。不能将其通过扩写为代理冻结通过：真实WorkflowBrowserResources只保存pool ID，实际SQL选择器在同一快照后续acquire使用新成员及新端点。诊断使用合成Profile/kernel/投影，无真实网络或worker；它足以证明生产选择实现缺口，不构成代理实网验收。
- P1–P3补充规格与文件级计划已自审，并按AGENTS架构确认规则提交用户审核。覆盖固定候选/端点、重放/凭据后竞争、关闭领取、环境代次延迟来源；未批准前不修改生产契约。
- ENV-05/XE-A20/XE-C02增加范围断言及implementation_missing分类，状态保持原值。251条仍249有断言/2未定位、206partial/45planned/0verified；缺口按唯一ID计数为241生产证据、16实现、10测试、24外部，分类可重叠。旧按gap条数的统计不等于唯一要求数。
- 生产代码和应用包未变；现有三平台35886627514继续，不重启。新增Profile脚本断言不在该CI源码中。历史PM6服务账号实网/系统凭据证据继续有效；当前打包Google/OAuth、签名及物理发行条件另列。

验证：完整打包API、101脚本、4映射测试、251引用和两脚本语法检查通过；完整ARM桌面通过，21张界面截图；五路万行46500ms/0busy、worker1004条31011ms、固定合成1000条60019ms/最大滞后25ms、两帧6ms，均为单次观察。releaseAccepted=false，不合并发布。
