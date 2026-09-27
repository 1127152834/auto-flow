# Studio 节点真实运行 QA

- 日期：2026-09-28；状态：confirmed。
- 基线：`33ae3aa49600840b1700c83723408c494dc201a8` 的当前工作树。既有未提交改动保留；未修改业务代码或用户数据库；审计产物由主任务统一提交。
- 平台：本机 macOS 26.4.1 arm64，仓库 Python 3.11 环境。
- 结论置信度：已列实际结果为高；未执行节点与其他平台的正确性未知。

## 结论与准确计数

**节点脚本最终执行 118 个真实场景：115 通过，3 个可复现缺陷失败。** 分为 88 个生产 `WorkflowRuntime + production registry` 场景、29 个真实子进程 worker 场景，以及 1 个真实隔离 sidecar 的共享/Webhook 综合场景。最后一个场景经过 HTTP、SQLite、生产 worker 和正式 Gateway，包含 7 个节点。没有替换执行器、HTTP 响应、文件服务、图调度器或识别模型；所有文件读写和公开网络请求真实发生。

节点脚本实际触达 **129 种生产执行器类型**。另行纳入主任务完成的 **1 个打包 Electron 原生 JS 场景**和运行链代理完成的 **1 个真实浏览器综合场景**（1 任务、26 次节点访问、19 种类型、9 个实际断言全过；均不计入上述 118 个脚本场景），按类型集合并集后触达 **149 种类型**：145 种有通过证据且本组未发现失败、3 种存在已确认失败、1 种人脸识别只完成真实无脸图负样本。不能把这些类型各自的一两个场景视为所有分支、参数组合或平台全覆盖。

批准集合为 **216 种**，生产注册表为 **217 种**；唯一额外入口为 `custom_module`，批准集合没有缺失执行器。它是自定义模块的通用调用入口，有实际执行器；UI 中由 `CustomModuleList.tsx:82` 动态生成具体模块，由 `WorkflowEditor.tsx:1218` 添加，不能理解为一个没有 UI 的额外内置普通节点。合并后的 149 种包含 `custom_module`，即触达批准集合中的 148 种。另有 `group`、`note` 两种结构节点经真实画布子流程处理，未伪计为执行器完成。**本台账仍有 66 种批准节点未执行**，逐项列在 [覆盖台账](nodes/coverage.md) 和 [机器覆盖数据](nodes/coverage.json)。早期阶段提及的 65 种、125 种是当时执行覆盖数量，已由最终统计取代，均不是系统完整节点数量。这是明确的局部验收，不能宣布系统全量真实测试完成；综合类型台账已合入上述两组独立补验证据，历史运行链重复触达的同类节点没有重复计数。

`results.json` 另外保留 2 条历史 `blocked` 范围说明（JS 宿主执行、不存在的通用路径/压缩独立节点）；它们不计入 118 个执行场景。JS 边界现由主任务真实补验解除，见 [native-js-result.json](ui/native-js-result.json)；为保留原始分工记录，没有把外部补验混入脚本结果。当前脚本结果以 `results.json` 为准，最终节点覆盖以合并后的 `coverage.json` 为准，探索轮次日志不作为通过总数来源。

## 真实数据和验证方式

输入直接读取仓库 `package.json`、`apps/desktop/package.json`、`apps/backend/pyproject.toml`、`AGENTS.md`、`docs/PROJECT_STRUCTURE.md` 的内容、路径、字节数及 SHA-256。颜色转换取自正式 Studio `autoflow.css` 中的实际颜色 token。数据来源及文件散列已写入 `nodes/results.json`，未创建虚构供应商、虚构业务记录或 mock 响应。

| 真实场景 | 实际验证 |
| --- | --- |
| JSON、字典、字符串、正则、Base64、散列 | 用真实源码文本/项目元数据，和 Python 标准库独立计算结果比对 |
| 列表、统计、数学、随机 | 使用真实文件尺寸与路径清单；确定性结果独立计算，随机值校验类型、集合成员、长度及边界 |
| 表格 → CSV/XLSX | 实际增行、增列、改格、删除、清空、导出；用 `csv` 与 `openpyxl` 回读产物，比对文件路径、尺寸和内容；保留 [CSV](nodes/source-files.csv) 与 [XLSX](nodes/source-files.xlsx) |
| CSV 防公式注入 | `@autoflow/desktop` 在 CSV 输出为带单引号前缀的文本；这是保护行为，未误报为数据错误 |
| 列表文件与 Base64 文件 | 实际覆盖/追加写文件、Base64 写文件再读回，对照源文件原始 bytes；`../` 越界写入被拒绝 |
| Python/Node.js | Python 实际读取源码、生成 ZIP 并读回验散列；`run_command` 实际调用 Node.js 读取项目包名；真实异常、超时与后继不执行均检查 |
| 图控制 | `foreach + condition` 按真实文件尺寸逐项求和；`loop/foreach_dict + continue` 验证次数与跳过后继；`infinite_loop + break + stop_workflow` 验证只进入一次并停止 |
| 嵌套执行 | 正式 worker 的依赖快照机制执行 `run_workflow_file`、`custom_module`、画布 `subflow`；校验真实文件尺寸汇总返回至父图的变量和断言 |
| 文件/时间触发 | 在专用临时目录实际复制 `package.json` 触发文件监听；实际等待 1 秒定时、短 wait，以及概率 100% 分支 |
| 日志/Allure | 实际 JSON 日志输出及 Allure HTML 文件，附真实 `package.json`，回读报告中真实源文件散列 |
| 公网 HTTP | `api_request`、`webhook_request` 只读 GET IANA 保留域名页面；`api_trigger` GET PyPI 的真实 httpx 元数据、按 `$.info.name == httpx` 触发；大响应实际外置为产物，再读产物验证 |
| 真实 sidecar 共享/Webhook | 用真实 `package.json` 启动隔离 `share_folder/share_file`，HTTP 下载原始字节及 SHA 一致；Webhook 错方法 404、缺校验头 403，实际元数据 POST 200 唤醒节点并传至 JSON/日志；7 节点均有持久结果，消费后回调 404；`stop_share` 实际关闭两个自身端口 |
| 主任务原生 JS 补验 | 打包 Electron 原生编辑器拖入、编辑、保存、正式运行；生产 worker 经真实 Electron JS Gateway 返回 `navigator`/时区，和实际应用值一致；另计 1 场景 |
| 运行链真实浏览器补验 | 生产项目 worker + CloakBrowser 打开公开 example.com 和真实 TOML/JSON；读 DOM、页面等待、首末标签、刷新、前进后退、真实滚动与生产截图，正文匹配磁盘原文，截图由正式产物接口下载校验；19 种节点/26 次访问只算 1 个独立综合场景 |
| 本地 OCR | 用仓库历史真实应用截图 `docs/migration/automation-studio-m5-retest-2026-09-13/packaged-editor.png`，真实 EasyOCR 本地权重推理，验证识别出“保存”且文本长度大于 50；没有截取当前用户屏幕 |
| 人脸识别 | 同一真实应用截图经实际人脸模型推理，确认 `source_faces == 0`。这是无脸负样本，未验证授权真人照片的匹配精度或误识率 |

运行使用专用临时目录，工作结束后清理 worker、隔离 sidecar 和临时目录。正式 worker 事件已保留，且核对 29 个 worker 场景的事件文件存在、互不重名。共享综合场景的 HTTP、节点日志与结果完整保留在 [sidecar-results.json](nodes/sidecar-results.json)，全部 9 个内容/生命周期断言通过；共享功能通过不代表不存在访问控制风险，安全边界另见 [安全审计](security-audit.md)。共享服务器按生产实现绑定 `0.0.0.0`，测试仅使用随机端口和临时复制的公开仓库文件、通过 loopback 下载，没有影响已有共享。创建执行配置需要真实已安装内核，本场景将现有内核用 APFS clone 复制至专属临时目录用于配置校验，未启动浏览器。

本子任务没有启动 Electron；上表明确引用的 JS 与下文 Excel 问题采用主任务提供的实际打包应用证据；浏览器补验来自运行链代理的独立生产执行。[浏览器说明](runtime/browser-nodes-realqa.md) 和 [浏览器机器证据](runtime/browser-node-results.json) 已核对持久节点尝试均 succeeded、26 次访问与19种类型对应、9个断言通过、owned 进程清理为空。`screenshot` 确实是图中的 n11 节点，不是失败时自动截图。`element_exists/element_visible` 只验证真实可见元素的正向分支；未泛化为所有分支通过。其他 UI 表单/菜单/IPC/SSE/正式运行按钮覆盖仍需结合主任务报告判断。

## 已确认缺陷

### N-01 / P2：只有标题行的 CSV 被当成一条业务记录

- 位置：`apps/backend/src/autoflow/application/workflows/executors/string_convert.py:70`。
- 输入：实际源文件元数据 CSV 导出后的标题行 `path,bytes,sha256`，`hasHeader=true`。
- 预期：结果为空列表 `[]`；第一行仅定义列名。
- 实际：成功返回 `[["path", "bytes", "sha256"]]`，并报告一行。输出类型也从字典列表变为二维字符串列表。
- 原因：只有 `has_header_bool and len(rows) > 1` 才跳过表头；单行文件落入 `result = rows`。
- 影响：正常的零记录 CSV 会被下游循环当作真实记录处理，并可能造成字段取值失败或错误执行。
- 最小修复方向：有表头时始终移除首行，剩余行可以为空；保留真实标题行回归用例。
- 证据：[results.json](nodes/results.json) 中“真实 CSV 导出仅剩表头时应为空数据集”。置信度高。

### N-02 / P2：Python 脚本参数不支持带空格的真实文件路径

- 位置：`apps/backend/src/autoflow/application/workflows/executors/python_script.py:73`。
- 场景：复制真实 `package.json` 至临时 `zip workspace/package source.json`，文件模式 Python 脚本通过 `sys.argv[1]` 读取它；参数按平台正常引号语法传入。
- 预期：读取文件，输出项目包名。
- 实际：`str(script_args).split()` 按空白拆开带引号的路径；子进程收到包含开头引号的截断路径，在 `.../zip` 处失败并返回 `FileNotFoundError`。
- 影响：带空格的用户目录、文件名和普通字符串参数不可可靠使用；实际脚本存在、Python 可用，失败来自参数序列化。
- 最小修复方向：优先在契约中使用参数数组；如保留字符串字段，按目标平台解析引用与转义，不能继续无条件 `split()`。
- 证据：[真实 worker 事件](nodes/qa-065-events.json)。置信度高。

### N-03 / P3：未知 SHA 算法静默降级为 SHA-256 并报告成功

- 位置：`apps/backend/src/autoflow/application/workflows/executors/utility_tools.py:198`。
- 场景：真实 `AGENTS.md` 文本，算法配置 `sha-does-not-exist`。
- 预期：配置错误，明确拒绝执行。
- 实际：`getattr(hashlib, sha_type.lower(), hashlib.sha256)` 回落到 SHA-256，结果成功；日志仍以请求的无效算法名称宣称完成。
- 影响：导入工作流/调用边界的错误配置无法被发现，消费者可能以错误算法名称使用正确但不符合请求的散列。正式下拉列表限制选项降低了手工编辑时的触发概率，故分为 P3。
- 最小修复方向：校验受支持算法白名单，未知值失败，不静默降级。
- 证据：[results.json](nodes/results.json) 中“不支持的散列算法应拒绝”。置信度高。

### N-04 / P2：Excel 导入丢失可操作的行列错误提示

- 真实场景：主任务通过打包应用原生对话框，将实际导出的源码清单 XLSX 导入，误把文本形式的 `bytes` 列映射为数字。后端正确拒绝该类型不匹配，失败导入保持未发布且零记录；恢复为原始文本类型后，实际 5 条记录往返一致。**类型校验与失败隔离本身通过，不作为缺陷。**
- 真实持久 Operation 的错误包含 `code=INVALID_PROJECT_DATA`、`field=bytes`、`rule=type`、`reason=must be a finite JSON-safe number`、`rowNumber=2`、`columnIndex=1`。后端在 `application/project_data/excel_import.py:81` 校验单元格，`:89` 加入行列，`:120` 完整保存错误明细。
- 问题位置：`apps/desktop/src/renderer/domains/project-data/use-excel-import.ts:37` 把 Operation 错误交给 `safeProjectError`；`domains/projects/presentation-error.ts:15`、`:50` 仅按顶层错误码转换为“填写内容有误，请检查后重试”，忽略结构化 details；`domains/project-data/components/DataOperationStatus.tsx:24` 只渲染该字符串。接口没有丢失细节，展示层丢失了定位信息。
- 影响：用户知道导入失败，却不知道是哪一行、哪一列、什么字段要求不符；面对较大的真实表格只能猜测映射或反复尝试。
- 修复方向：对已知校验码安全展示白名单字段，按零基 `columnIndex` 转换为用户列号，定位“第 2 行、第 2 列（bytes）应为数字”，并回到对应列映射。保留对原始诊断文本的过滤，不直接展示任意服务端消息。`ExcelImportMapping.tsx:36` 已使用 `columnIndex + 1` 展示列号，可保持一致。
- 证据：[实际打包应用导入结果](ui/native-import.json)、[初次失败的真实 Operation](ui/native-import-initial-operations.json)、上述展示调用链。置信度高。这是独立 UI 设计缺陷，不增加 118 个节点脚本中的失败场景数。

## 未执行范围和下一步

当前本台账尚未执行的 66 种类型按先决条件分组如下。正式 JS 与19种真实浏览器类型已根据完成的独立证据合并；没有把仍在计划中的测试计为通过。

### 需浏览器或正式UI（20 种）

`click_element`, `download_file`, `drag_element`, `element_change_trigger`, `extract_table_data`, `handle_dialog`, `input_prompt`, `input_text`, `network_capture`, `network_monitor_start`, `network_monitor_stop`, `network_monitor_wait`, `ocr_captcha`, `save_image`, `select_dropdown`, `set_checkbox`, `slider_captcha`, `switch_iframe`, `switch_to_main`, `upload_file`。

### 需外部服务或账号（30 种）

`ai_chat`, `ai_classify`, `ai_dedup_semantic`, `ai_element_selector`, `ai_extract`, `ai_generate_image`, `ai_generate_video`, `ai_normalize`, `ai_route`, `ai_sentiment`, `ai_smart_scraper`, `ai_summarize`, `ai_translate`, `ai_vision`, `ai_vision_act`, `email_trigger`, `firecrawl_crawl`, `firecrawl_map`, `firecrawl_scrape`, `notify_telegram`, `notify_webhook`, `proxy_change_ip`, `proxy_change_location`, `proxy_query`, `send_email`, `ssh_connect`, `ssh_disconnect`, `ssh_download_file`, `ssh_execute_command`, `ssh_upload_file`。

### 需设备或原生交互（16 种）

`face_trigger`, `gesture_trigger`, `get_clipboard`, `hotkey_trigger`, `image_trigger`, `lock_screen`, `mouse_trigger`, `play_sound`, `printer_call`, `set_clipboard`, `shutdown_system`, `sound_trigger`, `start_screen_share`, `stop_screen_share`, `system_notification`, `text_to_speech`。

### 本机安全执行、无需上述外部条件的剩余项（0 种）

原先遗漏的 `share_file`、`share_folder`、`stop_share`、`webhook_trigger` 已通过真实隔离 sidecar 补齐；`js_script` 已由主任务通过正式 Electron 补齐，另19种浏览器节点由运行链代理实际补验并纳入台账。这里的“0”仅针对按当前先决条件分类的节点类型，不表示所有参数、异常路径、平台和长期运行情形已经穷尽。

原生设备与外部账号项需要分别准备真实目标和授权；没有实际发送邮件、Telegram、通知 Webhook，没有操作打印机、全局键鼠、关机/锁屏，也没有改系统剪贴板。没有启动摄像头、麦克风或屏幕分享。

## 复现与证据

在仓库根目录运行；命令包含已知失败，因此前两个命令预期以状态 1 结束，继续执行下一个命令以完成整组采集：

```sh
PYTHONPATH=apps/backend/src apps/backend/.venv/bin/python docs/qa/2026-09-28-system-audit/nodes/run_real_nodes.py
PYTHONPATH=apps/backend/src apps/backend/.venv/bin/python docs/qa/2026-09-28-system-audit/nodes/run_more_nodes.py
PYTHONPATH=apps/backend/src apps/backend/.venv/bin/python docs/qa/2026-09-28-system-audit/nodes/run_sidecar_nodes.py
PYTHONPATH=apps/backend/src apps/backend/.venv/bin/python docs/qa/2026-09-28-system-audit/nodes/build_coverage.py
```

`run_more_nodes.py` 可传名称子串选择性复核，例如 `PyPI 真实画布`；保留未选中的前次结果。每次 worker 使用唯一 runId，防止重试覆盖其他场景证据。所有最终脚本机器结果见 [results.json](nodes/results.json)，逐节点状态见 [coverage.json](nodes/coverage.json)。`build_coverage.py` 对独立 JS/浏览器证据读取真实终态与节点尝试后合并，不改变脚本118场景基数。

本子任务未执行全量 pytest、Windows、macOS Intel 或长期压力测试；Electron/打包环境仅包含已明确引用的主任务补验，不能泛化为全部原生节点通过；已有单元测试不包含在这里的“真实测试通过”计数中。本次只生成测试与审计产物，未擅自实施修复。
