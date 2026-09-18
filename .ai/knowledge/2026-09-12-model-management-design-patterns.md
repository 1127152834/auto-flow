# 模型管理重设计参考

- 日期：2026-09-12
- 状态：调研与契约边界 confirmed；具体重设计 proposed。
- 来源：用户要求模型选择、模型列表以及设计理念参考成熟产品优化；OpenRouter 实际页面、Dify/Carbon/shadcn/WAI-ARIA 官方资料、当前源码。
- 参考与截图：[产品模式调研](../../docs/references/model-management-redesign-2026-09-12/README.md)。
- 方案：[重设计简报](../../docs/prototype/model-management/redesign-brief.md)。
- 稳定约束：供应商连接、远端目录候选、本地已添加模型和任务内单选是不同任务；设计应明确其作用域。连接检查成功、模型 enabled 和单次推理成功分别表达。
- 数据边界：当前缺少价格、能力、收藏/最近使用和持久模型健康字段；已有连接没有批量添加接口。原型不虚构这些支持。
- 实施状态：本轮仅研究与设计资料，不改业务代码、不调用推理、不修改用户连接或模型。
