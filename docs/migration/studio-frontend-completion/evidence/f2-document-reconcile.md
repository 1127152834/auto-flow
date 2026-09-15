# F2.3 既有证据核销（2026-09-15）

仅核销既有专题、用例及其直接实现；没有重审全库或重跑无变化全量。状态置信度高；未测项目不按源码存在标为通过。此文件是唯一实施台账 F2.3 行的证据附件，不是新计划。

## 可直接继承并关闭的子项

| 能力 ID（沿用 verified-cases.json） | 已实现且已验收内容 | 证据与边界 |
|---|---|---|
| MODULE.edit.*（18规则/组件＋browser-roundtrip） | 创建保留变量和结构、读取最新模块、空模块保存、元数据保留、保存竞态、备份故障、退出保存/放弃/取消、快捷键、模块切换、刷新恢复、主文档历史恢复 | custom-module-edit-protection.md、evidence/f2-custom-module/browser-validation.md；实际浏览器＋Mock，不是真实模块执行 |
| DOCUMENT.connection.*、DOC.empty.save、DOC.save.*、F5.document-new.* | 保存回执/同连接身份、重复提交、保存中编辑、变量空图、列表错误与重试、读取/删除迟到保护、新建草稿保护 | document-connection-validation.md（51专项通过）；正式保存/重开及宿主保护继承 evidence/f5-session-leave/native-ui.md |
| DOCUMENT.import-structure.open.* / merge.* | 重复/空标识、悬空边、容器错误拒绝，未完成与未知旧类型保留，旧格式缺省兜底 | import-structure-validation.md（20新增）；非全部节点schema |
| DOC.drop.*、F5.bundle-import.* | 多文件顺序、密码取消/异常/卸载、跨文档迟到、整包先处理草稿、资源返回期间编辑保护、失败/无效响应 | dropped-workflow-protection.md、bundle-import-protection.md；系统拖拽仍不是原生E2E |
| EDIT.drag.undo / keyboard.move / resize.undo、EDITOR.command.*、EDITOR.alignment.*、VAR.history.* | 手势单次历史、剪贴板普通节点、禁用、排版竞态、下对齐、变量CRUD/改名与历史 | editor-history-validation.md、editor-command-protection.md、alignment-validation.md、variable-editing-validation.md；旧“变量空图不能保存”已被 DOC.empty.save 替代 |
| CAPACITY.500.*、CAPACITY.layout.* | 两视图顺序模型500节点完整往返、末节点编辑撤销、真实浏览器导入保存重开、窄窗口末行可操作 | layout-capacity-validation.md，evidence/f6-layout-capacity/tests.log；模型测试含顺序/循环，不能推导所有复杂块交互通过 |

## 精确剩余（F2.3 内，当前两项）

1. **缺验收：两视图复杂结构及分组/便签/子流程。** 已有 BlockFlowModel 4项、循环回归4项、500节点顺序转换；缺实际 BlockFlowView 插入/重排/条件分支转换、GroupNode/NoteNode 编辑与尺寸/多选移动、子流程定义/重命名引用/复制删除/保存往返的专项。实现入口已有，不能直接判缺实现。
2. **缺验收：自定义模块列表维护与依赖整包全链。** 18项模块编辑已关闭；CustomModuleList 3项只含渲染/空/删除确认出现，customModuleStore 5项只含CRUD缓存；缺删除确认后的失败/取消/引用缺失、导入导出依赖缺失与确认链的直接专项。资源写入错误已有 image-* 专题继承，不重复证明所有图片工具。服务端事务作为后端合同边界，不列为已实现前端原子回滚。

## 2026-09-15 恢复后核销

- `pasteNodes`、`pasteNodesFromClipboard`、`mergeWorkflow` 已在生成新标识后重映射复制集合内部的 `parentId`、`data.subflowGroupId` 和 `errorPolicy.targetId`，并同步边标识。子节点在复制其父容器时保留相对坐标；未复制的外部引用保持原值，不冒充依赖已经一并复制。撤销/重做比较排除 React Flow 的 `selected` 会话状态，节点身份、位置、引用和文档数据断言不变。专项 3 项及关联文档回归通过，见 `evidence/f2-structure-copy/`。
- 七种导出均已通过实际 Toolbar → ExportDialog 入口。JSON、Markdown、加密分享包、依赖整包及三种脚本格式覆盖成功、取消和服务拒绝；加密包使用真实 WebCrypto 往返。三种脚本导出曾在更新失败后继续下载旧服务内容，3 个红例复现后在两个现有 handler 检查 `workflowApi.update` 确认，失败时显示错误、保留草稿且不发导出请求。16 项最终通过，见 `evidence/f2-document-export/`。组件测试的 Blob/anchor 替身不计原生落盘，原生下载仍由 F6 验收。

差异分类：原版入口/模型/组件迁入；文档身份、错误回执与宿主下载属于 AutoFlow 必要适配；500容量、统一草稿保护来自已批准要求。未新增产品设计。原生文件拖拽/剪贴板/导出入口与分发包平台验收仍应由F6记录，不能用组件或Mock通过替代。真实脚本生成与自动化执行仍为后端待实现项。

## 停止时增量（用户定时停止）

已新增 document-export-entry.test.tsx，实际 Toolbar → ExportDialog 点击路径16项，7格式成功、服务拒绝4、取消2已通过；三种脚本“更新失败后不得请求导出旧内容”均失败，复现上述错误处理缺口。真实 Web Crypto 加密/正确密码解密/错误密码拒绝通过；下载只验证 DOM anchor 与 Blob，不是原生文件落盘。最后运行13通过/3失败（6.79秒），保存 evidence/f2-document-export/before.log。早期夹具函数名错误保留 fixture-initial.log；最后红例已排除夹具问题。没有修改 Toolbar/Store。未执行类型/lint；停止后不要将新增测试宣称完成。下一步需在 Toolbar 两个脚本导出handler检查 update 回执，失败返回并保留文档，然后专项回归；依赖完整结构导出仍未补测。
