# 最终稳定版验收结果

日期：2026-09-28；状态：in_progress。来源：下列本轮原始日志、JUnit XML与command.json。置信度：已执行结果高；未执行不推断通过。业务源码基准d6f9cb0f，之后若仅前端或测试维护变动，会逐项声明适用范围。

| 类别 | 当前结果 | 证据与边界 |
| --- | --- | --- |
| 默认后端第一轮 | 4325通过、1失败、50跳过；1106.46秒 | final-backend-default.*；源码前后摘要一致。唯一失败为精确注册表集合遗漏本轮project_end，489224c5按Task1第三轮修复后，第二轮全量正在执行；本轮不能写全绿 |
| 默认后端最终第二轮 | 4326通过、0失败、50跳过；1897.86秒 | final-backend-default-v2.*；源码与测试前后摘要均一致；489224c5仅补精确基线 |
| 迁移与结构 | 80通过 | 最终第二轮默认回归子集，final-backend-default-v2-summary.json列出完整名称；不是80条独立升级路径，不额外累计 |
| 真实浏览器补跑 | 49通过，0失败/跳过；318.76秒 | final-real-browser.*：48真实浏览器检查+1实际浏览器执行后的内部回执注入。不是49个完整项目闭环，不是供应商实网或物理失联证明 |
| 冻结worker | 6通过，1明确不选的内部注入；43.86秒 | final-frozen-worker.*：正式项目数据1场景、End线性/循环/工作流/模块/画布5场景，每个End正向包含后续登录复用。Python宿主调度冻结worker，不冒称完整Electron原生操作 |
| 根脚本 | 102通过 | final-root-scripts.*，检查未覆盖历史验收文件 |
| 后端静态 | Ruff通过；普通mypy509源文件通过；strict1041既有/0新增；OpenAPI一致 | final-{ruff,mypy,strict,openapi}.log及final-backend-static.command.json。strict不是全量零错误 |
| 冻结后端构建 | exit0，168.53秒 | final-backend-build.*，源码前后摘要一致；后续真实冻结测试二进制SHA256前后一致 |
| 默认前端第一轮 | 5663通过、1失败（432文件）；lint/typecheck通过 | final-frontend-default.log、final-frontend-gates.command.json；唯一失败为新增End后的配色审计精确计数217→218遗漏。源码前后摘要一致；未称全绿 |
| 最终桌面构建及打包UI | 待Task3审查整改后执行 | Task3审查发现脚本请求读取的独立通信失败仍被归为操作失败，需补修与回归 |

历史三个负向worker终态异常、四项sidecar READY异常在本轮默认回归未重现；旧失败缺PID或stderr，不能据当前绿灯倒推它们全部由同一根因造成。真实SIGKILL已确认的冗余归属检查缺陷有独立红绿证据，见worker-cleanup-diagnosis.md。

End原始JSON按真实临时根归档，final-source-end为6个唯一场景（5正向+1内部注入），final-frozen-end为5个唯一正向场景。两个*rcurrent.json是pytest current目录符号链接产生的逐字重复副本，summary.json明确指向原文件，不额外计数。

未完成：人工跨应用重启续接等待原有现场语义差异裁定；Windows/Intel、指定外部账号/付费模型/消息发送、共享Android VM恢复与硬件用例未执行。AOCI仍由另一任务初始化，未介入维护。当前不能宣称完整生产验收通过。

默认后端50跳过逐个与真实补跑XML按classname/name核对：49项全部有独立门控通过记录，唯一未执行为付费模型真实调用。完整映射见 final-skip-coverage.json；其中内部回执注入仍按其真实边界标记，不改称物理故障验收。

第二轮耗时比第一轮长，原始时长如实保留；未调整超时、跳过或断言。final-skip-coverage-v2.json再次核对50项跳过中49项有真实浏览器门控证据，1项付费模型未执行。

前端第二阶段dae16113：432文件/5665测试通过，lint/type/build/package均exit0，源码摘要前后一致（final-frontend-v2-*）。独立复审随后发现claim等待阻塞轮询，Task3第二轮修复进行中；因此该阶段不代表最终前端通过。

打包End阶段packaged-end-v2：真实生产包、SQLite与本地HTTP，首次Run保留登录、完整应用重启、第二Run复用Cookie、End后继无请求、两会话进程退出通过；binary/asar指纹独立记录。原生随后能读取持久End完成结果，但配置回显/保存发现UI-03 nested/flat分歧，native-session-VwvJnD为失败证据。Task6必须修复后再验，不能计整个原生配置验收通过。
