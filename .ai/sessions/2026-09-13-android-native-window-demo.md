# 安卓原生窗口小闭环

- 日期：2026-09-13。
- 状态：用户授权的 Mac 有界验证已完成；鼠标自动化重连稳定性仍待定位。
- 用户已明确选择“页面监控 + 原生窗口操作”，原型中的网页内触控不再是当前优先路线。正式架构、批量租约、暂停恢复没有新增实施授权。
- 交付：`reference/redroid-demo/scripts/native_monitor.py`、`start-native-mac.sh`、独立 React `/native` 页面、测试及 [Mac 原生验证](../../reference/redroid-demo/NATIVE_MAC_TEST.md)。当前入口 127.0.0.1:8082/native。
- 实测：页面点击打开真实 redroid；原生窗口点击/滑动、Notes 输入；关窗仅清理连接；重开内容保留；已停止 Android 可由页面启动并出画面，重启后 Notes 文字仍在。
- 固定 scrcpy 3.3.4 / SDL 2.32.8 官方便携包并校验 SHA-256。4.1/SDL3 首轮合成鼠标坐标异常，3.3.4 完成首轮闭环但重连也有偶发异常；不能把固定版本视为彻底修复，需对照真实鼠标与 CUA 合成事件。
- 校验来源：CUA 原生截图、Demo API 状态、专用 SSH listener 关闭断言；4 项新增 Python 检查、28 项前端测试、类型检查、构建及脚本语法。无模拟数据，无正式工作流并发声明。
- 保留现有三台 Android 实例；只向旧测试 Notes 追加一行验证文本。其他工作流开发文件未修改。
