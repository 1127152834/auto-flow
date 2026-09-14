# 图像路径实际 UI 验证

2026-09-14，专用 IAB 标签7，http://localhost:5175/studio.html。
在测试草稿临时拖入“图像识别” ai_vision；图片来源选“图片URL”；点击“选择图像资源”，看到两个既有测试图片。选择 studio-image-preview-fixture.png 后，图片地址回填其 data:image/png;base64 路径，列表关闭。
按 Cmd+Z，再选该节点，图片 URL 模式保留但路径为空。按 Cmd+Shift+Z，再选该节点，恢复同一 data:image 路径。
撤销此次应用、来源修改和临时节点，画布回到两个固定等待、0个变量；12:13:21 保存到原专用测试文件 F3 暂停身份与单步确认.json。未运行 AI、未调用真实文件对话框、未修改资源库文件。操作使用实际拖拽、点击和快捷键，没有修改 Store 或调用内部函数。
