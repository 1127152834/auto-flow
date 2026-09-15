# F6 正式 Electron 原生 UI 验收

日期：2026-09-15

平台：macOS arm64

入口：仓库 Electron 主进程 + `ELECTRON_RENDERER_URL` 开发渲染入口
数据：独立临时 `user-data-dir`，没有读取或改写用户正式工作区

## 验收结果

| ID | 用户操作 | 可见结果 | 结论 |
|---|---|---|---|
| F6-NATIVE-001 | 启动正式 Electron 主进程 | 主窗口显示“本地服务正常” | 通过 |
| F6-NATIVE-002 | 在“总览”真实点击“工作流工作台” | 打开独立“工作流工作台 · AutoFlow”窗口，URL 带 `view=automation-studio` | 通过 |
| F6-NATIVE-003 | 查看动作库及浏览器配置 | 动作库显示 227；运行浏览器配置只显示共享 CloakBrowser Profile 入口；界面为中文单语言 | 通过 |
| F6-NATIVE-004 | 在画布空白处右键，点击“快速选择模块 → 打开网页” | 画布出现 `open_page`，模块数量变为 1，右侧出现专用配置面板 | 通过 |
| F6-NATIVE-005 | 在 URL 输入框输入 `https://example.com`，按 `Cmd+S` 并确认覆盖 | 日志显示“工作流已保存: F6 正式窗口验收.json” | 通过 |
| F6-NATIVE-006 | 选中节点，按 `Cmd+C`、`Cmd+V` | 模块数量由 1 变为 2；日志显示复制和粘贴各一次 | 通过 |
| F6-NATIVE-007 | 通过“文件操作 → 导出 → JSON 格式 → 立即导出”，在 macOS 原生保存面板点击保存 | 下载目录生成 `F6_正式窗口验收.json`；解析后名称正确、节点数 2 | 通过 |
| F6-NATIVE-008 | 关闭 Studio，确认主窗口仍在；再由主窗口真实点击打开 Studio | 新 Studio 正常打开，初始为空文档 | 通过 |
| F6-NATIVE-009 | 点击“打开”，在本地工作流列表点击 `F6 正式窗口验收` | 名称恢复、节点数恢复为 2、两个 URL 均为 `https://example.com` | 通过 |
| F6-NATIVE-010 | 关闭主窗口 | Studio 保持可用，已打开文档及共享 sidecar 不受影响 | 通过 |

## 原生文件证据

导出文件：`/Users/zhangtiancheng/Downloads/F6_正式窗口验收.json`

解析结果：

```json
{"name":"F6 正式窗口验收","nodeCount":2,"edgeCount":0}
```

## 边界

- 顶部明确显示“Mock 接口”，本记录只证明正式 Electron 中的前端交互、宿主桥接、原生保存面板和服务消费，不证明真实网页执行。
- AI 小助手的 Mock 回复明确表示未调用真实模型、未自动修改工作流；因此不把这次对话计为 AI 执行通过。
- 当前用户正式数据目录的数据库包含本分支不存在的 Alembic 修订 `0010_android_fleet`。本次使用独立临时数据目录完成验收，没有删除、降级或改写用户数据。该兼容问题作为集成环境阻塞单列，不影响当前前端主链结论。
- macOS Intel 与 Windows 没有可用实机，本记录不标通过。
