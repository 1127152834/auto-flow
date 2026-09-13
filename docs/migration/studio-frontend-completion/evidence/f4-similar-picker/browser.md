# 相似元素预览 UI 验收

2026-09-14 Asia/Shanghai，独立 http://localhost:5175/studio.html，IAB tab7，CUA真实点击。服务为明确标记的内存Mock，不操作真实网页。

- 06:30:58 打开已有F4拾取写回验收，保留单节点#submit。
- 06:31:16 属性面板可视化选择→启动选择器；开发场景选择「拾取：四个相似元素」。
- 06:31:27 展示审查弹窗：4个、索引1–4、.item:nth-child({index})。
- 输入变量名rowIndex→06:31:33确认使用，节点改为.item:nth-child({rowIndex})，全局变量增至1。
- 点击画布后Ctrl+Z：节点回#submit，变量回0；Ctrl+Shift+Z：两者一起恢复。
- 命名F4相似元素验收→Cmd+S，保存时间06:31:59.266。变量面板rowIndex=1，number。
- 刷新页面→文件菜单打开F4相似元素验收（文件列表15项，原F4拾取写回验收仍保留）。06:33:05重开，节点模式及rowIndex=1 number恢复。

没有直接修改Store完成以上操作；不计真实相似元素识别、iframe或正式Electron通过。
