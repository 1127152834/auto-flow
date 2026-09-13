# Automation Studio M3 验收记录

- 日期：2026-09-13；状态：实现完成，macOS arm64 实测；Windows 尚未实机验收。
- 依据：[批准规格](../superpowers/specs/2026-09-13-automation-studio-m3-design.md)、[实施计划](../superpowers/plans/2026-09-13-automation-studio-m3-implementation.md)。
- 基线：只读 WebRPA `5ccb900e8dcf1530aae66f676d87593c416c7ebb`；无旧项目运行时依赖。
- 置信度：列出的实际通过项为高；未实测平台与配置组合为未知。

## 交付行为

正式 Studio 增加可折叠拾取浏览器面板和元素定位工具。选择现有 Profile，以 headless=false 启动临时会话，不改 Profile、不访问起始URL、不继承运行/测试浏览器登录态。手动导航、选择标签页、拾取、高亮与匹配测试均经过独立 worker 操作真实 CloakBrowser。

原五类元素动作新增可选 framePath，旧文档缺省主页面，文档表/历史迁移不变。框架每层严格唯一；CSS/xpath=、嵌套和跨域 iframe 使用相同定位入口。路径解析与节点操作共享总超时；非元素截图忽略隐藏定位。声明初值引用沿 M2 解析一次，不用历史运行变量。保存不完整配置仍允许并返回字段问题。

结果预览后同时应用 selector/framePath，一次撤销；应用前再次查询浏览器确认目标仍有效。页面/框架/文档/节点/字段变化不会把旧请求结果写回新配置。测试只读取匹配数/首个可见性/短摘要，高亮最多前100项中的可见元素，3秒后移除，不点击、不滚动、不修改文档。

会话与运行原子互斥，Profile和对应内核锁持有到实际进程清理完成。运行前先捕获/校验草稿，确认后关闭拾取浏览器再运行原快照。新建/打开/关闭/退出/换区沿原协议先保存，再清理，再离开；保存失败或取消保持会话。未知启动保留原标识；重连不重启；服务崩溃不恢复页面、不重放动作。清理失败保留占用及重试责任。

## 与 WebRPA 的行为差异

| 参考实现 | AutoFlow M3 的选择 |
| --- | --- |
| element-picker API 使用全局 browser_engine 并尝试按 URL 复用页面 | 独立临时会话，明确pageId，不接管测试或运行浏览器，不用宽松URL归一化匹配页面。 |
| 拾取脚本含 Ctrl 点击、相似元素模式 | 本阶段左键拾取、Esc取消；不含相似元素批量提取。 |
| 录制/执行中另有 switch_iframe、索引/名称回退路径 | 每个元素节点自带由外到内framePath，每层唯一，无运行时全局框架切换或索引猜测回退。 |
| SelectorGenerator 可直接回退 tagName | 候选以实际定位器核验唯一且为同一元素；位置路径明确提示依赖页面结构，无法证明正确则失败。 |
| 可携带 hints 做选择器自愈 | 不加入自动修复或未知焦点降级。 |
| 查询结果与编辑器状态关联较松 | 稳定session/request/page标识及页面代次；应用前再核实；单次应用进入正式编辑历史。 |
| 浏览器长期全局复用 | 本次会话内保留手动状态，关闭后清理；运行始终新会话。 |

源码取用范围：WebRPA element_picker/script.py 的覆盖层、转义、属性/祖先/位置候选思路；按 AutoFlow provider 整理，实现额外的实际唯一性/元素身份验证。初始化脚本保留禁用时立即返回的事件守卫，保证再次拾取时先于网页业务监听拦截；取消后移除覆盖层并清空目标，不残留活动拦截。页面关闭时由浏览器销毁全部监听器。

## 实际场景与证据

测试使用独立临时工作区和本地受控页面。worker/应用脚本克隆已安装内核；直接浏览器测试使用该内核的只读可执行文件及临时数据目录。均不改用户Profile、Cookie或凭据。实测内核为145.0.7632.109.2，macOS arm64。

| 场景 | 实测结果/证据 |
| --- | --- |
| 真实输入拾取及副作用 | Playwright实际鼠标输入拾取链接、提交按钮和复选框；页面计数、URL、勾选状态不变。结束后正常点击恢复。通过。 |
| 生成/定位 | 特殊字符、重复ID、开放Shadow、与变量语法冲突的ID、结构回退；CSS/XPath零/一/多匹配与隐藏元素。通过。 |
| 框架 | 同域、跨域、嵌套iframe拾取；缺失、多匹配、非框架目标拒绝；导航/移除失效；新页和关页不自动转移目标。通过。 |
| 高亮 | 105项准确计数、仅前100项高亮、3秒移除、非法CSS拒绝。通过。 |
| 独立执行 | 另一套新context使用拾取出的框架路径完成六节点顺序执行，核验真实提取值和PNG字节。通过。 |
| 上述浏览器细项 | [browser.json](automation-studio-m3-qa/browser.json)，8组；脚本 smoke-workflow-inspection.py。 |
| worker资源与异常 | 真实启动/可见覆盖/空白初页/幂等/互斥；连续5次启动中关停、挂起导航关停、SIGKILL worker、SIGKILL sidecar及重启。受管worker/browser均清理，资源再次可用。源码与冻结各5组通过。 |
| worker证据 | [源码](automation-studio-m3-qa/source-worker.json)、[冻结](automation-studio-m3-qa/frozen-worker.json)；脚本 smoke-workflow-inspection-worker.mjs。 |
| 正式界面闭环 | 打开专用浏览器、手动导航、iframe拾取预览/应用/定位测试/保存、成组撤销重做、取消/确认关闭后独立运行、原生Studio关闭保护。开发URL、构建HTML、正式目录包各4组通过。 |
| 界面证据 | [开发](automation-studio-m3-qa/dev-studio.json)、[构建HTML](automation-studio-m3-qa/built-studio.json)、[目录包](automation-studio-m3-qa/packaged-studio.json)。 |
| 界面测试输入说明 | Electron中的按钮、画布操作使用CDP鼠标输入，表单通过原生value setter和input/change事件输入；为了稳定控制外部浏览器，受控iframe主动派发DOM点击进入真实拾取脚本。该项不冒充可信鼠标输入；可信鼠标拾取和副作用已由上方独立真实浏览器用例覆盖。没有模拟执行器或伪造拾取结果。 |
| M1正式应用回归 | 13组通过：真实保存/重启/冲突/撤销/复制、窗口复用、服务恢复、主窗口独立关闭、工作区切换成功/取消/失败回滚等。[证据](automation-studio-m3-qa/m1-regression/built-html.json)。 |
| M2真实运行回归 | 8组通过：六节点/变量/标签页/等待/截图/超时停止/资源锁/日志补读与重启隔离。[证据](automation-studio-m3-qa/m2-regression/source.json)。 |
| 离开与编辑竞态 | 前端交互测试覆盖关窗/退出/换区保存失败、取消、等待清理；迟到拾取的节点/文档/字段/页面变化；未知启动原ID重试；离线重连及关闭失败重试。通过。 |

启动即关闭验收曾出现15秒超时，失败轮次未记为通过。任务栈和确定性回归确认：Python 3.11 的 `asyncio.wait_for` 在内部读写刚完成与外部取消同时发生时可能返回结果、吞掉取消，导致 worker 继续读取。运行/拾取通道改用 `asyncio.timeout`；4个覆盖读/写及两类worker的竞态用例修复前均失败，修复后通过。另补齐 `--inspection-worker` 的原生进程身份识别，并将无法确认进程退出的等待限定为有界失败，保留占用和重试责任。最终源码和冻结入口各连续5次启动即关闭以及完整5组异常清理验收均通过。

## 工程检查

- 后端最终全量 pytest：529通过，2项现有依赖弃用警告。
- 前端全量：412通过，63个测试文件。
- Ruff、mypy（154个源文件）、TypeScript、ESLint通过。
- OpenAPI一致性、目录检查3项、脚本检查12项通过。
- renderer/main/preload、PyInstaller后端及macOS arm64目录包构建通过；正式目录包真实启动并完成M3闭环。
- 截图：[拾取预览](automation-studio-m3-qa/packaged-picker.png)、[定位测试](automation-studio-m3-qa/packaged-test.png)。

## 实机边界

Windows尚无实机测试；Windows Job对象/进程清理沿用现有适配，不将模拟平台分支视为实机通过。macOS签名/公证与正式发布不在本次验收范围。付费License、外部代理、第三方扩展及动态地理配置的所有组合没有逐项实测；复用既有启动参数，不声称组合全覆盖。封闭Shadow内部不提供定位保证。录制、Debug、控制流与企业/发布管理能力未在M3实现。
