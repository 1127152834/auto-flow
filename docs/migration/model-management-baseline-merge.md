# 模型管理合入 baseline 的验收

- 日期：2026-09-12
- 状态：confirmed；合并代码通过本机验收，提交父节点记录实际来源。
- 授权：用户要求将模型分支代码合并到baseline，并检查合并条件。
- 输入：`codex/architecture-baseline@b45ca84`、`codex/model-management@fe3672a`；共同基点`ad08bdb`；后续接入浏览器客户端检查点`06153ca`。
- 方法：从baseline创建独立worktree `autoflow-merge-models`，试合并、解决冲突和验证后，再将baseline快进到该合并提交。不重写模型或baseline历史，不推送远端。
- 置信度：本机合并与回归结果高；Windows实机和线上供应商仍未验证。

## 合并条件与处理

原始分支不能直接无冲突合并。baseline已包含代理模块、新内核服务与桌面IPC；以下冲突已按功能合并，未整文件覆盖任意一边：

| 位置 | 合并结果 |
| --- | --- |
| 后端装配 | 保留profiles、proxy、kernel服务及worker/代理连接/数据库关闭流程；增加model service和14条接口；复用baseline的延迟系统凭据存储，可注入测试凭据/网关 |
| HTTP错误 | 保留kernel/profile映射、proxy专用安全校验处理和model错误；普通401使用SIDECAR_UNAUTHORIZED；internal接口继续要求独立host token并拒绝Origin |
| 前端客户端 | 同时保留proxy的结构化error（风险确认、429和outcome_unknown）与model的code/details/requestId；接入BrowserApiError、对象body、请求超时与SSE取消，204和安全退化继续有效 |
| Electron main | 保留代理凭据复制、内核目录显示的受控IPC；采用模型工作台默认窗口尺寸 |
| 依赖与类型 | 保留baseline的Query/表单依赖，加入Radix菜单；从合并后的真实OpenAPI重新生成客户端，不手拼生成文件 |
| 迁移 | 保留已存在的两份0002迁移；新增`0003_merge_proxy_models`汇合版本，形成唯一head，避免改写已执行历史 |
| 文档与记忆 | 保留代理、内核和模型记录；独立分支验收作为历史证据，当前合并结果以本记录为准 |

数据库汇合采用Alembic merge revision，父节点为`0002_proxy_management`和`0002_model_management`。这不是让部署选择两个head；`upgrade head`最终只有`0003_merge_proxy_models`。新增测试分别从空库、0001、代理0002、模型0002升级，重复升级仍成功；已有代理组、代理扩展记录和模型清理意图不丢失，外键检查通过。

## 验证

全部验证在隔离worktree、临时数据库中执行，没有拿正在运行的用户数据库做升级试验。

| 检查 | 结果 |
| --- | --- |
| `uv run --directory apps/backend pytest -q` | 304 passed，2条既有依赖弃用提示 |
| `ruff check .` / `mypy src` | 通过，102个Python源码文件 |
| `npm test` | 23 files / 126 tests passed，包含原proxy/kernel和model组件回归 |
| `npm run typecheck` / `npm run lint` | 通过 |
| `npm run openapi:generate` / `npm run openapi:check` | 通过，internal路径未进入公开schema |
| `npm run test:scripts` | 7 passed，含3个结构检查 |
| `npm run build` | main/preload/renderer构建通过 |
| `npm run smoke:desktop` | 启动、认证、退出后sidecar回收通过 |
| `node scripts/smoke-model-management.mjs` | 开发Electron + 真实本地API完整增删改查/测试流程通过 |
| `npm run backend:build` / `npm run package:dir` | macOS arm64后端与Electron目录包通过 |
| 打包应用的`smoke-model-management --executable` | 随包后端、迁移、完整UI流程及退出回收通过 |

新增`test_merged_management.py`验证四个模块同时可读、模型缺Key错误未被proxy handler覆盖、代理校验不泄露合成Key、普通token不能调用internal、带Origin的host请求被拒绝。新迁移测试和保留的客户端两套错误测试使合并风险成为可回归检查。

## 并发检查点整合

首次候选`9009285`验证的是`b45ca84 + fe3672a`（303后端、105前端）。快进时检测到浏览器任务正在修改共享客户端，Git中止且没有覆盖工作区；与该任务协调后，在独立worktree接入其已提交的`06153ca`再验收。上表为更新后的组合结果。

客户端保留Task7的普通请求body读取超时、headers之后SSE取消、连接阶段超时、字段错误和固定401文案；保留模型构造错误的code/details/requestId及代理风险确认元数据。模型的六类外部操作使用60秒前端总预算，避免新的10秒本地请求默认值截断目录和生成；后端15/30秒HTTP超时配置不变。新增慢目录12秒、生成20秒测试验证这一交集。

`ApiProvider`（浏览器）与`query-provider`（模型）当前各自服务独立页面，未在当前App嵌套。浏览器Task11统一会话查询上下文和全局导航时必须保留模型入口以及SIDECAR_UNAUTHORIZED/epoch恢复，已经向所属任务交接。

## 工作区与能力边界

baseline已有的automation计划、浏览器/automation未提交文件保持原样。Vite本地修改与模型分支的Tailwind配置字节一致，随这次合并进入版本历史；其内容不改变。未提交文件在合并前后按SHA-256核对，实际落地状态以会话记录为准。

这是已批准模型模块与baseline现有能力的代码合并，不补做其他线程的浏览器工作台或代理全局导航。模型分支的顶部入口被保留；其余未提交页面继续由原任务推进。

Windows/macOS Intel、真实线上模型供应商、ProxyPanel真实响应映射与发布签名仍沿用各模块既有未验证边界，不作为本地合并通过的证据。
