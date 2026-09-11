# 模型管理设计：旧能力证据与布局交互对齐

- 日期：2026-09-12
- 状态：confirmed（用户要求沿用旧布局及旧交互、源码和现场取证事实）；proposed（修订原型待确认）。
- 验证方式：主任务与只读子任务独立审阅旧前后端源码；后续按用户要求构建并打开旧 Electron 应用，实际核对页面与弹窗。现场操作范围见[取证清单](../../docs/prototype/model-management/reference/README.md)，不证明各外部服务当前兼容性。
- 旧源码根目录：`/Users/zhangtiancheng/Documents/projects/browser-automation/autoflow-desktop`。

## 已确认的迁移边界

| 结论 | 源码依据（相对旧源码根目录） |
| --- | --- |
| 接入三步为预设、连接配置、模型选择；最终连接再次发现模型，并原子保存 | `src/renderer/features/models/ProviderWizard.tsx`；`backend/src/autoflow/api.py` 的供应商接入处理 |
| 供应商持久配置是名称、预设、协议、地址、密钥、启用、描述 | `backend/src/autoflow/schemas.py` 的供应商 schema |
| Ollama/自定义兼容预设允许可选密钥 | `src/renderer/features/models/provider-catalog.ts` |
| 模型配置仅 ID、名称、标签、可空上下文长度、启用、描述；编辑 ID 只读 | `src/renderer/features/models/ModelEditor.tsx`；`backend/src/autoflow/schemas.py` |
| 连接测试检查模型目录；持久供应商检查保存时间、单次耗时与结果 | `src/renderer/features/models/model-api.ts`；`backend/src/autoflow/model_provider_service.py`；`backend/src/autoflow/api.py` |
| 模型测试实际发起固定生成请求，最大输出 16 tokens，输出/推理预览截断为 240/2000 字符 | `backend/src/autoflow/model_provider_service.py` |
| 模型测试结果不持久化为健康状态 | `src/renderer/pages/ModelsPage.tsx`；`backend/src/autoflow/schemas.py` |
| 停用供应商移除其全部模型的业务可调用选项；停用单个模型只排除该模型 | `backend/src/autoflow/api.py` 的可调用模型查询；`src/renderer/pages/ModelsPage.tsx` |
| 删除供应商级联删除本地模型；删除模型只影响本地；同供应商模型 ID 唯一 | `backend/src/autoflow/models.py`；`backend/src/autoflow/api.py`；`backend/tests/test_models.py`（仅阅读，未运行） |
| 发现模型是刷新候选供选择添加，不是自动同步本地目录 | `src/renderer/features/models/ModelEditor.tsx`；`src/renderer/pages/ModelsPage.tsx` |
| 无采样参数编辑、价格、余额、额度、吞吐、成功率、长期模型健康、默认模型和工作流引用计数能力 | 上述页面、schema、service；`backend/tests/test_model_editor_simplification.py`（仅阅读，未运行） |

## 后续用户纠正与当前基准

- 用户明确要求“和旧项目一样”“交互也要做的一样”。此前三个无侧栏布局与“等待选择 1/2/3”的状态均为 superseded，不再作为候选。
- 旧主页面是 278px 供应商左栏和当前供应商右侧详情；模型编辑是约 285px 左侧摘要/测试和右侧字段的 split Modal。供应商侧栏是明确的业务切换入口，必须保留。
- 新应用的顶部全局导航保持既定方向，不将旧项目的全局项目/内核导航一起迁回。
- 新增供应商保持三步，步骤不可点击跳转；编辑直接进入连接信息。连接字段未改用“保存修改”，已改用“测试并保存”。
- 模型编辑保持字段顺序、标签提交规则、默认值折叠说明、单次测试状态和叠加移除确认。移除确认取消后回到未关闭的原编辑窗。
- 旧页面没有模型管理 Toast，也没有未保存关闭确认。此前额外引入的 Toast、2.6 秒消失和未保存确认均为 superseded。
- 连接字段修改后的验证更新由旧实现支持，不再把它列为拟增加能力；密钥只返回配置标记仍是可在后端规格阶段讨论的内部改进，不能据此改变现有可见交互。
- 当前[原型及交互说明](../../docs/prototype/model-management/model-management-interactions.md)包含主页面、供应商流程和模型流程三张同一设计的图片，等待原型确认。正式规格、API 契约、实施计划和业务实现尚未进入本轮范围。

## 当前验证

- 旧源码 `electron-vite build` 成功，使用真实 Electron 页面进行现场取证；旧开发服务遇到 5173 端口占用后，使用本地构建打开，未修改旧代码或占用该端口的其他服务。
- 八张 Computer Use 原始截图已保存，密钥输入保持遮蔽；没有输出或持久记录实际密钥。
- 本地模型目录夹具直接读取成功，但应用连接预览返回失败；根因未定位，成功进入第三步仍只有源码证据。夹具已停止，临时接入表单已取消。
- 生成主页面实际为 1487×1058；两张流程画板实际为 1448×1086；不按提示词请求尺寸宣称实际分辨率。
- 仅修改原型图片、文档及 AI 记录；不包含新项目业务代码。不将源码阅读或本地构建成功等同于供应商接口与迁移功能验收通过。
