// Source: WebRPA@5ccb900e, components/workflow/documentation/content-platform.ts; see SOURCE.md for license and adaptation boundaries.
export const platformGuideContent = `# 平台能力：导出与配置

> 当前 Studio 教学范围为保留节点及前端配置交互。Mock 用于交互演示，不执行真实网页、模型或系统操作；文中的执行行为需正式后端支持。

本页说明 AutoFlow Studio 当前保留的前端入口。当前 Studio 使用 Mock 服务；外部存储、凭据注入、脚本生成和清理请求的演示结果，不代表正式后端已完成相应操作。

## 工作流导出

从工具栏打开导出对话框，选择格式并提交。界面提供 JSON、Markdown、Playwright Python、Selenium Python、Playwright JavaScript、加密分享包和含依赖整包的选项。

JSON 用于保存工作流配置，Markdown 用于阅读流程。脚本和整包等服务生成内容，应检查返回结果及错误提示；不能将 Mock 文件当作已验证可独立执行的程序。

## 凭据配置

在“全局配置 → 凭据库”中管理名称、说明和字段。编辑已有凭据时，按表单说明处理留空字段；提交失败时检查提示后重试。

节点中的凭据引用格式为 \`{{cred:名称}}\` 或 \`{{cred:名称.字段名}}\`。实际解密与运行时注入依赖正式服务。当前 Mock 配置不应用于保存真实账号口令。

## 远程存储配置

“全局配置 → 存储”保留 WebDAV 设置，可填写地址、远程目录和连接信息，保存或测试连接。Mock 的测试响应不证明远程目录可以读写。

## 留存配置

“全局配置 → 留存清理”提供保留天数、容量限制、占用查询及清理请求入口。当前 Mock 不清理真实磁盘文件。

## 相关文档

- [自定义模块](custom-modules-guide)
- [选择器完全指南](selector-guide)
- [自动化浏览器](browser-guide)
`
