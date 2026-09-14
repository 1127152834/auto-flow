# Studio 调试命令与暂停身份

2026-09-14。本批完成 resume/step 的服务端暂停身份、控制修订、稳定命令 ID、并发幂等及查询确认。SSE 驱动 UI，旧暂停事件不再解锁命令，旧 resumed 不清除新暂停。复用 events/commands，不引入第二套执行器。

专项90、补强回归14、DTO13、全量2922、类型/lint/Ruff/mypy/OpenAPI/49脚本/构建通过。IAB 实际单步后仅1次 Mock调度并停止保存。39条逐项台账。没有验证真实后端执行或正式 Electron。

详见 docs/migration/studio-frontend-completion/debug-pause-command-contract.md。继续 F2 配套代码编辑器动态补全；不把本批通过当作 F1/F3 整批完成。
