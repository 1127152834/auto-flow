# 项目任务交互命令接入（2026-09-24，进行中）

## 已实现的进程边界

- 能力ID：`node:input_prompt` / `node:js_script`；分类：原版命令总线复用＋AutoFlow必要适配。沿用冻结迁入的执行器、`_WorkerCommandBus`、输入转换、JS变量写回；没有新JavaScript执行器或模拟自动化引擎。
- `ProjectGraphExecutor` 给根流程、子工作流、自定义模块、画布子流程接入同一总线。交互请求/关闭事件沿既有项目事件ACK链，附节点访问标识与作用域。
- 项目worker保持单一stdin读取方；有限的输入/脚本回传增加runId/执行代次核对，确认事件不包含提交值。发送前和取得写锁后均检查停止/失效，停止优先于仍在排队的回复。
- 输入密码值接入已有敏感变量机制，真实值继续用于运行，普通输出、后继日志及子流程摘要不得泄露。此为AutoFlow必要适配；原版输入转换、取消保留旧值及输出变量语义不变。

## 实际验证

- `red.log`：原项目worker不产生交互请求，真实子进程测试失败。
- `race-red.log`：写锁等待中的回复在停止后仍发送，失败后在实际发送边界修复。
- `nested-red.log`：子流程交互缺executionContext，失败后复用现有上下文封装。
- `password-red.log`：受控密码出现在普通输出事件，失败后使用已有敏感变量追踪。
- `regression.log`：86项共享Studio命令协议、JS、worker、项目图测试通过（早于最后嵌套及密码补充）。
- `final.log`：41项最终项目交互、项目图及冻结输入差分通过，39.16秒。其中10项是真实项目子进程：根/子工作流整数、取消保留值、JS返回/变量修改、密码隔离、停止及回复竞争；错误runId/代次/布尔代次拒绝。
- `ruff-final.log`、`mypy-final.log`：最后5个生产文件检查通过。
- 这些是进程/规则证据。JS响应由测试给定，不是正式renderer执行证据；没有把它当成Electron E2E或真实JS前端验收。

## 项目服务及事件接入（同日后续检查点）

- 复用 `ProjectOperationRow`，没有数据库迁移。项目/任务/代次准入后保存稳定命令ID及请求摘要；同ID同内容只查询、不重发，不同内容409。脚本沿原版领取→结果语义，拒绝另一个领取者。
- `POST /api/v1/projects/{projectId}/tasks/{taskId}/interactions/commands`；`GET .../commands/{commandId}`；`GET .../requests/{requestId}`。接口接入正式路由组、停写和已有错误包；OpenAPI已生成。提交202只表示accepted；worker确认与对应事件同事务写库后才applied。未确认命令在终态同事务结为failed，交互查询为unconfirmed，不回放。
- 请求内容只在活跃父进程内存中保留，经项目/任务归属检查单独读取（Cache-Control: no-store）。普通事件只保存请求标识、状态和执行上下文，不保存解析后的默认值、标题、选项、脚本和变量；既有项目事件序号/SSE用于发现与补读。结束请求及运行清空内存；服务重启不恢复网页动作/脚本执行。
- 通用项目操作目录补充workflowInteraction类型及资源定位器；继续沿既有规则隐藏行内runId/代次，避免新操作使原目录响应500。
- 发现重复已持久事件会重新打开已关闭请求，`service-replay-red.log`证明失败。只对新提交事件更新内存请求状态后，`service-final.log`37项通过（14项新服务/真实进程接口＋23项调度）。
- `service-worker-regression.log`85项通过（最终重复事件修复之前），包含现有10项真实进程、调度、项目API和事件合同。`service-regression.log`52项通过（同样在最终重复事件补充之前）。这些数字为重叠测试批次，不相加当作唯一用例数。
- 新服务测试中的2项使用真实项目worker＋SQLite＋ASGI路由，验证密码内容不出现在持久事件、脚本领取、请求失效、回执、重复请求和操作视图。输入/JS回复由测试给定，**不是正式renderer执行，也不是TCP/Electron E2E**。
- 测试搭建时出现过导入不存在的测试序列化函数、使用未启动的0代次，以及操作视图既有字段投影不匹配；前两项按真实实现修正测试，后一项按既有公开定位器调整新增契约，不放宽断言。
- `service-ruff.log`、`service-mypy.log`（9生产文件）、`service-types.log`、`service-openapi.log`通过。未重做冻结/目录包，不沿用前一批包作为新代码证据。

## 上一服务检查点的剩余项（由下方最新检查点更新）

- 主窗口复用输入对话框及JS Worker执行工具，不能依赖Studio窗口仍打开；项目切换/归档/停止要撤销旧请求；JS不得因重连重放。
- 请求读模型与主窗口消费的完整联调、真实网络断流/回执丢失、正式鉴权入口及停写UI行为；目前后端归属/代次/领取/幂等已专项验证，不能等同所有权限和生命周期正式验收。
- 正式项目任务入口、真实输入及renderer脚本执行、开发和冻结/正式目录包验收。当前目录182节点未改变，项目剩余仍31；本批不提前放开两个项目节点。
- 没有修改真实用户数据库、启动主应用或干扰其它工作树。完整目标（213节点、22外部/原生项、项目数据统计等）继续保留，未测平台不标通过。


## 主窗口接入与真实网络检查点（2026-09-24，未关闭正式验收）

- `ProjectInteractionHost` 在主窗口路由之外复用原 `InputPromptDialog` 和 `runJsScript`，项目任务不再依赖 Studio socket。通过现有 API client 每秒发现待处理请求，随后按项目/任务/运行/代次读取请求；没有新 SSE 或执行器。普通重连保留已领取脚本，恢复已提交输入只查询原命令。
- 增加 `GET /api/v1/project-run-interactions` 和有类型的请求读模型。详情仅活跃内存/`no-store`；不在普通事件保存默认值、标题、脚本或变量。无效回执原先会无限轮询（`receipt-red.log`），现在只有网络/超时/服务暂不可用会查询重试，身份不符明确失败。
- 文件/目录选择沿既有宿主 IPC：只允许已登记主窗口/Studio主frame，返回前复核工作区/服务身份。主应用和Studio共享同一适配入口；浏览器Mock仍沿原HTTP合同。原生选择本身尚未实测。
- 仅在 Studio 仍存在且不是退出应用时，正常关闭主窗口会隐藏而保留原 renderer；原JS Worker不转交、不重放。Studio关闭后恢复隐藏主窗口，输入到达时显示主窗口；真正退出不被隐藏策略拦截。原生正常关窗证据尚未通过，不能用单元测试或destroy替代。
- 目录新增 `input_prompt` / `js_script`，注册数184/213；29项仍未注册。这两个节点的项目正式验收未关闭，因此项目接入未核销仍31项，不能把注册数当验收数。历史Studio独立运行证据不改变。

### 最终专项证据

- `frontend-final.log`：86项/8文件，1.86秒；包含原输入验证/回传、路径选择、主窗口恢复、JS领取/取消/错配回执、宿主权限及关闭保留规则。组件JS使用可控替身，不冒充真实renderer执行。
- `main-app-regression.log`：51项既有App、项目导航、输入HTTP和路径合同，15.55秒（早于最后宿主关闭/回执修正；受影响8文件随后按上项重跑）。
- `backend-worker-service.log`：25项，31.75秒，包含10个实际项目worker；这批2个接口场景仍为ASGI。随后升级原场景为真实loopback TCP。
- `tcp-sse-final.log`：39项，12.64秒，包含输入/JS两个真实worker＋SQLite＋Uvicorn TCP接口，以及两次SSE连接完整读取/按序号续读、敏感内容不落普通事件；另外覆盖调度回归和正式应用鉴权/停写。JS回复仍由测试给定，未假称Electron执行。原SSE与列表的时间序列化不一致由 `tcp-sse-red.log` 记录；复用同一 `ProjectRunEventView` 后内容严格相等，没有放宽比较。
- `events-regression.log`：8项原项目事件合同回归，1.73秒。类型、ESLint、OpenAPI、结构检查和renderer/main/preload构建日志随附；构建30.45秒。冻结/目录包状态以下方最终记录为准。

### 正式UI当前阻塞及恢复入口

- `../formal-project-interaction-electron-rBdQBJ`：验收脚本使用错误模块中文名而失败，按原UI“用户输入”修正，没有改产品名称来迎合测试。
- `../formal-project-interaction-electron-eZXZwM`：真实点击/输入已创建并保存用户输入→JS脚本→打印日志三节点；正常关窗阶段未通过。`native-ui-blocker.json` 记录Computer Use返回Mac已锁定，已请求用户手动解锁。未使用destroy绕过这项门槛。
- 恢复命令：`AUTOFLOW_PROJECT_INTERACTION_TASK=1 node scripts/smoke-studio-backend-b3-control-flow.mjs`；正式包使用同脚本 `--executable`。需继续验证真实输入21→原JS Worker输出42/计数1→正常主窗口关闭仍继续→持久日志/输出→正常关Studio后主窗口恢复。原生文件/目录选择、取消/停止及相应生命周期仍需真实UI证据。
- 代码和注册已实现不等于项目节点通过。本批真实用户数据库未触碰；全部失败证据保留。Windows/macOS Intel未实测；外部服务、剩余节点、项目统计/数据/生命周期总目标不缩减。


### 冻结与打包结果（同一检查点完成）

最终生产源码冻结158.49秒、macOS arm64目录包生成成功（没有签名证书，未签名）。`verify_frozen.py`逐模块比较11个完整模块的字节码/常量/名称，冻结目录及正式包内后端均匹配，见 `frozen-code.log`、`packaged-code.log`；哈希见 `build-artifacts.json`。这证明打包内容，**不证明锁屏状态下未执行的正式包UI入口**。Ruff/4文件mypy最终通过，见final-ruff/final-mypy。没有因此关闭任何正式UI门槛。

证据日志仅去除行尾/文件尾空白以通过仓库diff检查，失败内容与断言全部保留；原始命令输出仍在本机/tmp。
