# ProxyPanel 位置与轮换：真实操作设计

- 日期：2026-09-12
- 状态：confirmed（用户批准实施；代码及只读验收已完成，实网写入待指定目标）。
- 输入：用户要求实现“位置与轮换”，并先思考实现方式。
- 依据：当前源码、官方 [Developers](https://proxypanel.io/developers)、[IP rotation 指南](https://proxypanel.io/docs)，以及同日使用已配置连接的只读 GET 核验。
- 范围：现有代理详情内的位置与轮换；不增加页面或侧栏，不扩展白名单、用量、购买、续费和浏览器执行。

## 1. 设计时的事实（下述本地占位状态已由本次实现取代）

1. 本地 change-ip、relocate、rotation-schedule、locations 路由仍返回不可用；页面没有绑定实际操作回调。
2. ProxyOperationRow 只有基础表结构，缺少远程命令仓储、执行器和状态查询路由。前端 waitForAction 遇到 accepted 直接报“结果尚未确认”，并没有轮询实现。
3. 官方换 IP 为 POST /proxies/{id}/rotate；官方说明应读取详情，等待 current_ip 改变。
4. 指定地点为 POST /proxies/{id}/relocate，请求 location_id 来源于 GET /locations。使用稳定 ID，不提交城市显示名称。
5. 计划由 ProxyPanel 服务端执行，AutoFlow 关闭后继续运行。PUT /proxies/{id}/rotation-schedule 使用 interval_minutes 和 mode；DELETE 同路径停止计划；GET 读取现有计划。
6. 官方模式为 same_city、same_city_carriers、full_pool。当前本地 random_city/same_carrier 和秒数接口是早期占位设计，需要修正。
7. 指南描述轮换周期从每分钟到每小时；API 示例为 10 分钟。合法步长、可选周期及非空计划字段，实施前还需结合实际表单/响应核验；不把文档范围当成已实测所有整数值。
8. 官方仅明确购买和续费支持其 Idempotency-Key。不能推断换 IP/切地点也支持外部幂等。

### 当前账户的只读核验

当前 4 条 active 代理的详情均返回 bound=false、rotation_available=false、rotation_blocked_reason=not_bound；抽样轮换读取 HTTP 200，返回 {"schedule":null}。

这些事实不等于代理不能联网：此前 SOCKS5 已实际通过。也不足以证明代理永久不支持切地点/计划，更不能仅凭不同 HTTP/SOCKS5 端口推断属于某种产品类型。rotation_available 只用作其已确认语义下的即时换 IP 前置条件，不直接套用为其他操作的开关。

官方指南另外说明 legacy fleet 不提供面板轮换，但当前这些代理是否受该条限制尚未证实。应显示“ProxyPanel 当前显示代理未绑定，暂不能更换 IP”，提供重新读取状态；不显示开发术语，不建议用户反复输入 Key。

POST /start 官方用途是启动暂停代理并开始预付时间倒计时。它不是已证明的 not_bound 修复措施，本功能不自动调用它。正式写入验收需要一条满足目标操作条件、且允许短暂中断的代理；不能在当前限制条件下承诺已有 4 条代理都能操作。

## 2. 用户交互

继续使用现有详情的“位置与轮换”页签，分为三个区块。

### 当前状态

- 打开页签时独立读取远程详情与轮换计划；地点目录在打开选择弹窗时加载。
- 展示当前城市、运营商、出口 IP，以及该操作当前可用/不可用的中文原因。
- 读取失败只影响对应区块，已有概览和本地设置可继续使用；显示重试，不把旧值伪装成最新状态。

### 即时操作

- 更换 IP：确认框显示当前出口与短暂中断提示；提交后显示旋转 loading 和“正在更换 IP…”。
- 改变地点：复用 LocationPicker 视觉形式，独立提取为领域组件；提供国家/城市搜索、运营商筛选、当前地点标记和真实可用容量状态。无容量项禁用，不展示推测延迟。
- 点击切换前展示目标城市/运营商；执行期间锁定同代理的冲突操作，不锁死其他代理的只读浏览。
- 受理后可关闭详情，后台继续确认；再次打开可以恢复任务状态。
- 有明确完成证据后才显示成功，更新列表/详情/浏览器代理选项；原健康结果失效，显示未检测。可单独再检测，换 IP 成功不等于网络检测成功。
- 限流显示服务端有效 Retry-After；没有时不编造倒计时。超时显示“操作结果尚未确认，正在重新读取状态”，不得直接显示失败并自动再发一次。

### 自动轮换

| 中文选项 | 官方 mode | 行为 |
| --- | --- | --- |
| 保持城市和运营商，只更换 IP | same_city | 地点保持不变 |
| 同城切换运营商 | same_city_carriers | 指南说明单运营商城市会退回普通换 IP |
| 随机切换城市和运营商 | full_pool | 在全池选择新地点 |

- 提供启用状态、模式、以分钟为单位的周期、独立保存按钮和关闭计划操作。
- 编辑只修改本地草稿，不在切换选项时立刻发送 PUT。关闭有未保存内容时提示；保存/关闭请求期间防重复提交。
- 保存或关闭后重新 GET，确认配置匹配或 schedule=null，再显示成功。
- 若真实响应提供且验证了下次运行时间，展示它；否则省略，不由客户端推算时间。
- 明确标注“由 ProxyPanel 执行，关闭 AutoFlow 后仍会继续”。不在 AutoFlow 建立定时换 IP 循环。

## 3. 后端与接口

沿用 adapters → application → domain，Provider 负责官方 HTTP 协议，SQLite 仓储负责事务。复用系统凭据库读取 API Key，不把密钥交给前端或任务表。

### Provider 能力

扩展现有固定官方地址的传输，支持受控 GET/POST/PUT/DELETE 与 JSON；只允许预定义路径。解析详情、地点、轮换配置和命令受理/错误，不跟随带凭据的 URL，不增加旧版 URL-key 回退。

将协议样本和运行能力区分：evidence 记录证据来源，available 表示“实现已接通且当前允许操作”。实施阶段需修正前端仅以 evidence===fixture-verified 判断可操作的做法，防止只能靠先执行一次成功才能启用按钮的循环依赖。文档支持并经契约测试的写入可以进入明确标记的联调阶段，但不能冒充已通过实网验收；实际服务器阻塞条件始终优先。此项在批准后更新既有能力边界 ADR。

### 本地契约变更

| 内部接口 | 方案 |
| --- | --- |
| GET /proxies/{id}/remote-state | 新增，只读刷新当前远程状态、按操作能力及当前任务摘要；不包含凭据 |
| GET /proxy-panel/connections/{id}/locations | 实现已有占位路径，规范化真实地点与运营商 ID；返回抓取时间和过期标记 |
| POST /proxies/{id}/change-ip | 实现；expected_revision + Idempotency-Key，返回 ActionResult |
| POST /proxies/{id}/relocate | 实现；expected_revision + location_id + Idempotency-Key |
| GET /proxies/{id}/rotation-schedule | 实现，映射服务端关闭/启用状态 |
| PUT /proxies/{id}/rotation-schedule | 将占位 DTO 改成官方三种 mode 与 interval_minutes，保留 expected_revision |
| DELETE /proxies/{id}/rotation-schedule | 实现，保留版本检查和幂等键；关闭后读回确认 |
| GET /proxy-operations/{id} | 实现已有规格中尚不存在的状态查询 |

现有轮换接口尚未可用、没有已保存计划数据，不保留错误模式名/秒数的兼容层。OpenAPI 和客户端类型一起生成。远程计划没有已证实的版本号，expected_revision 只能防本地过期提交，不能承诺防止用户在 ProxyPanel 官网同时编辑；保存后必须读回实际结果。

## 4. 远程命令执行与确认

1. 请求内用短事务检查投影 revision、连接身份、目标状态及同代理正在执行的命令，登记本地 operation，再返回 202/accepted。
2. 使用由应用生命周期监管的 asyncio 任务执行 HTTP 和确认读取；复用 proxy_operations 表，不引入 Redis、Celery 或独立常驻服务。
3. 本地 Idempotency-Key + 规范请求摘要实现去重。相同键相同请求返回同一任务，键相同而内容不同返回 409；不宣称 ProxyPanel 支持这些操作的幂等。
4. 每条代理一次只发一个远程变更。数据库以唯一约束/原子条件写防并发，不只依赖前端按钮或进程内锁。网络等待期间不持有 SQLite 写事务。
5. 命令发出前持久化 running；远程 HTTP 被受理后仍为 running。有最终证据才 succeeded；明确拒绝为 failed；连接断开、响应不可解析或进程中断导致结果不明时为 unknown。
6. 同步、本地编辑、取密和操作结果回写需要统一版本校验：仅合并本操作的远程字段，保留用户本地别名/启用值；凭据替换或连接身份变化后拒绝过时结果覆盖新投影。
7. 运行时主动写命令不自动重发。启动时将遗留任务转为待核实状态，仅只读恢复确认；不把 queued/running 重放到远程。unknown 必须在再次变更前完成核实，或由用户明确确认新的操作；不能解除锁后悄悄重复发送。
8. 本地记录保留幂等键、命令摘要、连接版本和必要的非秘密目标/前置观测；对已有表增加迁移，遵循当前唯一 Alembic head，不改旧迁移。

### 完成判据

- 换 IP：提交前读当前出口，之后依据官方详情 current_ip 的变化确认；有明确返回完成语义时结合验证。字段为空或相同不伪报成功，也不保证运营商每次提供从未出现过的 IP。
- 切地点：读回的实际地点与用户选择一致，并有足以区分旧快照的新观测（例如经验证的 location_generation）；不能仅凭 HTTP 200 或 generation 增加认定抵达目标。目标匹配字段需通过真实详情/地点样本冻结。
- 保存计划：GET 读回模式与周期匹配；关闭计划：GET 读回 schedule=null。
- 写入已成功但刷新失败与写入被拒绝分开显示。不能把刷新失败当成再次 POST 的理由。
- 初始后台观察预算 120 秒是 AutoFlow 本地策略，非供应商 SLA；超出为结果待核实。轮询采用有界退避，遵守 Retry-After。前端只轮询本地任务，隐藏时暂停、恢复时补读，不额外轮询供应商。

## 5. 组件和文件职责

- application/proxies：增加一个聚焦远程操作的用例模块及受监管任务执行模块；不把新流程堆进现有大 hook/facade。
- domain/proxies：增加远程状态、地点、计划、命令结果和所需仓储/Provider 端口；不引用 ORM/FastAPI。
- infrastructure/database：在现有代理仓储与操作表上增加原子方法和迁移。
- bootstrap/proxies.py：统一装配和 shutdown/recovery；不复制另一套 Provider 或凭据存储。
- 前端先完成 RemoteProxyStatus、RotationScheduleForm、LocationPicker、ProxyOperationStatus 领域组件，再由现有详情页组合；复用现有 Button/Select/Dialog、loading 图标与 Toast。
- 单独 useProxyRemoteControls 管理读取、草稿、提交、任务恢复；旧 useProxyManagement 保持列表、本地配置与检测职责。共享查询缓存失效以现有 ApiProvider 为边界，不建立第二套全局缓存。

## 6. 验收标准

- 真实地点和已有计划可读取；任何缺失字段都不能伪造默认成功状态。
- 不支持、未绑定、暂停、过期、暂时忙、限流和网络失败按具体原因展示，不再出现开发者英文 schema 提示。
- 支持的代理可完成换 IP、指定地点切换、计划保存和关闭；确认期间有 loading，终态后恢复，关闭重开不丢任务。
- 同代理并发、重复点击、相同幂等键、进程中断、Key 替换、同步乱序均不造成重复远程写入或覆盖新数据。
- 执行结果和网络健康分离；操作后旧健康状态失效。
- 单元/契约/真实临时 SQLite/前端交互检查覆盖成功、拒绝、超时、读回失败、重启恢复；合成测试不能标为实网验证。
- 在满足条件且允许中断的代理上完成真实写入、读回和 CUA 验收后才能标记“实网交付完成”。本轮只读结果不能替代该验收。

## 7. 本轮剩余证据

尚未取得换 IP/切地点/计划保存/关闭的真实写入响应，非空计划的字段与合法周期离散集合也未验证。当前 not_bound 对切地点及计划操作的限制范围未知，不能从换 IP 标志泛化。下一阶段先完成只读与契约资料，再做实现、受控写入验收；不继续交付永久禁用的占位页面作为完成品。


## 2026-09-12 实施对齐

- 本方案已获用户“好的 开始实施吧”批准。实现和读取证据见 [验收记录](../../migration/proxy-remote-controls-verification.md)。
- 地点样本发现 243 城市记录复用 125 目标 ID；选择器显示共用目标覆盖范围，不承诺精确别名城市。目标确认采用新 generation + 覆盖城市/国家/运营商匹配。
- 周期编辑采用当前官网已显示的 5/10/30/60 分钟。非空 schedule 仍未取得实网样本；匹配测试使用明确标识的合成数据。
- 命令监管与确认在一个聚焦用例模块完成，未额外拆任务框架。增加本地最近操作读取，保证供应商读取失败时仍能找回已登记命令。
