# 模型管理 OpenRouter 实网验收

- 日期：2026-09-12
- 状态：confirmed；macOS 开发环境实网与隔离 API 闭环通过。
- 授权来源：用户提供 OpenRouter Key，要求从接入到调用及各类管理场景完整测试。
- 实现分支：`codex/model-openrouter-live`。
- 凭据规则：Key 仅经密码输入框／进程 stdin 进入内存与系统凭据存储，不写源码、报告、数据库或日志。测试脚本不接收命令行或环境变量中的 Key。

## 结论与修复

实网发现并修复两项功能缺陷、一项反馈问题：

1. **公开目录不能证明 Key 有效。** 无认证及明显错误 Bearer Key 调用 OpenRouter `/api/v1/models` 都返回 200；相同错误 Key 调用 `/api/v1/key` 返回 401。原实现仅根据目录判断连接成功，会让错误凭据进入保存路径。现在 OpenRouter 预设先校验同一 Base URL 的 `/key`，收到合法对象后才加载目录。连接预览、首次保存、连接更新、已保存供应商测试共享此规则。
2. **目录元数据丢失。** 补齐 OpenRouter `name` 和 `context_length`，新导入模型可以保留真实显示名称和上下文窗口。已保存模型的用户自定义字段不会被目录刷新覆盖。
3. **失败提示为英文且信息不足。** 模型领域错误使用固定中文白名单；认证失败、接口不存在、限流和 HTTP 402 余额／额度不足分别给出明确提示。远端错误正文仍不返回前端。

OpenRouter 网关沿用用户填写的 Base URL，不会把网关 Key 转发至另一个固定官方地址；选择 OpenRouter 预设的网关须提供 `/key`。其他 OpenAI-compatible 预设不增加鉴权请求。

来源：[当前 Key 接口](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-key)、[模型目录响应](https://openrouter.ai/docs/api/api-reference/models/get-models)；实际行为以本次 HTTP 检查和测试为准。

## 真实调用与桌面操作

运行环境为 baseline 的 Electron、真实本地后端和 macOS 系统凭据存储。

| 场景 | 实际结果 |
| --- | --- |
| OpenRouter 官方 `/key` 鉴权 | 200；不记录账号详情 |
| 新建供应商时 Key 为空 | 测试连接按钮禁用 |
| 供应商目录 | 实际发现 445 个模型；该数量会变化 |
| `liquid/lfm-2.5-2.6b:free` 调用 | 429，界面显示调用失败；不计为成功 |
| `google/gemma-4-26b-a4b-it:free` 调用 | 429，界面显示调用失败；不计为成功 |
| `openai/gpt-4o-mini` 调用 | 返回 `OK`，桌面记录约 939 ms；[截图](01-generation-success.jpg) |
| 手动添加、编辑模型 | 模型标识、名称、上下文、标签和说明保存后可读取；编辑时标识只读 |
| 标签搜索、停用、状态筛选 | 标签搜索结果为 1/3；停用后“已启用”筛选为 0/3 |

桌面测试过程中已有 `QA OpenRouter 0912` 及两个 Aion 模型被保存；供应商级删除验收在独立临时工作区执行，不删除当前桌面的这组记录。桌面截图中的“QA 免费模型”为换用 GPT-4o mini 前的临时显示名，后续已改为“QA GPT-4o mini”，不代表该模型免费。

## 隔离实网 API 闭环

脚本：[verify-openrouter-live.py](../../../scripts/verify-openrouter-live.py)。使用真实 `HttpModelProvider`、真实 `SystemCredentialStore`、临时 SQLite 和 FastAPI `TestClient`；没有替换模型网络请求或凭据存储。

结果：[api-results.json](api-results.json)，**25 PASS / 0 FAIL，14 个管理接口均覆盖**。脚本实跑两轮，每轮独立实网生成一次，GPT-4o mini 均返回长度为 2 的正文；报告保存最终脚本的一轮结果，不把重复运行叠加为用例数。以下均是实跑断言：

| 检查组 | 验证内容 |
| --- | --- |
| 接入 | 预览不落库、错误 Key 被拒、零模型接入、选定模型接入、供应商列表与详情 |
| 元数据 | 真实目录非空名称和正整数上下文、供应商基础信息更新 |
| 连接回滚 | 错误 Key 和无效 URL 保存失败后，原配置、系统凭据引用和实际 Key 字节保持不变 |
| 模型管理 | 手动创建、重复拒绝、上下文校验、ID 不可变、编辑和删除 |
| 启停 | 模型停用与供应商停用均从模型选择器移除；恢复启用后恢复可选 |
| 实际调用 | 使用失败连接更新前的原有效 Key 调用 GPT-4o mini，正文非空且符合长度上限 |
| 服务重建 | 关闭 TestClient 生命周期、重新装配应用和凭据存储后，配置与 Key 仍可读取，供应商测试成功 |
| 删除 | 供应商删除后模型级联删除、Keychain 条目消失、列表与 options 为空、凭据清理队列为空；再次重建应用仍为空 |
| 秘密边界 | 响应不包含 Key／secretRef；临时数据库不包含明文 Key；finally 清理本次创建的两条凭据 |

复跑方式（会进行一次少量真实生成；交互输入 Key，不放进命令）：

```sh
uv run --directory apps/backend python ../../scripts/verify-openrouter-live.py \
  --model openai/gpt-4o-mini \
  --report ../../docs/migration/model-openrouter-live/api-results.json
```

默认模型为免费模型；可以用 `--model` 指定当时可用的模型。模型目录和限流会变化，因此重跑结果应重新记录，不能沿用这次结论。

## 自动化回归与构建

- 修复前模型范围：后端 68 passed；前端 39 passed（5 files）。
- 修复后后端全量：339 passed。新增覆盖 OpenRouter 鉴权顺序、错误 Key／错误结构不继续目录请求、非 OpenRouter 路径、元数据和 401／402／404／429 安全中文错误。
- 实网脚本自身的合成故障测试：1 passed；验证系统凭据写入中途异常时，引用仍被跟踪并由 finally 清理。脚本继承真实系统存储，仅记录写入前的引用，不替换真实读写；报告仅保留引用数量。
- Ruff、mypy、桌面 ESLint、TypeScript 检查通过；独立 worktree 的 `npm run build` 通过。
- 现有非失败警告：Starlette 的 httpx／anyio 弃用提示；构建依赖 zod 中两处 PURE 注释被 Rollup 忽略。

主要命令：

```sh
uv run --directory apps/backend pytest -q
npm --workspace @autoflow/desktop exec -- vitest run src/renderer/domains/models
npm --workspace @autoflow/desktop run typecheck
npm --workspace @autoflow/desktop exec -- eslint src/renderer/domains/models
npm run build
git diff --check
```

## 验收边界

- 本次验证模型管理模块，不等于其他功能模块或所有 445 个远端模型均已验证。
- OpenRouter 的成功调用和两种免费模型的 429 是实网结果；402、断网、超时、并发冲突、系统凭据故障等异常主要由已有／新增确定性测试覆盖，不标作线上复现。
- 隔离脚本的服务重建属于应用生命周期和持久化验收，不能代替 Windows 原生凭据存储、安装包或完整 Electron 进程重启验收。
- Windows、其他供应商的真实 Key、多模态与长推理模型、计费金额均未在本轮验证；不作全平台／全模型可用承诺。
