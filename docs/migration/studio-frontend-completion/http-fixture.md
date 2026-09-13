# 现有协议的 HTTP/SSE 夹具

日期：2026-09-13。状态：已实现局部协议验证；F1 完整合同尚未冻结。

位置：apps/desktop/src/renderer/domains/workflows/tests/fixtures/http-studio-server.ts。测试时绑定 127.0.0.1 的随机端口，将请求交给同一个状态化 Mock；不代理外网，不执行浏览器动作，不读用户工作区。测试结束关闭响应流和服务器连接。

transport-parity.test.ts 使用同一组断言分别运行 memory/http：

| ID（分别加 .memory/.http） | 数据和操作 | 界面/协议预期 | 状态断言 |
|---|---|---|---|
| HTTP-DOC-001 | input_text 文本重复 18,000 次“中文😀”，保存/读取，注入 507，重读；再发送损坏 JSON 和未知地址 | 本测试不挂载 UI；成功/507/400/501 状态真实返回 | 内容无截断，失败不覆盖旧文档 |
| HTTP-CMD-001 | 相同 commandId 重复相同内容，再改 enabled | 返回相同命令结果，改内容为 409 | 命令身份不变 |
| HTTP-SSE-001 | 中文/emoji 日志，读取 seq1，取消，断线期间发 seq2，从 afterSeq1 续读 | HTTP 服务按 7 字节写 SSE，中文完整，续读从 2 开始 | 前一个流取消，事件不重放 1 |
| HTTP-CLIENT-001 | 正式 StudioEventClient 接收一次日志，断流期间再发一条 | 自动续连并补读两条，未制造 completed | 无重复 listener 调用 |

运行：npm test --workspace @autoflow/desktop -- src/renderer/domains/workflows/tests/transport-parity.test.ts。8 项通过（4 个场景×2 个传输），证据记录到本批全量测试输出。

目前只验证 JSON 命令和 SSE；multipart、鉴权/权限、启动响应丢失查询、真实工作区、全部 API 语义、持久历史及正式 Electron 主链未因此通过。服务器仅为测试夹具，不能作为生产后端。
