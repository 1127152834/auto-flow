# 最终稳定版验收结果

日期：2026-09-28；状态：confirmed（已执行结果）；完整产品验收仍未完成。来源：下列本轮原始日志、JUnit XML与command.json。置信度：已执行结果高；未执行不推断通过。业务源码基准d6f9cb0f，之后若仅前端或测试维护变动，会逐项声明适用范围。

| 类别 | 当前结果 | 证据与边界 |
| --- | --- | --- |
| 默认后端第一轮 | 4325通过、1失败、50跳过；1106.46秒 | final-backend-default.*；源码前后摘要一致。唯一失败为精确注册表集合遗漏本轮project_end，489224c5按Task1第三轮修复后，第二轮完整重跑结果见下一行；本轮失败原样保留 |
| 默认后端最终第二轮 | 4326通过、0失败、50跳过；1897.86秒 | final-backend-default-v2.*；源码与测试前后摘要均一致；489224c5仅补精确基线 |
| 迁移与结构 | 80通过 | 最终第二轮默认回归子集，final-backend-default-v2-summary.json列出完整名称；不是80条独立升级路径，不额外累计 |
| 真实浏览器补跑 | 49通过，0失败/跳过；318.76秒 | final-real-browser.*：48真实浏览器检查+1实际浏览器执行后的内部回执注入。不是49个完整项目闭环，不是供应商实网或物理失联证明 |
| 冻结worker | 6通过，1明确不选的内部注入；43.86秒 | final-frozen-worker.*：正式项目数据1场景、End线性/循环/工作流/模块/画布5场景，每个End正向包含后续登录复用。Python宿主调度冻结worker，不冒称完整Electron原生操作 |
| 根脚本最终版 | 102通过、0失败/跳过 | final-frontend-v3-root-scripts.log，在e49144f2执行；历史验收文件未改写 |
| 后端静态 | Ruff通过；普通mypy509源文件通过；strict1041既有/0新增；OpenAPI一致 | final-{ruff,mypy,strict,openapi}.log及final-backend-static.command.json。strict不是全量零错误 |
| 冻结后端构建 | exit0，168.53秒 | final-backend-build.*，源码前后摘要一致；后续真实冻结测试二进制SHA256前后一致 |
| 默认前端第一轮 | 5663通过、1失败（432文件）；lint/typecheck通过 | final-frontend-default.log、final-frontend-gates.command.json；唯一失败为新增End后的配色审计精确计数217→218遗漏。源码前后摘要一致；未称全绿 |
| 默认前端第三阶段 | 5683通过、433文件、0失败；190.38秒 | final-frontend-v3-default.log；e49144f2，源码前后摘要一致；未屏蔽localStorage实验性警告 |
| 默认前端最终第四轮 | 5686通过、433文件、0失败；187.03秒 | final-frontend-v4-default.log；c2367a17，源码前后摘要一致 |
| 最终根脚本 | 102通过、0失败/跳过 | final-frontend-v4-root-scripts.log |
| 最终桌面门禁 | lint/typecheck/build/package全部exit0 | final-frontend-v4-gates.command.json：7.70/23.74/33.54/27.60秒；源码摘要362a41041b8582c938c99553a871df312588bb9227523895205d43336c158ccf |
| 最终打包End | 1场景通过（2个实际Run、2次完整应用启动） | packaged-end-v4.command.json，23.81秒；packaged-end-4CaggM/result.json；新Run真实Cookie复用，End后继无请求，两次进程均退出 |
| 最终原生配置 | 2场景通过，2次应用会话 | final-native-config.json；真实RecordRef静态数组保留/清空、nested子流程选择，SQLite保存及整应用重启保持；不计为执行链场景 |

历史三个负向worker终态异常、四项sidecar READY异常在本轮默认回归未重现；旧失败缺PID或stderr，不能据当前绿灯倒推它们全部由同一根因造成。真实SIGKILL已确认的冗余归属检查缺陷有独立红绿证据，见worker-cleanup-diagnosis.md。

End原始JSON按真实临时根归档，final-source-end为6个唯一场景（5正向+1内部注入），final-frozen-end为5个唯一正向场景。两个*rcurrent.json是pytest current目录符号链接产生的逐字重复副本，summary.json明确指向原文件，不额外计数。

未完成：人工跨应用重启续接等待原有现场语义差异裁定；Windows/Intel、指定外部账号/付费模型/消息发送、共享Android VM恢复与硬件用例未执行。AOCI仍由另一任务初始化，未介入维护。当前不能宣称完整生产验收通过。

默认后端50跳过逐个与真实补跑XML按classname/name核对：49项全部有独立门控通过记录，唯一未执行为付费模型真实调用。完整映射见 final-skip-coverage.json；其中内部回执注入仍按其真实边界标记，不改称物理故障验收。

第二轮耗时比第一轮长，原始时长如实保留；未调整超时、跳过或断言。final-skip-coverage-v2.json再次核对50项跳过中49项有真实浏览器门控证据，1项付费模型未执行。

前端第二阶段dae16113：432文件/5665测试通过，lint/type/build/package均exit0，源码摘要前后一致（final-frontend-v2-*）。独立复审随后发现claim等待阻塞轮询与同实例重连恢复缺陷，现已由d2bcae4f/8828eb2a修复并完成独立复审；Task6还有共享配置变更，因此该阶段不代表最终前端通过。

打包End阶段packaged-end-v2：真实生产包、SQLite与本地HTTP，首次Run保留登录、完整应用重启、第二Run复用Cookie、End后继无请求、两会话进程退出通过；binary/asar指纹独立记录。原生随后能读取持久End完成结果，但配置回显/保存发现UI-03 nested/flat分歧，native-session-VwvJnD为失败证据。Task6必须修复后再验，不能计整个原生配置验收通过。

AOCI在本次压缩恢复中交付4/8块后返回cognition_snapshot_unavailable：正式索引在交付期间变化，工具拒绝混合快照。未完成交付/Attestation，未接管另一任务的初始化或维护；当前工程结论绑定实际源码、提交和运行证据。

2026-09-28后续证据：packaged-end-v3在e49144f2完整应用运行、重启、Cookie复用及进程清理通过；native-session-ZM6bSH/LCCIyR原生保存revision4、重开、整应用重启、真实任务c9645a83-df96-4a05-9cb1-53e3ea70316d成功，持久环境名称与UI输入一致，专属网页收到真实请求。两次原生应用及HTTP服务均已退出。最终c2367a17仅前端两项修复，单独补门禁/原生验收，不冒称上述包已含最新改动。

最近AOCI刷新8dca481f-4a40-4bc9-afac-6ef6ca880cad已完整收到10块/553条并确认交付；Attestation因工具未展开的答案字段schema不匹配尚未提交成功，未猜测语义重试；治理dirty/stale且另一任务拥有维护责任。已加载且交付已验证，不宣称当前完整系统认知可靠。

最终结果校验：以上c2367a17门禁已完成；此前“执行中/补验中”段落为阶段记录，已由本段及最终表格替代。backend-evidence-applicability.json证明489224c5之后backend全部未变，真实worker二进制SHA256仍b0b94c9c7e13372d9f97a9f941e24dc106fbf92f0db75fea72205eda75768bbe，因此不重复相同后端全量。最新版app.asar SHA256为faaf7f667e92240e85699fb19b54c9e861ca5f7b133197b557b26d0fc3f97311。final-resource-cleanup.json确认6个明确归属的最终QA临时目录均已移除，未清除历史报告、SDD待决记录或其他任务资源。
