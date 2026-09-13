# 前端完整交付：实际验收记录

日期：2026-09-13。当前为 F0 进行中；F1–F6 未完成。

## 已执行

| ID | 前置/操作 | 预期与实际 | 测试层级/证据 |
|---|---|---|---|
| F0-CATALOG-001 | 运行 inventory-studio-completion.mjs，从当前分类和 AST 取证 | 284 个唯一保留入口，全部找到直接条件/case 源码候选；通过 | 静态结构检查；capabilities.json |
| F0-ROUNDTRIP-节点类型 | 对每个节点调用实际 addNode→export→clear→import | 284 个节点创建的配置、位置、ID 均保留；通过 | Store 规则；catalog-roundtrip.test.ts；不是 UI 保存重开 E2E |
| F0-AI-001 | 已有 open_page，AI 请求仅添加 excel_create | 请求拒绝，原节点不变；通过 | excluded-assistant-nodes.test.ts |
| F0-AI-002 | AI 批量添加 open_page/qq_send_message，并连接两者 | 仅保留 open_page，删除悬空边；通过 | 同上 |
| F0-AI-003 | AI 请求已移除 Excel 工具/资源面板 | 明确拒绝且不切面板；通过 | 同上 |
| F0-UI-001 | 独立 localhost 预览→更多操作→全局配置 | QQ、飞书标签不存在；模型/数据库/凭据等保留；实点通过 | CUA 浏览器 AX 观察；见 evidence/browser-check.md |
| F0-UI-002 | 刷新独立预览，检查底栏及动作库 | 284 入口；无 Excel 资源页签；数据表格/全局变量/图像资源保留；实点通过 | CUA 浏览器；不是正式 Electron E2E |

## 台账边界

capabilities.json 和 test-cases.json 由 scripts/inventory-studio-completion.mjs 生成。1,988 条是逐节点的初始用例模板，尚需展开实际字段分支、工具与期望合同，状态为“待细化”。**不能将模板数当成已执行用例数。** 源码 AST 字段/组件是候选依赖，不是人工确认的完整调用闭包。

## F0 尚未关闭的事项

- 逐节点实际字段、共享工具、动态分发与全部分支的人工核对。
- 非节点能力逐项注册与具体用例展开。
- 排除能力的剩余 AI 工具描述、Mock 路由与无引用源码清理。
- 旧文档顶层排除节点闭环已通过；自定义模块内部的递归检查仍需核对。
- 现存数据/图像资源共享消费者审计；不得误删保留节点的配套功能。

## 未验收

全部 HTTP/SSE 契约一致性、运行/Debug/录制复杂闭环、正式 Electron 用户端到端、正式包及 macOS Intel/Windows。本轮浏览器实点不能替代这些验证。真实后端执行也未实现。

## 工程回归

- 全桌面单元/组件测试：79 个文件、765 项通过，见 evidence/unit-tests.txt。
- 首次全量检查发现 3 条新增中文缺少英文翻译；已补充 uiI18nDict 并完整重跑通过，没有放宽断言。
- 这些测试包含旧系统、源测试和新增用例；数量不代表 765 个端到端业务场景。
- TypeScript、ESLint、renderer/main/preload 构建通过；构建输出见 evidence/build.txt。依赖的 Rollup 注释警告保留在输出中，不影响构建成功。

## F0 第二批：旧节点与入口保护

- F0-LEGACY-API-001：保存含 excel_create 的旧文档，GET 保留原字段，execute 返回 422，活跃运行仍为空，再次 GET 无损；mock-transport.test.ts 通过。
- F0-AI-004～006：版本提交、发布和屏保动作不再执行；excluded-assistant-nodes.test.ts 通过。删除相应实际分支及权限元数据，保留已确认范围内的定时任务能力。
- F0-UI-003：宽窗口通过“导入整包”选择独立测试文件，选择旧节点显示原配置；F5 明确拒绝运行；保存→刷新→打开→选中，path=/original.xlsx、custom=preserve 保持。CUA 真实浏览器操作通过，接口为 Mock，不能计作正式 Electron E2E。
- 旧节点专属表单改为配置 JSON 预览；通用备注与高级设置仍可编辑，不声称整个文档只读。
- 284 个入口分类提取为纯 lib/moduleCatalog.ts，AI/Mock 不再反向依赖 React 侧栏组件。component-tools.json 增加函数式组件依赖候选，未解析项仍需核对，不能作为完整覆盖证明。
- 当前全量回归：79 个测试文件、769 项通过；TypeScript、ESLint 通过。renderer/main/preload 构建通过，见 evidence/f0-legacy-build.txt；测试输出见 evidence/f0-legacy-tests.txt。
