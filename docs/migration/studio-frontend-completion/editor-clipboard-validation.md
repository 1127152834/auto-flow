# 三种代码编辑器复制操作验收

2026-09-14，confirmed（F2有界交互修复）。JavaScript、页面注入JavaScript和Python复用CodeCopyButton；保留原按钮样式。原生writeText完成后才显示“已复制”，进行中禁用重复操作，权限拒绝或剪贴板能力缺失显示中文错误并可重试。关闭/重开或代码变化后旧回执失效，卸载取消提示定时器；复制不修改工作流或执行代码。

最初测试夹具未定义clipboard导致9项初始化失败，修正夹具后9项行为测试仍失败并暴露3个未处理拒绝。实现后15项新增通过，联合补全和JS执行25项通过。TypeScript首次发现测试使用不支持的exact选项，改用等价锚定名称后通过；ESLint及renderer/main/preload构建通过。最新全量基线157文件1884项在本文件新增前已收集，不能把15项加总当作新全量执行。

15项按三个编辑器×失败重试/关闭重开/定时器释放/无能力/代码变化展开，见verified-cases.json和code-editor-clipboard.test.tsx。浏览器真实按钮回执通过，但工具虚拟剪贴板为空，不能核对原生剪贴板内容，详见evidence/f2-editor-clipboard/browser-ui.md。该内容传输E2E与正式宿主仍标未验收，不拿组件替身冒充系统验证。
