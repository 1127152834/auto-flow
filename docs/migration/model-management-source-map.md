# 模型管理源码复用记录

- 日期：2026-09-12
- 状态：confirmed；记录本分支已实现的源码参考与资源复用。
- 用户授权：可直接参考旧项目代码，保持模型管理旧布局与交互。
- 来源仓库：`/Users/zhangtiancheng/Documents/projects/browser-automation/autoflow-desktop`
- 来源 HEAD：`324748abe7095f085b4ffb9467be9cb5c8851a5c`；下表哈希针对读取时工作树。
- 本分支：`codex/model-management`，基点 `ad08bdb`。

| 旧相对路径 | SHA-256 | 新相对路径 | 复用与改动 |
| --- | --- | --- | --- |
| `src/renderer/components/ui/modal.tsx` | `4cb78b1a8adc88266b0ecbd2304f5be0043242132c2ee1937f5d15e8faaae844` | `apps/desktop/src/renderer/shared/components/Modal.tsx` | 复用焦点归还算法；改为共享Radix/Tailwind shell |
| `backend/src/autoflow/schemas.py` | `1672cff4e1a58302a7a3f5cad177bc34e1d9ab01e1f7689aa183be4b8d54e20a` | `apps/backend/src/autoflow/adapters/http/model_schemas.py` | 复用非秘密字段/长度/标签；分离读写、严格上下文、writeOnly Key |
| `backend/src/autoflow/model_provider_service.py` | `19e156093ee792dfd8d298fa2e0204fbbe625786cea01838245351cc86a28b4e` | `apps/backend/src/autoflow/providers/model/http.py` | 复用协议/解析思路；去ORM、无空Bearer/环境代理/重定向，按流读取并限制响应大小 |
| `backend/tests/test_model_provider_service.py` | `6b9be61805a68b5d703a0ce7486e941b90b3c2a6a16796c84e4068d4fc9d6194` | `apps/backend/tests/unit/test_model_provider.py` | 复用协议场景；增加URL/secret/上限验证 |
| `src/renderer/assets/model-providers/alibabacloud.svg` | `c8b18c07ebc462395f26cea2795ef622ec4c59c5cd5a9b6a3fd9938e0e7650e4` | `apps/desktop/src/renderer/domains/models/assets/provider-icons.ts` | 原字节编码为 data URL，供 Qwen 使用 |
| `src/renderer/assets/model-providers/anthropic.svg` | `1cc599f6ebce2016dc388cf84e54a52c6b13487655c7e243554d654c7bce1882` | `apps/desktop/src/renderer/domains/models/assets/provider-icons.ts` | 原字节编码为 data URL |
| `src/renderer/assets/model-providers/deepseek.svg` | `7a55a0a7391d116eba7d32807d6838478f9209f6034612941e74fbb14934e2ef` | `apps/desktop/src/renderer/domains/models/assets/provider-icons.ts` | 原字节编码为 data URL |
| `src/renderer/assets/model-providers/googlegemini.svg` | `a6228d8846040401e941a39ed17459785e8324dbb7b870ce84233c9b3e9863a0` | `apps/desktop/src/renderer/domains/models/assets/provider-icons.ts` | 原字节编码为 data URL |
| `src/renderer/assets/model-providers/moonshot.ico` | `df91c1ecf1d4894cf05845cdce44549ed3ccca3478b97a70972d1bc82ac4f2d1` | `apps/desktop/src/renderer/domains/models/assets/provider-icons.ts` | 原字节编码为 data URL |
| `src/renderer/assets/model-providers/ollama.svg` | `9c62bf0159ee96c8b58c86a732f33b002b4b3bb165ec86e8ecca51ad6a82dab6` | `apps/desktop/src/renderer/domains/models/assets/provider-icons.ts` | 原字节编码为 data URL |
| `src/renderer/assets/model-providers/openai.svg` | `45be1f0757eb18889eefb1e7db79668ef46a275dc4e0e78e8df5ebd7f6cdeadc` | `apps/desktop/src/renderer/domains/models/assets/provider-icons.ts` | 原字节编码为 data URL |
| `src/renderer/assets/model-providers/openrouter.svg` | `9148696e3a06d23e8fe2b743ebd3ee1173354dbd7b58d33d1ca6a40ee0018d53` | `apps/desktop/src/renderer/domains/models/assets/provider-icons.ts` | 原字节编码为 data URL |
| `src/renderer/assets/model-providers/siliconflow.png` | `b22c6e5167d27c206ef34652eeec6824ee9c52e04835da394a839035ea5aa4f3` | `apps/desktop/src/renderer/domains/models/assets/provider-icons.ts` | 原字节编码为 data URL |

| `src/renderer/pages/ModelsPage.tsx` | `ebe0a8d6d6e350f9faf5159fa4d25ba388c7716797bfd8494cd52aca671ab9a9` | `apps/desktop/src/renderer/domains/models/{components,hooks,pages}/` | 保留选择、搜索、按钮互斥与反馈；拆分页面组合与查询；加实例/会话隔离 |
| `src/renderer/features/models/ProviderWizard.tsx` | `1d427e3ff77f945e56f196d8a5a00e3dcb3704d58bc05a4242b05de8fa44250e` | `apps/desktop/src/renderer/domains/models/components/Provider*.tsx` | 保留三步新增/直接编辑；分离子步骤；密钥只写；忙碌锁与冲突恢复 |
| `src/renderer/features/models/ModelEditor.tsx` | `a054cdc44dda63de3858dea3d3ed7f0bc6e608f13f5ad141d6c877170abd819c` | `apps/desktop/src/renderer/domains/models/components/Model*.tsx` | 保留split/字段/测试并行语义；拆分表单、ID、测试、移除；迟到结果隔离 |
| `src/renderer/features/models/provider-catalog.ts` | `ec2adb1b73c00999c40caf0555a48ed01c37cccfb2f6f09176f733bee069b7ff` | `apps/desktop/src/renderer/domains/models/provider-catalog.ts` | 预设目录与品牌复用；前后端统一空Key策略 |
| `src/renderer/features/models/model-api.ts` | `1a7e3e662ec4ba0d80fe8929f4e8efdb0f1fe8f619ecd0551f80bbe3082c6b3e` | `apps/desktop/src/renderer/domains/models/api.ts` | 参考endpoint/操作；改用新OpenAPI类型与共享客户端 |
| `src/renderer/features/models/ProviderWizard.test.tsx` | `ee3414aad46f3518c80c71f7b305aa0b039a8400a98ece7e1a9497084e44dcb0` | `apps/desktop/src/renderer/domains/models/tests/ProviderWizard.test.tsx` | 参考旧行为场景；增加busy、冲突、缓存和失败重试 |
| `backend/src/autoflow/api.py` | `b6c43463cacdef67fc5e56a595c34c67712a55fe7e16845ea37f73e631b9895b` | `apps/backend/src/autoflow/adapters/http/models.py + application/models/service.py` | 参考模型路由行为，按adapter/application重写；不复制整个api.py |
| `backend/src/autoflow/models.py` | `dffc32886fefaa0f75dd611fd4d9be3c7cefaa49dac1d3747190a3b6065c5d61` | `apps/backend/src/autoflow/infrastructure/database/model_providers.py + models.py` | 参考非秘密字段与关系；新增事务仓储、CAS和cleanup intent |

保留已有文件/资源的来源声明。上述应用源码依据用户授权复用；没有把旧仓库作为运行时依赖，没有复制旧数据或密钥。

依赖：复用现有 Radix、Phosphor、httpx、Pydantic、keyring；新增 TanStack Query 5 和同族 Radix DropdownMenu。没有迁入旧 react-router/openapi-fetch 或供应商 SDK。
