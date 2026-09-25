# 模型管理首页操作提示自动消失

- 日期：2026-09-24
- 状态：confirmed
- 来源：用户截图指出供应商连接提示常驻，要求显示 2 秒后消失；源码及定向自动测试验证。
- 根因：`use-model-management.ts` 未清理操作反馈；`ModelManagementPage.tsx` 又使用持久化 `lastCheckMessage` 作为通知兜底。
- 实现：首页供应商连接测试、模型行测试和启停失败反馈 2 秒后移除；同一提示再次触发重置计时，供应商之间独立计时，页面卸载清理现有定时器。不再回显历史检查消息，连接状态徽标与检查时间保留。Modal 内联结果、表单错误及列表加载错误不在本次范围。
- 验证：新增 5 个回归场景在修复前全部按预期失败；`npm test -- src/renderer/domains/models` 5 文件 / 44 测试通过；`npm run typecheck`、`npm run lint`、`npm run build`、`git diff --check` 通过。
- 限制：未进行真实 Electron 手测；测试使用现有 API 替身与真实页面组件。构建有依赖注释和分包体积警告，测试有 Node localStorage 实验性警告。
- 文档：已更新 `docs/prototype/model-management/model-management-interactions.md` 的反馈规则及验收项；此前首页反馈常驻行为 superseded。
