# Studio 手势历史修复

日期：2026-09-13；状态：implemented/verified（局部）。

原实现拖动结束才pushHistory，已丢失起点；无dragging标志的位置编辑也不标脏。改为首个拖动/显式resize事件前快照，并复用节点UI手势标志合并后续事件。规则测试先红后绿，真实浏览器拖动/快捷键已回验。详见 docs/migration/studio-frontend-completion/editor-history-validation.md。下一项变量编辑的保存与历史；总F0–F6仍在进行。
