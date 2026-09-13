# Studio 对齐修复

2026-09-14，confirmed。下对齐按底边计算，使用原有节点尺寸和撤销机制。3 新回归用例，相关 11 用例、类型、lint、构建通过；此前全量 111/1295 通过。详见 docs/migration/studio-frontend-completion/alignment-validation.md。分组 parentId 映射及完整 F2 工具矩阵仍未关闭。
