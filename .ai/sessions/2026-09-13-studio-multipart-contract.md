# Studio HTTP 上传与场景装配

- 日期：2026-09-13；状态：confirmed 局部完成，F1 未关闭。
- 依据：真实本地 HTTP/SSE 夹具与同组 memory 测试。
- 保留 HTTP 请求头和二进制 body；Request/URL 输入一致，JSON结构失败和损坏multipart明确400。
- 70,000字节上传在两种传输逐字节通过；Node/jsdom File realm测试设施已修复。
- Mock按钮迁出 StudioApp，保留在显式前端预览入口，不删除用户要求的测试工具。
- 全量90文件1,097项通过；真实后台能力未因此实现。默认transportMock和正式服务schema仍是未完项。
