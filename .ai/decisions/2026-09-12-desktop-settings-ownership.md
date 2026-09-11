# 桌面设置与运行信息的所有权

- 日期：2026-09-12；状态：confirmed。
- 来源：用户授权自主实施设置/总览；已实现源码和 `docs/migration/settings-dashboard-status.md` 的验证。

本机 UI 偏好、工作区根、原生目录与保存选择器、服务切换和诊断落盘归 Electron main；统一 IPC 类型在 `apps/desktop/src/shared/settings.ts`。Python 仅提供资源聚合、运行信息和执行器占用/暂停门控；renderer 不持有任意文件写入能力。

切换采用预检、暂停变更、停止旧服务、验证目标服务、提交路径，失败回退。对外 sidecar 状态在提交完成前保持 starting，避免 UI 将新 token 与旧工作区混合。每次启动创建新 supervisor，避免旧进程退出事件覆盖新实例。

ApiProvider 按连接替换缓存，外层 React key 仅绑定实际工作区；同目录重连不卸载未保存表单，换工作区重置领域树。离线状态保留内容但禁止操作，设置仍可访问。

诊断导出用白名单 JSON 替代原型 ZIP，不增加压缩依赖；可选日志限定当前会话生命周期事件，完整预览与落盘一致。Windows 本机验证仍待专用环境，不能由 macOS 检查代替。
