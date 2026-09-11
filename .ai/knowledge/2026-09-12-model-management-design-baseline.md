# 模型管理设计：旧能力证据与候选状态

- 日期：2026-09-12
- 状态：confirmed（以下旧源码事实）；proposed（布局及交互改进）
- 验证方式：主任务与只读子任务独立审阅旧前后端源码；未启动旧页面、未执行供应商请求，本轮不证明各外部服务当前兼容性。
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

## 本轮产物与未决项

- [布局及交互草案](../../docs/prototype/model-management/model-management-interactions.md)记录三张独立图片，显示顺序固定为布局 1/2/3。
- 使用已确认的暖灰、黏土棕视觉系统，没有模块左侧栏或永久右侧栏。
- 用户尚未选择模型管理布局；不要从之前其他模块的“第三版”选择推断本模块也选择第三版。
- 三张图由内置 imagegen 生成，附带代理管理原图作视觉参考；完整提示词保存在模块目录。
- 生成示例数据未经真实 API 验证。布局 3 的行选择框是待移除生成偏差，不构成批量功能授权。
- 详细弹窗画板、正式规格、API 契约和实施计划尚未完成。选择布局后继续设计，不直接进入页面开发。
- 密钥只返回配置标记、连接字段变更后旧检查状态失效、未保存确认等为拟改进项，需要在正式契约中落实，不能宣称旧系统已支持。

## 本轮验证

- 三张 PNG 均为工具原始 1487×1058 输出，目标视口在提示词中为 1440×1024；不重新采样、不覆盖生成原件。
- 本轮仅新增/修改原型文档和图片，不涉及业务代码，不需要运行应用测试或构建。
