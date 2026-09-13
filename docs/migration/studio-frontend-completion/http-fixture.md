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

## F1 传输跟进

- HTTP 夹具现在保留原请求头和二进制 body，以 Request 交给相同处理器；不再先将上传字节解码为 UTF-8。
- mockRequest 支持 Request/URL 两种输入、JSON 对象、multipart 与 Request.signal。主动取消不会显示连接故障。
- HTTP-UPLOAD-001.memory/http：构造 70,000 字节（含 0–255）、中文文件名的 multipart；上传后逐字节核对 dataUrl、size、name；损坏 boundary 返回400且库不变。此用例验证二进制协议，不声称该测试二进制是可解码图片。
- HTTP 解析使用 Node Web API File；测试显式替换 jsdom 的不同 File realm。首次原生解析失败来自测试环境类型混用，修复后没有放宽字节断言。
- 现有六组协议分别运行 memory/http，共12项通过；全量90文件、1,097项通过。鉴权、全量合同和原生Electron仍待后续。
- Mock 场景控制迁到 workflows/development/StudioMockTools，由 studio.tsx 明确装配；StudioApp 不再直接导入 Mock 服务。当前 transport 的默认 Mock 和固定服务地址仍需后续正式连接装配，不宣称生产链路已完成切换。
