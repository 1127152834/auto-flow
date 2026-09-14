# 审查问题与闭合记录

日期：2026-09-14；状态：confirmed（本轮代码与证据审查）。

| 问题 | 修正 | 复核 |
|---|---|---|
| 主要 IP / 模型上下文仍 12px，部分创建按钮40px | 主值14px、列表创建工具32px；辅助文案保持层级 | 规格智能体复核；Electron computed metrics |
| AI Markdown 含合法属性的 table 可能漏样式 | DOMPurify 后用 DOM 遍历装饰所有表，不修改原值和消毒边界 | MessageBubble 测试包含脚本/onerror移除、合法属性表 |
| 无layer的 toolbar display 覆盖调用方 grid | 默认布局归于 cn Tailwind utilities；视觉规则留CSS | 组件覆盖测试与模型实图 |
| TableScroll overflow 覆盖调用方轴向约束 | 默认overflow归于utility，生成Markdown显式overflow-auto | 组件测试、源扫描 |
| Studio宽表纵滚动条随内容移出视口 | 正文唯一双向滚动，表头同步偏移 | 1万行真实组件QA |
| Studio焦点在不滚动的外框 | 真正正文region/tabIndex=0，外框不占Tab | PageDown实际滚动；聚焦屏外列头后headerX=rowX=-370 |
| 同时运行多个Electron流程发生非确定点击超时 | GUI流程改为串行运行；保留失败报告；未删业务断言 | run-RRCBkm、run-J7B7of走通。不能据此断言已定位所有首次失败根因 |
| 脚本仍查旧toolbar role | 改查具名group，继续验证列表数量不因不匹配新增而变化 | E14-list通过 |
| Studio元数据脚本缺忽略的参考源码 | 只读复制所需冻结源文件到本worktree ignored reference路径 | 48脚本测试通过；脚本生成的无关Studio台账恢复到原HEAD |

独立规格与工程审查由 table_spec_review、table_quality_review 完成；最终工程审查无未闭合阻断，并重新计算renderer源码hash与components-rOXBoV一致。此结论不替代用户手测，不宣称Windows、打包或外部模型/代理服务通过。
