# 代理检测按钮反馈

- 日期：2026-09-12
- 状态：confirmed
- 来源：用户要求检测期间将检测图标切换为 loading，获得结果后恢复。
- 改动：代理列表与详情统一使用现有 Phosphor CircleNotch + animate-spin；按钮通过 aria-busy 标记忙碌，继续禁用重复点击。复用 checkingId/probing，请求与结果刷新完成或异常后的 finally 恢复 Pulse 图标；不修改后端和检测协议。
- 验证：既有代理页面 12 项交互测试通过；TypeScript、ESLint、生产构建、git diff --check 通过。
