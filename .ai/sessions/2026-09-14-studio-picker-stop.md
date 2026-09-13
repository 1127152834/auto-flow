# 拾取停止确认

修复当前ConfigPanel在停止业务失败后误报已停止及Promise未处理的问题。显式/单选/相似停止共用确认，失败保留重试，等待去重。新增7项加已有回归36通过；UI503失败和重试通过。卸载/跨入口所有权仍待完整会话合同，未宣称全局清理完成。见docs/migration/studio-frontend-completion/picker-stop-validation.md。
