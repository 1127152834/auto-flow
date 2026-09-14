# 全局小圆角

2026-09-14，confirmed。用户在精细网格完成后明确要求全系统更硬朗、接近直角但保留可见圆角。统一为小元素2px、控件4px、卡片/表格/弹窗6px；覆盖主窗口与Studio。唯一设计令牌为renderer/styles/radii.css，替代原control8/card12/modal16及Studio最大22px。圆形语义控件、画布连接点与原生窗口外壳保持。后续新增UI复用语义令牌，不再写独立大圆角。规格、实图与核验见docs/ui/radius-system。
