# M5 5B 实施决定

- 日期：2026-10-07；状态：confirmed
- 来源：用户在 M4 收尾时明确授权"都由你来决定，你来做决策"，并要求继续执行 M5；依据 2026-10-07 五个区域的源码调研与完整性评审，步骤见 [5B 步骤计划](../../docs/superpowers/plans/2026-10-07-remediation-m5-5b-step-plan.md)
- 范围：只约束 5B；延续 5A 的 D1–D14

| 编号 | 决定 | 理由 |
|---|---|---|
| D15 | 接受新增 CodeMirror 6（`@codemirror/state`、`view`、`autocomplete`、`commands`，约 4 个包），仅 Studio 入口使用；合入前先 `vite build` 对比 studio chunk 体积；补全面板沿用现有下拉的数据与排序；超标再考虑自写 | 规格 R5-13 指定 CodeMirror 6；Studio 为独立入口，不影响主窗口 |
| D16 | `tagInput` 与 5A 的 `newStudioLayout` 同为客户端 featureFlags（URL > env > localStorage），不进工作流文档，不触发规则 1；`VariableInput` 同名同属性导出，内部按开关委托 `TagInput`；保存值保持字符串（`{input.组.字段}`），不加新语法，显示名由解析器现查；默认关，Task 3 完成并逐页验证后才切为默认开，保留一个版本可关 | 563 处调用方不能改 |
| D17 | 稳定 key 不做数据迁移：旧中文 key 合法，新建一律用英文 key；共享解析器同时识别新旧四种引用格式并显示别名；转不了的（记录身份、版本）保留旧格式；旧 `{变量}` 保留到 M6 | 避免批量改写用户的流程文档 |
| D18 | 虚拟滚动用 `@tanstack/react-virtual`（写代码前用 Context7 核对 v3 与 React 19），做成共享 `virtual-list` 组件供批次任务表与数据表共用；数据表先做全宽/冻结首列/列宽记忆/抽屉，虚拟化与游标分页在基准证明服务端分页不足时再上，但 R5-23 条目保留 | 两处共用一套方案 |
| D19 | 签名样例值放进 `content.signature` 的可选 `sample` 字段（敏感字段拒绝落样例），沿用 `keep_signature`；签名 outputs 契约 5B 不做编辑，R5-12 的输出区块先只读展示 End 业务结果与写回产出（B12 留到后端先定契约后） | 避免前端先于后端定契约 |
| D20 | 4 个写回表单（更新当前记录、设置状态、新增记录、查询记录）是 `project_data` + operation 的外观层：不新增 moduleType、不改后端执行器、旧工作流无需迁移；参数 JSON textarea 折叠到高级；文档写明服务批量录入与多账号运营场景（规则 5） | 最小改动且可回退 |
| D21 | 新增后端 `POST /automations/{id}/input-match`（B4）：接收草稿 inputPlan，返回每输入 matched/unprocessed/sample[3]，口径为"台账无成功或占用记录且满足状态条件"，后端脱敏、`asyncio.to_thread`；落地前绑定页只显示"当前条件匹配 N 行"+样例（records list 近似），不显示 M，文案不暗示可运行 | 未处理口径必须由后端定义 |
| D22 | End 预检放启动请求校验：`previewWrites` 且 End 配置 `retainEnvironment` 时启动直接 409（沿用 `PREVIEW_CANNOT_SAVE_ENVIRONMENT`，不创建批次/任务），保存工作流时不拦；保留 `end.py` 运行时兜底并补测试；前端清除 sessionStorage pending 并显示原因与建议 | 现状是网页操作已真实执行后才 409，规格要求预检阻止 |
| D23 | 批次监控实时性：后端聚合接口 + 可见性感知的 ≤2 秒轮询，不新建批次级 SSE；失败归组键用稳定 `errorCode` 枚举（含 unknown 兜底）而非 message；前端维护 code→文案/建议映射并加漂移测试；10,000 行聚合附基准与 loop_lag | 事件批量与规则 3/4 |
| D24 | 缩略图：先降级为"最近一张已有截图并标明非实时"，不新增 5 秒周期帧接口；Phase B 末尾再评估是否新增轻量最近一帧接口（限频、etag、仅可见时拉取） | 现有证据模型只有错误/结果截图 artifact |
| D25 | 运行总览：5B 的 Task 8 只做项目内指标行；跨项目聚合与全局导航一起放 5D | 避免与 R5-19 重复 |
| D26 | 节点实际值来源：优先复用 `NodeAttemptView.executionContext` 与 output 事件 payload；缺才补后端字段，且必须后端脱敏，不得前端按字段名正则猜（现有 `/password|密码/` 打码改用 `sensitive` 标志） | 规则 2 与安全 |
| D27 | 批次进度的 errorCode 只来自台账（last_outcome/last_error.code）；数据库固定为 SQLite（失败分组与占用查询使用 json_extract） | 与 D23 配套，换库时需重写这两处查询 |
| D28 | CodeMirror 6 实测净增约 658KB（未压缩，studio chunk 3.60MB→4.27MB；仅 state+view 就 431KB），超过 D15 设定的 400KB 保险线。决定**接受**（规格 R5-13 指定 CodeMirror 6，Electron 本地加载无网络代价），但 `TagInput` 用 `React.lazy` 动态引入，CodeMirror 单独成块、只在 `tagInput` 开关开启时才加载，默认用户启动与解析成本不变；`VariableInput` 开关关闭时与原实现逐字节一致，开启但块尚未加载时回退为原生输入框。开关开启下约 63 项既有测试依赖原生输入框（占位符查询、`fireEvent.change`、label htmlFor），逐页适配后才可考虑默认开启 | 体积保险线是实施方自设的阈值；懒加载同时满足规格与"默认用户不受影响"；实测（2026-10-07 构建）：studio 入口 3,619.87 kB（装前约 3,601 kB，基本持平），CodeMirror 独立懒加载块 TagInput 650.24 kB；开关开启时 workflows 域实际失败 13 项/7 个文件（含 1 个本机已知失败）。|
