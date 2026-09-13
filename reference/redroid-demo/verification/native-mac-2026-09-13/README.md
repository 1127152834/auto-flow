# 原生窗口验证证据

- 日期：2026-09-13；状态：小闭环 confirmed，输入稳定性待定位。
- [01-native-input.jpg](01-native-input.jpg)：在原生 scrcpy 窗口中输入完整测试文字。
- [02-monitor-after-close.jpg](02-monitor-after-close.jpg)：关闭原生窗口后，监控页显示实例仍就绪。
- [03-reopened-data.jpg](03-reopened-data.jpg)：从页面重新连接，原文字保留。
- [04-after-android-restart.jpg](04-after-android-restart.jpg)：停止并重新启动 Android 后，再次打开 Notes 的数据证据。
- [result.json](result.json)：实际实例状态、窗口状态、专用隧道释放检查和客户端版本。
- 限制、失败对照及复现命令见 [NATIVE_MAC_TEST.md](../../NATIVE_MAC_TEST.md)。截图来自 CUA 的 Mac 原生窗口/浏览器截图，没有使用生成图冒充运行证据。
