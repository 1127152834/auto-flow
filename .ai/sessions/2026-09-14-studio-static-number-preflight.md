# 静态数字运行预检

2026-09-14；confirmed（有界范围）。来源：NumberInput、ConfigPanel、冻结workflow_executor.py及27项新增测试；定向105项、类型/lint/build通过，实际IAB验证拒绝与修正后Mock启动。

复用严格整串有限十进制解析，所有运行入口读取当前Store进行静态检查；直接起点过滤上游，失败保留原文、日志定位字段并选中节点。共享内部超时例外以冻结源码为准，未引入表达式执行。

后续：必填字段元数据接口缺失且失败缓存为空，需补合同、Mock返回、失败重试和连接隔离；当前不能声称284节点完整校验。见docs/migration/studio-frontend-completion/static-number-preflight.md。
