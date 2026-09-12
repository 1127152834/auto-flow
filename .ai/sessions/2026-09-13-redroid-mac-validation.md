# redroid Mac 验证交接

- 日期：2026-09-13。
- 状态：confirmed。
- 来源：用户明确“现在只需要在 Mac 上进行测试”；实际本机 VM、Docker、Android、API、CUA 与自动测试。

## 已完成

- 独立 Demo 增加 Apple Silicon → Lima VZ → Ubuntu 24.04 ARM64 → Docker Engine 路线，Mac 入口 127.0.0.1:8081；原 Docker Desktop context 保持不变。
- 真实 Android 13、三实例数据与端口隔离、Python 批量流程及清理、普通/Magisk APK 安装启动、无效 APK 失败、界面坐标及输入已实测。
- 固定 redroid-script 构建 Magisk 产物；容器 UID、VM 宿主 ADB root 与 Magisk su 分别记录。运行版本实际为 30.6:MAGISK:R，下载文件名为 v30.7。
- 修复 ARM 平台/镜像匹配、启动探针过早报错、Magisk 只读 rootfs 的 Docker archive 传输失败、误调用 AOSP su；增加有限失败回归。
- 保留两台供用户体验：普通版与 Magisk 版；其他本次测试设备按归属清理。完整证据见 [MAC_TEST.md](../../reference/redroid-demo/MAC_TEST.md)。

## 边界

- 早期“Mac 只能查看诊断，真实 Android/Magisk 未验证”结论 superseded；现在在 Mac 本机的独立 Linux VM 已实测。
- 应用级 root 仍未知；不能用 ADB/shell UID0 或 Notes 安装成功替代。Windows/WSL 未测，本轮不等待 Windows 节点。
- 摄像头、环境伪装、视频、集群和正式 AutoFlow 接入继续属于后续范围；不修改主应用架构。
