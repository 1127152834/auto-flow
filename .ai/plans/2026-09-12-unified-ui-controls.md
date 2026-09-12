# 全系统基础控件统一

- 日期：2026-09-12。
- 状态：proposed；只有本轮静态盘点和计划文档已完成，尚未批准实施。
- 来源：用户要求先实际盘点、设计与计划，不大规模替换；源码快照c7c3021与主目录15cf2e8。
- 工作位置：`/Users/zhangtiancheng/Documents/projects/autoflow-ui-controls-plan`，分支`codex/ui-controls-plan`。
- 正式盘点：`docs/design-system/2026-09-12-ui-controls-audit.md`及JSON/逐点明细。
- 正式规格：`docs/superpowers/specs/2026-09-12-unified-ui-controls-design.md`。
- 正式计划：`docs/superpowers/plans/2026-09-12-unified-ui-controls.md`，T0–T13，全部实施复选项未勾选。
- 推荐：现有desktop shared内补齐Radix，自有tokens与滚动条，React Aria组合框定向封装；不扩建packages/ui、不改接口/后端/数据。
- 顺序：确认→基线→tokens→展示/浮层G0→共享G1→浏览器/内核→代理/池→模型→设置/总览/壳→扫描与双平台G3。
- 并行保护：主目录在固定快照后继续扩展UA后端目录及EnvironmentOptionField；T0再核对最终接线，禁止用本计划的旧datalist描述覆盖新实现。
- 下个动作：用户确认设计和计划后，读取executing-plans，先核对主线最新提交并执行T0–T2；不把文档分支旧业务checkout覆盖主目录。
- 尚未验证：新行为库与现有Dialog的运行兼容、全部控件视觉、性能、Windows/macOS/读屏验收。
