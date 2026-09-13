# M6 网页录制设计建议

> 2026-09-13 路线替代（superseded）：用户要求完整迁入 WebRPA UI、前端交互及后端业务逻辑，并允许弃用现有 Studio 实现。后续以[源码迁入规格](../../docs/superpowers/specs/2026-09-13-studio-webrpa-source-migration-design.md)为准。本文保留为历史记录；旧自定义视觉、节点/执行模型及 M6 计划不再约束新 Studio。M6 未完成试验已归档，不能标为交付。

- 日期：2026-09-13。
- 状态：proposed；用户授权下一阶段文档，尚未确认实施。
- 来源：当前 M1–M5 源码、M5复测记录、冻结WebRPA recorder.py与RecorderPanel.tsx静态读取。

建议先做常见网页录制和必要回放节点：独立可见临时浏览器，ready后开始；停止后审查、一次性加入普通流程；不建立另一套回放器。复用workflows领域、共享定位、浏览器启动/进程监护、资源互斥及离开协调。

录制草稿独立持久化，读取不消费，控制使用稳定ID和确认截止序号。录制不是运行，不写运行历史。导航尾部不能确认时显示缺口；异常重启仅恢复审查，不恢复浏览器或重放操作。

原文可能包含现有模板语法，因此建议schemaVersion3加入literalPaths，v1/v2保持原语义。页面别名与流程变量分离。新执行节点先真实可用，再允许录制生成。密码字段页面侧不读取原值，待补值不等于合法空文本。

范围建议包含常见输入、点击、选择、勾选、限定按键、滚动、导航和页面路由；WebRPA已有drag/upload本轮仍未对齐，明确进入后续专项。子流程、错误处理/重试、双视图/分组继续未完成。

完整规格与实施批次只有一份正文，分别见docs/superpowers/specs/2026-09-13-automation-studio-m6-design.md和docs/superpowers/plans/2026-09-13-automation-studio-m6-implementation.md。没有新增业务代码或M6实测证据；技术判断高置信，实际采集可靠性待批次A验证。
