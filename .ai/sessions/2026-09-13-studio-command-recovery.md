# Studio 命令响应恢复

日期：2026-09-13；状态：局部implemented/verified。

修复HTTP与事件停止不校验目标导致串线；原命令ID可读成功/拒绝结果；前端丢响应查询原ID，未确认不重发。真实本地HTTP主动断开连接后恢复验证通过。完整证据见 docs/migration/studio-frontend-completion/command-recovery-contract.md。

仍需独立runId、持久恢复、命令容量/所有业务应用和完整离开协调。继续F0–F6，不标全量完成。
