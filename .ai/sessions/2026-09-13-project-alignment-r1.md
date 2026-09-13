# R1 项目管理对齐实施

日期：2026-09-13。状态：confirmed / 实施进行中。

来源：用户确认 R1 执行计划；实施工作区 HEAD 1e79c7b，git status 只有原三个 QA 未跟踪目录。B0 已由用户确认，历史报告继续保留原验证时状态。

仅实现目录、页头、紧凑查询和通知，不进入 R2。主项目与旧仓只读；共享控件和页面装配由主协调负责，领域纯组件分包。使用 Superpowers writing-plans、subagent-driven-development、test-driven-development、verification-before-completion，提交前先规格后工程审查。复用既有查询语法与 PM2 接口。

阶段完成后提供隔离启动和 R1-M01–09 手动方案，等待用户验收。当前尚无 R1 业务验证结果。


## 交付更新（2026-09-13 confirmed）

上文“进行中/尚无 R1 结果”由本节替代：R1 开发与本机自动验证完成，等待用户验收。代码提交 9c7c354 → fb7d02d → 73a4bc8 → 05aa3e9 → 4daa752，隔离工具 a13e649。来源：acceptance/r1/verification.json、review-resolution.md、manual-test.md。

前端 115 文件 865 项，后端既有目录与查询定向 21 项；静态检查、构建和两个 PM2 smoke 通过。真实 Electron 验证目录、文本搜索/导出一致、浮层100%/200%、真实冲突、响应丢失、重启及两个工作区。实际一万行 Excel 导入 6363ms、下一页158ms，仅为本机样本。系统文件面板在自动文件流程中注入返回，用户原生操作/表格软件复核与 Windows/其他架构/打包未执行。

设计取舍：ProjectTabs 原结构符合本轮要求，仅复用；查询最终表达式按真实字段/状态统一校验，不能先清理后短暂查询全部；工作区浏览偏好留存会话，业务编辑上下文独立清理。主项目/旧仓仅只读参考，原三个 QA 目录未修改。停在 R1 验收点。
