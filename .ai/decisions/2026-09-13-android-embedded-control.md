# 安卓内嵌控制与设备独占

日期：2026-09-13。状态：confirmed。来源：用户确认的四图实施计划、正式代码、真实 Mac 设备验证（docs/validation/android-exact-2026-09-13）。

- 手动操作默认在页面内，保留独立 Mac 窗口。两个入口共用单设备控制会话；切换端点递增 generation。旧会话输入和工作流占用期人工写入由服务端拒绝。
- scrcpy 固定 3.3.4。沿用已安装的 scrcpy Java server，通过安装级受控 ADB 转发读取 H264 视频、写控制消息；不下载未知版本。Electron WebCodecs 解码 Annex B H264，无新增前端视频运行库。只在本机鉴权 API 上传输，凭据不写 URL。
- 协议实现依据 [scrcpy develop 文档](https://github.com/Genymobile/scrcpy/blob/v3.3.4/doc/develop.md)、[control_msg.c](https://github.com/Genymobile/scrcpy/blob/v3.3.4/app/src/control_msg.c)、[control_msg.h](https://github.com/Genymobile/scrcpy/blob/v3.3.4/app/src/control_msg.h)。scrcpy 为 Apache-2.0。触摸使用 generic finger ID -2；-1 是鼠标，不能互换。scid 必须是 8 位十六进制。
- 视频流缓存配置与有界 GOP，重新订阅从关键帧解码；帧／队列过大明确断开，不无限积压。旋转后以解码尺寸计算 contain 区域，忽略黑边点击。关闭与失焦释放按键，断线不自动重发操作。
- 命令按会话串行，安装／启动跨设备并发上限为 2。会话心跳 5 秒，30 秒没有使用则回收连接；暂停的工作流不会因页面失联自动继续。
- 安装支持 multipart 文件上传（python-multipart 0.0.20，Apache-2.0）及受控原始 APK 请求。单文件上限 256 MB。设备侧 pm install 写完成标记，未知结果保留 pendingCommand，先核实再释放设备。
- 正式 FastAPI 接口定稿为 `/android/profiles`、`/batches`、`/allocations`、`/sessions`、`/devices/{id}/runs`。后者先按设备筛选再分页，默认 50 条。规格中的较长 URL 是设计草案命名；实际 OpenAPI 为客户端唯一来源。
- 新迁移不改旧分支版本号：0009_merge_android_m5 汇合，0010_android_fleet 增加资源表。工作流父进程持有按设备的运行上下文和锁，VM 创建／预算仍串行。动作边界暂停保留 worker 栈位置，不另建运行来接管。
- 主线后续 `25273d5` 删除旧工作台及工作流实现，与本隔离分支依赖的 M5 冲突。合入路线待用户选择，不覆盖这项新决定。
