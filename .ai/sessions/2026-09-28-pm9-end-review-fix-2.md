# PM9 End 审查修复 round 2

- 日期：2026-09-28；状态：confirmed（实现与定向验证），主控复审待进行。
- 来源：FIX_BASE 1fdda1c8 的新增P2，task-1-report round2 与 `docs/qa/2026-09-28-remediation/pm9-end/fix2-*`。
- 改动：DurableEndResult复用createOperationCommand，发送前持久保存原键；未知仅核验，禁新提交；连接资格与workspace恢复键分离，存储失败不写。已知结果刷新事实而不改变历史Run。
- 必要接线：已有repairEndAssociation/environment定位器/EnvironmentOutcome加入公共ProjectOperationView，结果error完整保留，生成类型更新。无权限/运行语义改变。
- 验证：29前端、1真实SQLite/ASGI原键身份合同、6项目合同；TS/OpenAPI/ESLint/Ruff/2模型mypy通过。红/绿精确命令与退出码已归档。传输故障为组件模拟，无物理断连；无新浏览器、冻结包、Electron人工或跨平台证据。
- 不改AOCI、主控QA、其他WIP，不push；后续主控范围复审。
