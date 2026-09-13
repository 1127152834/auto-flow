# Studio 图编辑未保存状态

2026-09-14。修复 addNode、deleteNode、onConnect 的脏状态遗漏，并避免不存在删除或重复连线污染历史。6 个新增用例；全量 119 文件/1383 用例通过，类型/lint/构建通过。浏览器验证删除最后节点后新建触发保护，取消后可撤销恢复。详见 docs/migration/studio-frontend-completion/graph-dirty-validation.md。正式 Electron 和 F0–F6 尚未全量验收。
