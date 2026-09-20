# F3 确定执行轨迹夹具

2026-09-14，confirmed。configureMock 可设置下一次运行的 executionOrder（节点ID数组）；开发场景面板提供输入/应用/恢复顺序入口。接受启动时从文档副本选择节点并冻结顺序，允许重复ID；缺失节点422且不产生运行事件。配置只供模拟，不修改已保存文档、不求值条件或循环、不执行用户代码。原顺序夹具保持可用。

轨迹共享现有 tick、断点、单步、停止、事件和结果通道。日志增加本次调度序号；重复提取保留两行结果。启动后改变轨迹配置不会改变活跃运行。

6个新用例（内存和真实HTTP各3）：所选分支与重复结果/冻结，过期节点ID拒绝，重复断点和单步。相关20通过；全量125文件/1453用例、类型/lint/构建通过。证据 evidence/f3-execution-order，含实际浏览器导入→断点→单步→继续→日志与两条结果。

这是F3测试基础与一条已验证交互链。执行ID/循环上下文完整合同、嵌套与零轮轨迹台账、命令迟到、运行身份隔离、刷新历史、服务端筛选分页和正式Electron仍待实现/验收，不能据此宣布F3完成。

## 2026-09-15 F5功能块关闭

保留当前改动，沿用唯一剩余清单。F4.2原生录制审查恢复/生成/撤销/保存/独立Mock运行已核销；F5拾取/暂停运行/录制 × 关窗/退出/换区9格通过真实CUA操作，额外主窗先关闭及显式服务重启通过。修复提交阶段设置守卫滞后及历史日志遮蔽离开失败反馈；红测与回归见f5-settings-commit。显式重启新身份和无动作重放由真实hooks+Mock网络测试补证。剩余5块，继续节点具体字段/工具核销，独立凭据UI缺口并行。macOS arm64构建HTML+Mock仅证明前端/宿主；真实后端/分发包/其它平台不计通过。AI代码助手保留原版三入口，修复温度0默认及NDJSON重复读取，8项通过。

## 2026-09-15 定时停止安全检查点

用户授权定时停止指令到达后，不再启动工作/新测试，已通知全部子代理收尾。当前已提交ba8d896(F5离开协调)、52bba7f(AI代码消费/字段入口)；保留所有其它未提交修改及无关工作。

已验证但部分尚未提交/回填：高级配置及数值预检、网页导航合并7文件174项通过，整体类型检查通过（evidence/f2-common-advanced/merged*.log）；导航14项通过。凭据管理字段/独立改名、原子命令Mock协议7文件143项、DTO31项、最后UI9项、类型/lint/Ruff/OpenAPI检查通过，见evidence/f5-credential-fields；尚未整合最新构建/原生凭据UI。选择器核心10节点11字段专项通过，后续消费者待核销。未运行新全量构建。

恢复首先处理未完成F2.3结构复制：editor-store.ts有未提交remapNodeReferences和两种paste/merge修改；structure-copy-references.test.ts最后仍3失败。两paste已通过内部引用/相对坐标断言，后续比较因history剥离selected而失败，须按文档状态判断（不能放宽身份/位置断言）；merge仍保留旧parentId，说明映射尚未真正接入，必须修复。失败证据evidence/f2-structure-copy/interrupted-failing.log，不计通过，不撤销半成品。不为停止继续修复。

唯一剩余清单仍5块：F2.2节点/工具、F2.3文档/编辑、F5.3配置/AI、F1合同、F6正式窗口/平台/交接。已有新的字段核销在capabilities.json工作树，尚需把高级54用例/选择器11用例/凭据新用例回填verified-cases和总表。F2.3核销附件evidence/f2-document-reconcile.md：既有自定义模块编辑18项及文档/普通编辑/500节点沿用；复杂结构、导出、模块列表依赖仍未全验收。真实后端执行/采集/秘密存储不算Mock通过。

停止确认补记：本任务启动的Electron通过原生Cmd+Q正常退出，exec44752 exit0；没有强杀其它应用。三个子代理均已完成收尾且无自启测试进程。导出专项最终16项中13通过/3失败：三种脚本导出忽略workflowApi.update.error，仍导出旧内容，恢复应修Toolbar两handler后回归；新document-export-entry.test.tsx未跑type/lint，evidence/f2-document-export/before.log保留。选择器11项证据已完整落f2-selector-entries（tests/types/lint、entries/cases），其余15字段直接按entries续做。全部未提交修改保持原样；不因停止而补跑测试或把失败改为通过。
