# 全局表格统一为精细网格

日期：2026-09-14。状态：confirmed。来源：用户选定第二种原型并明确授权先共享组件、后全局盘点与迁移；实际源扫描及Electron验收。

全部真实表格使用暖灰/黏土棕的细浅横纵线、14px主值、32px普通单行与查询工具；含操作行40px、多行可增高。行内按钮28px，保留可见焦点。组件复用shared Table/TableScroll/TableToolbar/TableStatus；不增加DataGrid引擎或packages/ui第二实现。普通卡片不强行转表。

基于主线bdca5ee隔离实施，包含同表新增及完整Studio。业务查询、输入草稿、typed身份、CAS、幂等/恢复均保留。Studio只适配视觉和实际滚动焦点，不改执行接口。

范围与验证边界：docs/ui/table-system/inventory.md、verification/report.json；未运行Windows、打包、外部真实代理/模型服务及用户手测不记为通过。
