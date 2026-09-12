# T6–T7 共享浮层与数据反馈

日期：2026-09-12；状态：implemented / G1自动验证通过，人工平台矩阵仍pending。

复用既有Modal焦点返回与busy规则，Drawer仅更换同一外框的侧边布局；Tooltip、Dropdown挂载OverlayHost，Tabs默认手动激活。新增语义Table、Pagination、Alert、EmptyState、Skeleton、Progress，Badge状态色和Toaster关闭控件/定时器清理统一。新增OverlayCases/DataFeedbackCases展示页。

先执行Drawer/Tabs/Tooltip与分页/反馈测试，缺少实现及自动页签激活产生红灯；实现后shared 27文件85测试、typecheck/lint/build通过。Electron 16组检查通过，包括Drawer中菜单打开Modal、逐层返回、Tooltip键盘与Escape、Toast关闭，以及既有G0、真实浏览器表单与设置诊断回归。证据位于g1/；此阶段尚未迁移领域Select，不声称真实页面已使用全部新控件。

没有新增依赖，没有修改后端/接口/数据。Window/读屏/实体IME仍待最终人工矩阵。后续按T8–T12接入领域并退出旧入口。
