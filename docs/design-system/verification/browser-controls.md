# T8 浏览器和内核控件迁移

日期：2026-09-12；状态：implemented，自动与本机页面检查通过。

浏览器的筛选、视口、色彩、人类行为、内核、发布通道和代理选择迁入自绘Select；语言/时区/UA用Combobox保留服务端目录及手动输入切换。FormField显式绑定ARIA，错误聚焦从查询name（会命中隐藏表单节点）改为RHF ref；viewport仍用专有定位标记。高级说明复用Disclosure，内核安装进度复用Progress。没有改后端JSON/API/hooks/schema。

新增环境目录搜索与手动焦点测试先失败；迁移后profiles/kernels 20文件111测试通过，包括通道回落Stable、代理互斥引用清空、保留自定义UA与422跨页签聚焦。测试改为对真实role=option点击，不使用原生selectOptions；业务payload断言保留。typecheck/lint通过，Electron16组共享/真实表单回归通过（browser-controls/）。无真实License登录或远端下载验收，未声称通过。
