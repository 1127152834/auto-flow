# Automation Studio M4 验收记录

- 日期：2026-09-13；状态：实现完成，macOS arm64 实测通过；Windows 尚未实机验收。
- 依据：[正式规格](../superpowers/specs/2026-09-13-automation-studio-m4-design.md)、[实施计划](../superpowers/plans/2026-09-13-automation-studio-m4-implementation.md)。
- 实测：macOS arm64，CloakBrowser Chromium 145.0.7632.109.2；独立临时工作区、本地多 origin 页面，无第三方账户。
- 置信度：本记录列出的实测项为高；Windows/macOS Intel 等未实测平台为未知。

## 已交付能力

正式 Studio 提供条件判断、次数/列表/条件循环、设置/增减/追加变量，以及退出/跳过最近循环。控制块自动配对，按端口和配对关系编译为结构化顺序计划，允许嵌套32层；不是按画布坐标或节点数组顺序执行。

条件支持 typed literal/variable、对象字段与列表索引、严格比较、all/any 短路，以及 M3 selector/framePath 网页判断。循环局部变量只读、无静默遮蔽，列表按进入时快照遍历，while 每轮重新判断。单循环与全运行有明确上限；每步可取消。

文档格式2兼容读取1，旧文档内存升级不置脏，手动保存才更新原 revision；未完成配置可以保存。复制/删除起点包含完整块，结束节点不能独立删除；修改进入原撤销历史。

逐次 executionId、循环路径、分支、耗时与产物引用沿现有 seq/SSE 持久化。终态来自调度结束和资源清理，进度显示实际调度次数。当前一次执行的停止/失败不能被该节点先前成功覆盖。产物索引使用增量迁移0007，旧文件/标识不变，新增分页与节点/执行筛选；截图仍不覆盖显式同名文件。

## 实测矩阵

| 场景 | 结果与证据 |
| --- | --- |
| 完整业务流程 | 保存并重启服务后读取流程；foreach 遍历启用/禁用项，根据 item.enabled 与跨域嵌套 iframe 页面状态分支；真实输入、点击、提取、累积和元素截图。禁用项 continue，结果严格核对为 `["1","3"]`，两张 PNG 均检查实际文件签名。源码/冻结通过。 |
| 条件与汇合 | typed 布尔分支、全部/任一、顺序短路；非法 CSS 位于被短路规则时不执行；正常汇合后结果节点只执行一次。真实浏览器通过；变量汇合交集另有领域测试。 |
| 网页条件 | 实测零匹配、隐藏/不可见、否定存在、CSS/XPath、开放 Shadow DOM、嵌套跨域 iframe。非法 CSS、缺失框架返回 condition 节点及 `config.rules.0.selector/framePath.0`，不进入假分支。 |
| 三类循环 | foreach + continue、count、while 重新求值及上限边界在真实 worker 通过；0次/空列表由调度测试验证；1000轮变量累加后写入真实 input，提取核对为1000。 |
| 嵌套 break 与列表快照 | 外层 foreach 遍历 `[1,2]`，内层循环 break，仅退出内层；每次向原列表追加9，最终真实输入/提取结果为 `[1,2,9,9]`。追加数据没有扩大本轮遍历。 |
| 变量和保护 | 严格 bool/number/string 比较、字段/索引缺失、深复制、列表追加一个值、只读局部名、分支可用性与循环后越界引用、错误配置 JSON 类型均有领域测试。声明对象数据和结构化 literal 区分，固定文本不执行变量模板。 |
| 控制图与上限 | 配对、端口、非法回边、变量路径、32层允许/33层拒绝、100000次调度前拒绝下一步均有测试。次数超过循环上限在体前失败；while 上限条件仍真失败、变假正常结束。 |
| 编辑与兼容 | 配对插入、整块复制/删除/撤销、局部重命名、旧文档无脏升级及真实 revision 冲突测试通过。正式 Electron 用实际属性表单与 React Flow 端口编排，保存、打开、独立运行；不是只向 API 注入示例。 |
| 逐轮产物 | 同一提取节点55次真实执行，55个唯一产物/执行标识；详情只取50项，按17项分页补齐，按 executionId 筛选、重启后读取末项均通过。两轮元素 PNG 分别保留。 |
| 日志 | 按7条一页补读全部事件，序号无丢失/重复，node_started 数量与 executionCount 一致；正式日志/结果显示轮次，画布显示累计次数。旧事件继续显示历史单次执行。 |
| 停止和清理 | 100000上限 while 运行中请求停止，10秒内确认 cancelled，随后检查克隆内核路径下无受管浏览器。补充真实子进程满 stdout 管道测试，停止不提交排空消息，所有权清理后释放。 |
| 历史迁移与持久化 | 旧 artifact 数组迁入索引，标识/文件路径保留，升级/降级/再升级测试通过。123个产物分成50/50/23项，独立事件事务及筛选验证通过。 |
| M1 生命周期回归 | 正式 Electron 13组：六节点编辑、撤销、剪贴板、真实保存打开、离线恢复、冲突、未完成保存、窗口复用、主窗独立关闭、退出、切工作区取消/保存/放弃及回滚，完整应用重启恢复。 |
| M2 浏览器回归 | 8组：六节点、输入替换/追加/空值、六类提取及大于64KiB结果、四种等待、标签页跟随、截图范围/路径/同名拒绝、失败即停/资源占用、SSE续读及重启、会话隔离和配置。 |
| M3 定位回归 | 8组真实浏览器：鼠标拾取副作用拦截/恢复、特殊/重复标识、开放 Shadow、同域/跨域/嵌套 iframe、路径错误、导航/页面关闭失效、105个匹配高亮上限，以及拾取后新context的六节点实际执行。 |

M4 网页判断复用 M3 定位器；不把 M3 的页面关闭/导航测试记成在每一种 M4 条件表单下重复实测。离开协议、资源异常恢复和快照竞态同时由现有前后端测试回归覆盖。

## 证据文件

- worker：[源码7组](automation-studio-m4-qa/source-control.json)、[冻结7组](automation-studio-m4-qa/frozen-control.json)。
- 正式 Studio：[开发URL](automation-studio-m4-qa/dev-studio.json)、[构建HTML](automation-studio-m4-qa/built-studio.json)、[macOS包](automation-studio-m4-qa/packaged-studio.json)，每个入口3组。
- 画布与结果：[编辑器](automation-studio-m4-qa/packaged-editor.png)、[执行标记](automation-studio-m4-qa/packaged-executed.png)、[逐轮结果](automation-studio-m4-qa/packaged-results.png)。
- 回归：[M1](automation-studio-m4-qa/m1-regression/built-html.json)、[M2](automation-studio-m4-qa/m2-regression/source.json)、[M3](automation-studio-m4-qa/m3-browser.json)。
- 工程统计：[checks.json](automation-studio-m4-qa/checks.json)。

## 实施中发现并修复

1. 高速循环填满 worker stdout，停止时消费者停止读取，进程退出等待被管道拖延。清理阶段独立排空管道，并保留进程树清理/重试责任；排空消息不被补写成成功事件。真实压力场景及专用进程回归通过。
2. React Flow 受控节点重新生成时丢失 measured/handle bounds，开发模式重开后节点可能保持隐藏。尺寸只保留在画布会话中，并通过正式 updateNodeInternals 接口更新连接点；不写入工作流。开发与正式包复测通过。
3. 旧“文档节点都完成即 finishing”不适用于分支/循环；已改为调度结束后进入清理。历史 nodeId 成功不能代表本次 executionId 成功，避免重复节点本轮取消仍显示完成。
4. 保留原六节点未完成保存的断开节点问题；schemaVersion2 不应使缺少参数时的连线提示消失。M1 实际应用回归确认。

## 工程与平台边界

pytest、Ruff、mypy，前端测试、TypeScript、ESLint，OpenAPI 一致性、目录检查、脚本测试，以及 renderer/main/preload 构建、PyInstaller 冻结和 Electron `package:dir` 均执行；具体数量见 checks.json。

macOS arm64 的开发URL、构建HTML、冻结 sidecar 和 `AutoFlow.app` 已实际运行。Windows x64、macOS Intel 尚未实机验收。此次验证的是本地未签名应用包，未进行发行签名或公证。

子流程、异常处理分支、自动重试、Debug、录制、双视图、分组注释及剩余核心动作仍未交付；M4 不代表 WebRPA 核心能力全部对齐。[差异及来源表](../automation-studio/WEBRPA_CAPABILITY_MATRIX.md)保留了本轮明确批准的契约差异。
