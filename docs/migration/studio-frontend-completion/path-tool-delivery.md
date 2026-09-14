# 文件与目录工具回填保护

2026-09-14，F2/F5 有界批次通过。PathInput 与 ImagePathInput 使用既有 system/select-file、select-folder；不实现真实宿主文件对话框。

- 回填必须以成功确认为准，失败响应即便含 path 也不能写入。
- 保留已有包装/平铺成功返回兼容；空字符串或 null 选择按既有 InputPromptDialog 和接口取消合同处理，不能误报路径错误。路径对象/缺失非法结构仍报错。
- 同一控件只允许一个在途选择。字段手动编辑、卸载、文档/节点切换（ConfigPanel 已按文档与节点 key 重挂载）或连接替换后，旧结果失效。
- 取消保留字段；加载结束恢复按钮；服务错误在字段下展示，不仅 console 输出。
- 两模式（文件、目录）和 both 双按钮均验证；不更改输入路径原文，不新增 i18n。

## 验证及取消契约修正

8个通用路径场景实施前全部失败，修复后与图像工具/运行输入共3文件45项通过。284节点面板注册和字段上下文共292项回归通过，类型/lint/构建通过。没有重新运行全量，也没有验证真实宿主文件对话框。

图像工具上一批将 success=true/path='' 作为无效路径，这与既有 InputPromptDialog 的空选择兼容行为冲突。现明确 null 和空字符串为取消；无效类型用数字42独立验证，缺少字段仍失败。原 TOOL.image-path.file-path-missing 台账标为已替代，历史 evidence/f2-image-picker 保留；新增两条取消用例，不隐藏这次合同修正。冻结版取消包装由 api.ts /system/select-file、select-folder 的专属分支处理。

证据见 evidence/f2-path-tool。PathInput 的平铺成功兼容保留，但失败即使有顶层 path 也不回填。11条本批独立台账（8通用、2取消、1非法类型修正）。
