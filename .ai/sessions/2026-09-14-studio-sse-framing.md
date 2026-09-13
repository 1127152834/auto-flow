# F1 SSE 完整帧与重连补读

2026-09-14，confirmed。共享 SSE 解析器原先在 EOF 派发未以空行终止的尾部事件，导致 Studio 可能将未确认尾部推进为已消费序号。现在只有完整空行提交事件，EOF 丢弃尾部；支持 CR、LF、CRLF，包括跨网络分块的 CRLF；无数据块清空事件类型，空 event 字段使用 message。事件 ID 仍按 SSE 规则保留。

依据 [WHATWG SSE 解析与解释](https://html.spec.whatwg.org/multipage/server-sent-events.html#event-stream-interpretation)，本次未引入另一套事件解析器。

7 个解析器用例覆盖逐字节中文/BOM/三种行分隔、三个尾部截断与空块类型恢复；2 个内存/真实 HTTP 用例验证第一次未确认尾部不回调业务、不推进游标，下一次 afterSeq=0 补读后只派发已确认结果。修复前9失败，相关35通过。全量120文件/1392用例，类型/lint/构建通过。证据 evidence/f1-sse-framing。

本次覆盖 Studio 与共享内核事件读取回归，没有模拟真实浏览器动作。服务重启的 epoch、失效游标状态重建、完整 F1 schema 和正式 Electron 验收仍未完成。
