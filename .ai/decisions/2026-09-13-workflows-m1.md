# 工作流编排 M1 边界

- 日期：2026-09-13
- 状态：confirmed；来源为用户明确批准并要求实施的 M1 方案。
- 验证：后端契约/数据库测试、前端组件/交互测试、macOS 真实 Electron 开发与打包入口；详见 [验收记录](../../docs/migration/automation-studio-m1-validation.md)。

正式领域统一 `workflows`，位于现有 backend domain/application、HTTP adapter、SQLite infrastructure 与 desktop renderer/domains；不新增 sidecar、项目管理或执行引擎。前端沿用 components/hooks/pages/tests 目录，使用 @xyflow/react 和现有 shared UI。

文档与编辑布局分开表示，在工作区原 SQLite 的单表事务中保存。服务生成 revision 和修改时间；revision 是并发条件，不是用户可管理的版本。手动保存、稳定 UUID、允许未完成配置，格式损坏拒绝写入。OpenAPI 生成前端类型，节点默认值唯一来源是后端目录。

同一个 renderer 产物以固定 query 选择独立 StudioApp；窗口分别管理 UI 状态，共用 sidecar。新建、打开、关闭、退出、换目录先处理草稿，成功保存才继续；退出先于 shutdown，切换成功才替换工作区文档。同工作区服务重连保留本地历史；失败回滚保留原稿。运行上下文仅授权登记窗口主 frame。

六节点的超时统一 timeoutSeconds=60 秒；旧 timeout/waitTimeout 的 UI 与执行器默认值有冲突，不照搬。M1 只实现编辑，不执行浏览器节点、表达式或截图；不接入录制、Debug、产品版本管理或 Windows 控制。完整字段映射见验收记录。

旧空白工作台已由正式编辑器替代。早期 automation 原型和研究资料继续作为历史，不得作为正式运行入口；后续实施以 [M1 规格](../../docs/superpowers/specs/2026-09-13-automation-studio-m1-design.md) 和后续用户批准的里程碑为准。
