# M1 正式工作流编辑器设计

- 日期：2026-09-13
- 状态：confirmed；用户明确粘贴并批准完整 M1 执行方案，要求实施。
- 来源：本任务用户的 `PLEASE IMPLEMENT THIS PLAN`，及 brainstorming 中确认的四项产品选择。

## 产品与验收

六类节点：open_page、click_element、input_text、wait_element、get_element_info、screenshot。正式独立窗口内单文档编辑，手动保存和 Ctrl/Cmd+S，允许参数未填或未连线的文档保存并显示问题。顶部工具栏、左侧动作库、中间 React Flow 画布、右侧属性/变量标签，复用当前主题和 shared UI。没有示例节点、模拟运行、执行引擎、录制或 Debug。

画布支持增删、选择、多选、连线、移动、缩放平移、适应视图、复制剪切粘贴。顺序节点单入单出，禁止自连、重复连线和普通环；删除节点同时删除相关连线。撤销覆盖文档、参数、变量和布局修改，拖动合为一次，输入框快捷键优先处理输入。变量支持 string/number/boolean/array/object、普通引用插入、重命名同步引用及被引用变量删除确认。

节点配置保留经实际 WebRPA UI/执行器核对的字段。超时统一 timeoutSeconds=60；空输入文本合法；元素截图缺 selector 标为待完成；空截图路径表示运行产物默认目录；默认输出 element_value/screenshot_path，重名提示但不自动改名。

## 运行与数据边界

同一 renderer 产物用固定 ?view=automation-studio 加载 StudioApp，同一 sidecar；主进程只给登记窗口的主 frame 读上下文与服务恢复权限。主窗口管理和凭据权限保持原边界。

领域统一 workflows。工作流 document 与 layout 分开，SQLite 原子存储，revision 防并发覆盖，不提供产品版本历史。OpenAPI 生成客户端类型。节点默认值与配置元数据由后端目录提供。

API：GET /api/v1/workflows/node-catalog；GET/POST /api/v1/workflows；GET/PUT /api/v1/workflows/{id}。POST 使用稳定文档 ID 防止失败重试重复创建；PUT expectedRevision 原子比较更新。结构损坏拒绝，缺配置/变量值类型未完成以 issues 保存并返回，issues 含 nodeId/path/code/message。

## 数据不丢失规则

新建、打开、关闭 Studio、退出和切工作区统一保存/放弃/取消；保存失败不离开，409 保留草稿并允许另存或重读。保存时继续编辑不能被旧响应清 dirty。同工作区重连保留草稿与撤销，离线仍可本地编辑。切工作区先处理草稿，再冻结，失败回滚保留原文档；退出先保存再停止后端。不提供未保存草稿的崩溃恢复。

## 本次实现裁定

- 布局视口随显式保存写入，但单纯平移/缩放不产生撤销项或未保存提示；节点位置变化正常计入。
- 工作流/节点/边使用稳定 UUID；文档名称允许重复，通过 ID 区分，打开列表显示修改时间。
- 图结构暂按顺序单入单出验证，未来分支/循环在 M3 显式扩展。
- 引用仅识别普通 {name}/${name}，不在编辑器执行表达式。非法数字/列表/对象编辑保留原始文本并标问题。

验收覆盖：六节点保存重启恢复、未完成文档、历史和引用、失败/冲突/保存竞态、每类离开动作、双窗口/服务恢复/工作区隔离、契约/迁移/类型/lint/build及实际 Electron 开发和打包入口。Windows/macOS 按实际平台分别记录，不把模拟测试当 Windows 实机验证。
