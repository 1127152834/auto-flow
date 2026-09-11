# Task 11 独立审查：真实列表页、服务恢复与草稿替换

- 日期：2026-09-12
- 审查范围：`ba7096c..d1e4b9a`，提交 `d1e4b9a feat(browser-management): integrate live profile workspace`
- 精确变更集：17 个文件，571 行新增、54 行删除
- 审查顺序：规格符合性 → 代码质量与回归验证
- 结论：**PASS**
- 置信度：**高**

## 可操作问题

未发现需要阻止 Task 11 通过的可操作问题。

## 规格符合性证据

1. **真实列表、筛选与分页符合规格。** `BrowserManagementPage` 通过 `useProfiles` 读取生成契约对应的真实 API；名称/描述搜索和 `none/proxy/pool` 模式筛选完全在客户端完成，没有筛选写请求。页大小固定为 10，搜索和模式切换立即回到第一页；列表数量变化会把当前页钳制到有效范围，删除当前页末项时显式回退一页。页面测试覆盖搜索、模式筛选、11 条数据分页、末项删除回退及筛选复位。

2. **列表信息和状态反馈完整。** 每项展示名称、描述、公开/正式版本、Stable/Preview、指纹种子、内核版本、语言/时区和代理模式；编辑、复制、重新生成指纹和删除均接入现有领域操作。指纹请求有全局互斥、300ms 旋转图标和成功/失败 Toast；页面具备初始加载、空态、无筛选结果、首次错误、后台刷新错误与重试状态。生产页面自身挂载 `Toaster`，通知不依赖测试 helper。

3. **页面只做既有组件组合。** 页面复用 Task 9 的 `ProfileFormDialog`、`ProfileActionDialog` 和 Task 10 的 `KernelManagerDialog`，没有复制表单或内核状态逻辑，没有新增模块侧栏或独立内核路由。App 仍保留总览、代理、模型、设置导航和既有模型认证恢复/`connectionEpoch` 逻辑，只把浏览器占位替换为真实页面。

4. **草稿、嵌套弹窗和焦点行为符合要求。** 配置表单与内核管理组件持续挂载；打开/关闭内核管理不会重置 RHF 草稿。管理按钮的真实元素传入 `returnFocusTo`，关闭内核弹窗及关闭嵌套删除确认后均恢复焦点。共享 Dialog 与 AlertDialog 的 overlay/content 统一在 `z-[50]`，依靠 portal DOM 顺序使后打开的遮罩和内容覆盖前一层；组合测试验证双层 overlay 和返回焦点，既有共享 Dialog 测试验证顶层焦点陷阱。

5. **离线 portal 写保护和恢复入口完整。** App 在连接中或离线时保持已有 workspace 树挂载并向页面传入 `disabled`。配置表单、复制/删除确认、内核 License、刷新、下载、取消、重试、默认项、目录打开和删除均同时使用按钮禁用与处理函数守卫；已打开的配置、操作和内核弹窗内部提供可访问的“重新连接”按钮，因此无需离开焦点陷阱或丢弃草稿即可调用 App 既有 `connect(true)`。测试验证离线草稿、复制确认、配置删除确认和内核弹窗不会发出写请求。

6. **新实例/新 token 不卸载草稿或重放写请求。** `ApiProvider` 仅以实际 `workspaceKey` 作为 App 层 key；同一工作区的 sidecar 实例与 token 更新会替换 client 和查询会话，但保持 `BrowserManagementPage`、表单和本地交互状态。App 回归测试验证新 token 发出新的 profiles GET、名称草稿仍存在，且没有任何非 GET 请求。既有模型 `SIDECAR_UNAUTHORIZED` 单次自动恢复和 POST 不重放测试继续通过。

7. **旧 mock 草稿已退出运行路径。** 当前树中不存在 `renderer/features/profiles`、`profile-workspace.tsx` 或 `profile-workspace-nav.tsx` 文件，也没有相关源码引用；浏览器入口只指向 `renderer/domains/profiles/pages/BrowserManagementPage.tsx`。

## 独立验证

以下命令均在 `/Users/zhangtiancheng/Documents/projects/autoflow`、HEAD `d1e4b9a` 执行：

- `git diff --check ba7096c..d1e4b9a`：通过。
- Task 11 与相关 Task 9/10、App/ApiProvider 定向回归：7 个测试文件、49 个测试通过。
- `npm test`：45 个测试文件、259 个测试通过。
- `npm run typecheck`：通过。
- `npm run lint`：通过。
- `npm run build`：通过；仅有 Rollup 对第三方 `zod` 注释位置的非失败提示，不影响产物。

## 审查边界

Task 9 和 Task 10 的领域能力已各自独立通过，本次只检查 Task 11 对它们的组合与获授权的 `disabled`/`onReconnect`、共享 overlay 层叠和 License 按钮 nowrap 调整。Task 12 正在进行的脚本、CI 和桌面打包验证不属于本次 17 文件变更集，未将其未完成项计为 Task 11 缺陷。主线已有真实 public 145 创建/刷新持久化、嵌套 dirty confirm、删除取消与 reveal 的 CUA 证据；本结论另外建立在精确源码审查和上述独立测试上，没有把该 CUA 结论作为唯一依据。
