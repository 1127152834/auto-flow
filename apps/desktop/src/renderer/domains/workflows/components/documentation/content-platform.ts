// Source: WebRPA@5ccb900e, components/workflow/documentation/content-platform.ts; see SOURCE.md for license and adaptation boundaries.
export const platformGuideContent = `# 平台能力：导出与配置

> 桌面正式入口连接本机后端。运行前请配置节点所需资源，执行结果以当前运行日志和实际产物为准。

本页说明正式桌面工作台的导出、凭据、远程存储与留存入口。它们连接当前工作区的本机服务。

## 工作流导出

从工具栏打开导出对话框，选择格式并提交。界面提供 JSON、Markdown、Playwright Python、Selenium Python、Playwright JavaScript、加密分享包和含依赖整包的选项。

JSON 用于保存工作流配置，Markdown 用于阅读流程。脚本和整包由本机服务生成。导出成功表示文件已生成；独立执行仍需对应运行环境和资源，不等同原流程全部能力已在目标格式中验收。

## 凭据配置

在“全局配置 → 凭据库”中管理名称、说明和字段。编辑已有凭据时，按表单说明处理留空字段；提交失败时检查提示后重试。

节点中的凭据引用格式为 \`{{cred:名称}}\` 或 \`{{cred:名称.字段名}}\`。秘密保存在系统凭据存储中，按稳定工作区身份隔离。历史无工作区归属的凭据需要重新录入；系统不会自动读取另一工作区同名秘密。

## 远程存储配置

“全局配置 → 存储”保留 WebDAV 设置，可填写地址、远程目录和连接信息，保存或测试连接。连接测试会访问配置的真实服务；测试失败会显示错误，远程文件读写还取决于目录权限。

## 留存配置

“全局配置 → 留存清理”提供保留天数、容量限制、占用查询及清理请求入口。清理会按当前留存规则处理本工作区的运行记录与产物；执行前核对设置和占用信息。

## 相关文档

- [自定义模块](custom-modules-guide)
- [选择器完全指南](selector-guide)
- [自动化浏览器](browser-guide)
`
