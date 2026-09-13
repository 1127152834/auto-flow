# 多行输入保存重开：浏览器 UI 证据

2026-09-14，独立 localhost:5175/studio.html，IAB tab 7，Mock 服务。

通过文件菜单与真实文件选择器导入 browser-fixture.json；选中 #input 节点，在可访问文本区域输入：

```text
第一行
第二行 {name} ${name}
```

03:06:04 Cmd+S 显示“工作流已保存: F2 多行输入验收.json”，工具栏空闲。刷新后通过菜单“打开”选择此文档，03:06:28 显示已打开；展开输入节点配置，AX 文本区域仍为上述两行完整文字，元素选择器仍为 #input，清空选项为开启。

全链使用 UI 操作，未直接写 Store；这是内存 Mock 持久化前端闭环，不是网页自动输入或正式 Electron E2E。
