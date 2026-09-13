# F1 图像资源类型与响应契约

2026-09-14。图像元数据及上传、重命名、移动、目录变更响应由 AutoFlow 的 Pydantic 模型定义，经现有 OpenAPI 生成链供 Studio API 和 ImageAsset 引用。未增加业务路由或文件存储实现。

上传必须返回 asset 包络；重命名同时返回 success 和 asset。目录创建、重命名、删除及移动分别返回 path、newPath、deletedCount、newFolder。size 为非负安全整数，success 严格布尔，path 可缺省或 null；兼容现有扩展元数据。uploadedAt 保持字符串，未增加日期格式保证。

新增 Python 契约用例 21 项；加命令与 schema 导出回归共 43 项通过。前端图像/HTTP 相关 60 项通过；类型、lint、构建、OpenAPI 一致性、Ruff 和 mypy 通过。证据见 evidence/f1-image-schema。未在本批重跑全量或 Electron 端到端，不将类型检查算作真实文件服务验收。

运行时图像响应验证、完整服务 operation 矩阵及正式宿主接入仍需补齐。生成类型本身不能替代网络数据校验，F1 未完成。
