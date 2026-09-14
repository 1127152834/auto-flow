# 全局精细网格表格实施计划

> For agentic workers: 使用 superpowers:subagent-driven-development 分包审查，verification-before-completion 核验。

**Goal:** 以第二种精细网格统一真实表格及其查询工具。
**Architecture:** 复用React原生表语义和Radix控件；共享视觉令牌、Table、TableScroll、TableToolbar；业务行为留在领域。
**Tech Stack:** React19、TypeScript、Tailwind4、现有Vitest/Electron CDP。

## T0 盘点
- [x] 初始核对 dcb1831/cda081d；主线整合后改从 bdca5ee 创建独立 autoflow-table-system 分支，保留行内新增及 Studio，主线只读。
- [x] 生成使用点清单，区分主线独有、嵌套、文档及非table虚拟网格。

## T1 共享基础（主协调）
文件：renderer/shared/components/ui/table.tsx、table-toolbar.tsx（新）、styles/tables.css（新）、styles/index.css、ui/pagination.tsx。
- [x] 先补table.test.tsx，验证TableScroll具名region、ref、scope、选中行，运行npm test -- table.test.tsx得到缺少导出的失败。
- [x] Table增加af-table标记；TableScroll有label/children及div原生props；TableToolbar有label/children及div props，role=group避免承诺未实现的toolbar箭头协议。
- [x] tables.css集中横纵1px线、14/20px正文、8px横/5px纵padding、32px工具、40px含按钮行，分离普通表与键值表hover。
- [x] 运行组件测试、typecheck；可访问状态不靠CSS伪造。

## T2 领域接入（实现智能体，独占以下文件）
路径前缀apps/desktop/src/renderer/domains：
project-data/components/{SchemaEditor,SchemaImpactDrawer,DataTableSourcePanel,ExcelInspectionPanel,DataStatusTable}.tsx；
proxies/components/{ProxyFleet,LocalProxyGroups}.tsx；models/components/ModelDirectory.tsx。
- [x] 原生table/th/td改为共享组件，保留列、事件、空态、真实状态及禁用。移除局部大padding/字号，不改接口。
- [x] 查询工具用TableToolbar，紧凑控件；保留原查询触发方式。模型原生select换现有Select，不留系统下拉。
- [x] npm test -- ModelDirectory ProxyFleet LocalProxyGroups SchemaEditor DataStatusTable；再审规格、再审工程。

## T3 记录表与查询（主协调）
project-data/components/{DataRecordsTable,RecordQueryToolbar}.tsx。
- [x] 保留typed身份和筛选表达式；只调整共享TableScroll、选中行、状态标记、紧凑工具。
- [x] 移除h-12/text-base/py-3等局部样式；记录列宽按角色收紧，长内容由原详情展开。
- [x] npm test -- DataRecordsTable RecordQueryToolbar pagination；全部断言保留。

## T4 主线Studio差异
- [x] 只读复核workflows/components/{DataTable,LogPanel,DebugBar,documentation/MarkdownRenderer}.tsx。
- [x] 在 bdca5ee 的独立交付工作区实际接入 Studio，不覆盖其他任务 WIP、不修改数据库。
- [x] 虚拟网格保持索引映射和虚拟滚动；不能用CSS改行高却不改estimateSize。

## T5 验证与交付
- [x] npm test -- --maxWorkers=2、npm run typecheck、npm run lint、npm run build。
- [x] npm run openapi:check、npm run test:scripts、npm run test:structure、git diff --check。
- [x] node scripts/qa-record-grid-entry.mjs、node scripts/qa-project-alignment-r3.mjs（旧 smoke-project-data 仍期望已退役的整页新增，改用现行行内新增 E2E，业务断言保留），截图真实新构建。旧QA断言若明确只约束旧样式则记录被新规格替代，业务断言不得删除。
- [x] 新表格验收报告列出实际截图、computed尺寸、作用范围及未执行平台。
- [x] 交付手测：记录→筛选取消/应用→字段/状态→来源→模型/代理→Excel预览；100/200%及Tab/Escape，不触碰业务数据。
- [x] 只提交本任务明确文件；不宣称主线集成、Windows或用户手测已通过。


## 完成记录（2026-09-14）

实际交付已从 bdca5ee 的 autoflow-table-system 完成，主目录未修改；T4 包括AI回复Markdown（补齐原计划盘点遗漏）。详见 docs/ui/table-system/README.md 与机器报告。T5业务回归替换过时整页新增脚本为现行qa-record-grid-entry；其17组本轮断言通过，整体partial与未执行项如实保留。额外完成Studio窗口回归及1万行组件键盘验证。Windows和用户手测不在上述完成勾选中。红阶段/早期失败记录保留在verification与runs，未删业务断言。
