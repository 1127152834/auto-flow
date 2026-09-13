# Studio 前端源码与 Mock 迁入

- 日期：2026-09-13；状态：implemented；来源：用户明确授权前端优先，接口可 Mock。
- 从冻结 WebRPA 迁入 275 项源文件调用闭包，保留原编辑器、两种视图、Store、表单、录制/Debug/日志和助手组件；当前范围内动作库 472 项。来源清单/原许可保留。
- 同 renderer 构建增加 studio.html，入口为正式单窗口控制器。请求统一 studioFetch，事件改成 HTTP 命令/SSE，Mock 本地存储与内存会话显式标注。
- 修复实际发现的空默认目录、撤销历史、导入历史、保存快照比对、重连假完成和节点失败双重完成事件。增加 Electron 关闭确认与先关 Studio 后关 sidecar 顺序。
- 通过 474 前端/宿主测试、类型/lint/build、12 脚本/目录测试、OpenAPI 一致性；浏览器实点保存/打开/录制生成/断点单步，macOS arm64 正式构建 HTML 新窗口实际打开并正常退出。细节以 docs/migration/studio-frontend-mock-validation.md 为准。
- 未完成真实后端、工作区/资源锁、真实浏览器与原生工具、全部源功能逐项对照、分发包及 Intel/Windows；不勾选 R1–R8 真实执行验收。
- 未覆盖用户其他模型/UI/知识记录改动。未改后端表、旧迁移或旧工作区数据。
