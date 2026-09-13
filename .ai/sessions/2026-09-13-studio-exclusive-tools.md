# Studio 专属工具依赖清理

日期：2026-09-13；状态：implemented，F0 总体验收未关闭。

通过整个 apps/desktop/src 的符号引用搜索确认，32 个 Desktop 配置导出没有调用方。保留混合文件其余代码，删除这 32 个导出；删除无调用入口的 phone-coordinate-input 以及 phoneApi、desktopRecorderApi、desktopPickerApi。来源记录在 excluded-source-files/symbols.json。保留网页选择器、图片资源、共享坐标控件及用户数据。

验证：完整前端 91 文件/1,107 用例通过，包含全部 284 面板注册；lint 首轮发现残留 import，修正后复跑。最终检查日志随提交记录。继续 F0–F6，不能以删除无用代码代替功能实现。
