# F2.2 节点配套工具入口验收

日期：2026-09-15

本批按冻结 WebRPA 配置面板和现有 AutoFlow Store/服务边界核销 `capabilities.json` 登记的全部 385 条工具依赖。测试挂载实际 `ConfigPanel` 消费者；仅将被测工具的外部选择结果或 Monaco 渲染替换为确定夹具，没有绕过节点面板直接改 Store。

- `VariableInput` 174 个节点入口、`VariableNameInput` 86 个、`VariableRefInput` 10 个、`NumberInput` 56 个：逐入口提交唯一标记，断言只改目标字段，并验证撤销、重做和文档重开。
- `PathInput` 19 个节点的 22 个字段：覆盖文件/目录/两者模式及条件分支，验证请求上下文、结果字段和历史。
- `ImagePathInput` 7 个节点的 8 个字段、`Slider` 5 个节点、坐标与双坐标各 1 个节点：验证实际字段换算、成对更新和相邻值保护。
- `AIModelPicker` 3 个节点、共享 `AITaskApiBlock` 8 个节点：验证 Profile 选择、可选字段、后备模型、空列表和已删除 Profile。
- 三种脚本编辑器：通过实际编辑器入口验证 AI 请求、审查后应用、取消、失败、缺配置、零温度和 NDJSON。
- 三个复合下拉部件在 AI 图片、AI 视频和 Webhook 节点中通过实际 Radix Select 交互验证；它们是同一个用户控件的组成部分，不按三个独立用户操作重复声称能力。
- 手势节点的输入、确认和提示对话框通过录制成功、删除成功及服务拒绝三条实际入口验证，失败不修改草稿。

结果：7 个测试文件、396 项通过。385 条台账工具入口全部有对应能力 ID；其余 11 项是共享工具的取消、错误、空状态和协议分支。TypeScript 与本批 ESLint 均通过。详情见 `target.log`、`types.log`、`lint.log` 和 `cases.json`。

边界：涉及服务的用例使用显式类型化 Mock，只证明前端请求和状态消费；不证明摄像头录制、路径选择、模型服务或自动化后端真实执行。原生入口及打包结果留 F6 验收。
