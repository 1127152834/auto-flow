# R1 连续操作用例与证据登记

- 日期：2026-09-13；状态：confirmed（仅所列执行报告与行为事实）。
- 本文是证据索引，不是 R1 总体验收通过书。两份 R1 报告均为 `result=passed`、`visualReview=pending`；已配置筛选截图目前复审为 **70 分，正在修复，视觉待复验**（来源：主协调任务本次交接，不是 JSON 自动评分）。后续修复不能追溯改变本轮截图或版本。
- 用户手测：未执行。Windows：未执行。其他架构、打包应用：本证据集未验证。
- 阅读方式：每项的版本引用下方证据批次，实际结果仅限明确写出的断言；截图用于定位状态，存在截图不等于视觉通过。未有独立截图的步骤明确标注“报告断言”。

## 证据批次、版本与执行方式

| 批次 | 报告与时间（UTC） | 版本与环境 | 证据类型、边界 |
| --- | --- | --- | --- |
| A | [run-2ZtfTu](../r1/runs/run-2ZtfTu/result.json)，13:43:51.591 | HEAD `25e7d330f4d051c9732b9334a22f9591ccf4fdaa` **加报告列出的未提交文件**；darwin/arm64；script SHA `854f3eb6dcf8adb259270465646c2932f2ce21b2628e9921645358a90e1a4a03` | 自动真实 Electron UI；小样本由 UI 建立；分页 fixture 经真实 HTTP；读取/丢响应由当前隔离 renderer 注入；导出保存面板返回值注入。 |
| B | [run-ifBsTk](../r1/runs/run-ifBsTk/result.json)，13:43:47.709 | 同一 HEAD 加未提交文件；darwin/arm64；script SHA `ef92f25f9837c048b39cc26f5e3eb117d6b68fe52007c0b67f6c75268e063d01` | 目录专用真实 UI 操作；长名项目为 API fixture，不冒充 UI 创建。 |
| C | [run-aiFSoY](../../../../migration/project-data-directory-qa/run-aiFSoY/result.json)，13:33:47.174 | darwin/arm64；报告**未记录 HEAD、脚本或构建哈希**，不补写推定版本 | 真实 UI、HTTP 与持久事实；包括竞争写入及丢回执恢复；不覆盖 Excel、批状态、Sheets、执行。 |
| D | [run-X0tkxr](../../../../migration/pm2-detail-qa/run-X0tkxr/result.json)，13:34:42.953 | 报告未记录 HEAD、构建哈希、platform/arch；不据邻近运行推定 | renderer UI、IPC、HTTP、SQLite、工作簿 I/O 为真；系统打开/保存面板结果注入；不是原生面板操作证据。 |
| E | [run-fUMbE7](../../../../migration/pm2-native-picker-qa/run-fUMbE7/result.json)，13:39:36.385 | darwin/arm64；报告未记录 HEAD 或构建哈希 | 未改写的 macOS 原生打开/保存面板，由本次 UI 操作者操作，真实 IPC 与令牌登记；**不是用户手测**，未验证原生保存发布。 |

A/B 的桌面构建 SHA 均为 `76c8ec8d00f9d3f0dd289b08bf0bf91746d795a41ebef3b3dae895e0dcf7cf65`，脚本 SHA 不同，分别引用原报告；不可合称同一脚本快照。A/B 使用 CDP 1440×1024 桌面视口覆盖；200% 为 720×512 逻辑视口、DPR 2，不将物理窗口尺寸冒充该视口。

步骤依据 [qa-project-alignment-r1.mjs](../../../../../scripts/qa-project-alignment-r1.mjs) 的 `visualDirectoryFlow`、`uiDataFlow` 与自动主流程，运行身份以报告哈希为准；当前脚本链接可能随修复变化。C/D/E 的步骤是报告明示操作的复现摘要，不声称已还原未登记的每次点击。

## 项目目录连续用例

| 用例 / 版本 / 类型 | 前置与步骤 | 预期 | 实际与截图 |
| --- | --- | --- | --- |
| A01 / A / UI | 工具创建空隔离工作区；进入项目目录；创建 R1手建A、R1手建B，依次打开 A 再 B，返回最近。 | 空态可进入创建；最近顺序为 B、A。 | 行为通过；[空态](../r1/runs/run-2ZtfTu/r1-a-empty.png)、[最近](../r1/runs/run-2ZtfTu/r1-a-recent.png)。视觉待复验。 |
| A02 / B / UI + 几何断言 | 创建“内容采集项目”“客户跟进项目”；依次打开；检查卡片图标、信息、更多菜单。 | 最近按访问排序；图标在信息左侧、菜单在卡片右上；单一主标题，无页面横向溢出。 | 报告行为/结构断言通过；[最近](../r1/runs/run-ifBsTk/VR-A01-recent.png)。 |
| A03 / B / UI | 在最近目录打开“更多客户跟进项目操作”→编辑项目→取消。 | 打开编辑表单，路由不变。 | 报告断言通过；无该表单独立截图，不以最近目录图代替。 |
| A04 / B / API fixture + UI | API 建立 36 个 🧪 的未访问项目；进入全部；搜索“不存在的资料”；清空搜索；返回最近。 | 全部可见未访问项目，最近不包含它；无匹配可恢复。 | 通过；[全部](../r1/runs/run-ifBsTk/VR-A02-all.png)、[无匹配](../r1/runs/run-ifBsTk/VR-A04-no-match.png)。 |
| A05 / B / API fixture + UI + 几何断言 | 从全部打开长名项目，再回最近；设置 200% 缩放并滚至卡片。 | 长名实际触发省略，完整 title 保留；布局不撑宽。 | 通过，断言包含 scrollWidth 超出 clientWidth 及 ellipsis；[200%](../r1/runs/run-ifBsTk/VR-A01-recent-200.png)。 |
| A06 / A / API fixture + UI | 已有两个 UI 项目；API 新建 52 个 R1分页项目；目录搜索 R1分页；点击下一页。 | 第一页 50 张卡，第二页 2 张。 | 50/2 断言通过；[第二页](../r1/runs/run-2ZtfTu/r1-a-all-page2.png)。API 准备不计为 UI 创建通过。 |

## 数据目录、记录与查询连续用例

| 用例 / 版本 / 类型 | 前置与步骤 | 预期 | 实际与截图 |
| --- | --- | --- | --- |
| B01 / A / UI | 打开 R1手建A→数据；从空态创建“资料库”和带较长说明的第二张本地表；每次返回目录。 | 空态明确；真实创建后可打开并显示两张卡。 | 行为通过；[空态](../r1/runs/run-2ZtfTu/r1-b-empty.png)、[两表](../r1/runs/run-2ZtfTu/r1-b-two-local-tables.png)。卡片视觉仍须复验，不从截图文件名推断对齐通过。 |
| B02 / A / UI + GET 核对 | 打开资料库→字段；建立标题、文章链接、发布日期、已检查、优先级；状态页创建已核对、待补充；记录页创建三条。 | 五字段四类型可录入；记录写入真实服务。 | 流程通过；fixture 包含 Unicode、长文本、空字符串、日期清空、布尔及数字。报告只明确核对三条记录及状态数量，未对每个边界值独立 GET 等值断言；[记录](../r1/runs/run-2ZtfTu/r1-c-business-records.png)。 |
| B03 / A / UI + DOM 断言 | 完成第三条记录创建；等待成功通知；截图后再次检查。 | “记录已创建”成功通知真实存在，不误拍已退出通知。 | 前后存在断言通过；[通知](../r1/runs/run-2ZtfTu/r1-d-record-created-toast.png)。样式视觉待复验。 |
| B04 / A / UI + GET 核对 | 在“温室管理清单”行修改状态为已核对；保存。 | 显式改变该记录业务状态；其他记录维持未设置。 | GET 三条记录，其中一条 statusId 非空；[记录](../r1/runs/run-2ZtfTu/r1-c-business-records.png)。该断言不单独证明非空状态 ID 的名称映射。 |
| B05 / A / UI | 点击选择本页记录→观察数量→清空选择。 | 显示已选择 3 条，随后可清空。 | 通过；[已选择](../r1/runs/run-2ZtfTu/r1-c-selected.png)。 |
| B06 / A / UI + 几何 | 有五个业务字段；测量记录身份表头；隐藏全部业务列后再测量；逆序勾回全部字段并应用。 | 两种布局身份列均为 112px；恢复所有列不错误显示已应用标记。 | 两次实测均 **112px**，恢复 marker=false；[普通几何](../r1/runs/run-2ZtfTu/record-identity-geometry.json)、[零列几何](../r1/runs/run-2ZtfTu/zero-column-geometry.json)、[零列截图](../r1/runs/run-2ZtfTu/r1-c-zero-business-columns.png)。 |
| B07 / A / UI + 几何 | 在记录页依次打开筛选、排序、显示列。 | 浮层宽度不超过 512/400/288px、高度不超视口，主内容宽度不变。 | 宽度实测 512/400/288px，高度 289/212/304px，主区均 1280px；[筛选几何](../r1/runs/run-2ZtfTu/popup-筛选-geometry.json)、[排序几何](../r1/runs/run-2ZtfTu/popup-排序-geometry.json)、[显示列几何](../r1/runs/run-2ZtfTu/popup-显示列-geometry.json)；[筛选图](../r1/runs/run-2ZtfTu/r1-c-business-筛选.png)、[排序图](../r1/runs/run-2ZtfTu/r1-c-business-排序.png)、[显示列图](../r1/runs/run-2ZtfTu/r1-c-business-显示列.png)。 |
| B08 / A / UI + 焦点断言 | 筛选浮层打开内部 combobox；连续按两次 Escape。 | 第一次保留外层筛选；第二次关闭外层，焦点返回筛选按钮。 | 断言通过；截图为上项外层状态，无两次 Escape 独立截图。 |
| B09 / A / UI 状态捕获 | 打开筛选→添加字段条件→运算符包含→填写温室→截图→取消；打开排序→添加排序→截图→取消。 | 能建立未应用草稿并取消，不据此宣称复杂查询已提交。 | 两个草稿状态已捕获；[已配置筛选](../r1/runs/run-2ZtfTu/r1-c-filter-populated.png) **70分、修复中、视觉待复验**；[排序草稿](../r1/runs/run-2ZtfTu/r1-c-sort-populated.png)。此用例没有“应用该高级筛选后 GET 结果正确”的断言。 |
| B10 / A / API fixture + UI | API 在 R1分页001 建立分页资料库、一文本字段及 120 条温室/花园交替记录；从目录点击项目→数据→打开表。 | 正常显示记录；表头处于紧凑预算。 | 表头 top≤380px 断言通过；[目录](../r1/runs/run-2ZtfTu/r1-b-directory.png)、[记录](../r1/runs/run-2ZtfTu/r1-c-records.png)。 |
| B11 / A / API fixture + UI | 输入文本搜索“温室”，比较输入前后 tbody；点击搜索记录。 | 输入不立即查询；提交后出现温室记录且无花园记录。 | 页面内容断言通过；本步骤无独立搜索结果截图，结果另由 B12 工作簿核验。 |
| B12 / A / UI + 注入面板 + 文件核验 | B11 已应用；导出 Excel→当前筛选结果→选择保存位置；面板返回工具路径；openpyxl 读取输出。 | 输出仅 60 条温室记录。 | 61 行含表头，60 条记录首列均以温室开头；报告断言通过。无独立工作簿截图；原生保存面板未在此执行。 |
| B13 / A / UI | 显示列取消标题→取消；再次取消标题→应用显示列；最后恢复。 | 取消不生效，应用才隐藏。 | 表头存在/不存在断言通过；[显示列](../r1/runs/run-2ZtfTu/r1-c-显示列.png)仅定位对应面板。 |
| B14 / A / UI + 缩放断言 | 100% 及 200% 依次打开三种查询浮层、按 Escape 关闭。 | 无应用全页横向撑宽，搜索与筛选按钮不重叠。 | 流程断言通过；[筛选200%](../r1/runs/run-2ZtfTu/r1-c-筛选-200.png)、[排序200%](../r1/runs/run-2ZtfTu/r1-c-排序-200.png)、[显示列200%](../r1/runs/run-2ZtfTu/r1-c-显示列-200.png)。不等于所有浮层内容视觉已验收。 |

## 故障、恢复与隔离连续用例

| 用例 / 版本 / 类型 | 前置与步骤 | 预期 | 实际与截图 |
| --- | --- | --- | --- |
| C01 / A / 真实进程重启 | 保留搜索后的表；重启 sidecar 并等待 ready；随后完整关闭并重新启动 Electron；回项目目录。 | 表记录恢复，最近访问事实持久化。 | 报告通过；[重启后](../r1/runs/run-2ZtfTu/r1-after-restart.png)。 |
| C02 / A / 真实工作区切换 | 原工作区已有 54 个项目；切工具创建的第二工作区，再切回。 | 第二工作区零项目，原工作区恢复 54 个。 | 两次 GET total 断言通过；无单独切换截图。 |
| C03 / A / renderer 故障注入 + UI | 保存当前目录内容；注入一次读取失败并刷新；再注入读错误直至错误态；再次刷新恢复。 | 自动重试可恢复；错误态仍保留上次成功内容。 | 注入次数、旧目录全文一致及错误消失断言通过；[读取失败](../r1/runs/run-2ZtfTu/r1-read-failure.png)。这不是服务真实宕机证据。 |
| C04 / A / 回执丢失注入 + GET | 注入提交响应丢失；UI 创建 R1响应丢失；见核对保存结果后 GET；点击核对并再次 GET。 | 同一操作恢复且不重复插入。 | 两次项目 total 均为 1；[待核对](../r1/runs/run-2ZtfTu/r1-lost-response.png)。 |
| C05 / A / 真实竞争写入 + UI | 编辑项目留草稿；API 用当前修订竞争更新；UI 保存；显式基于最新内容重新编辑并保存。 | 409 保留输入；显式处理后才能保存。 | 草稿字符串及表单关闭断言通过；[冲突](../r1/runs/run-2ZtfTu/r1-real-conflict.png)。 |

## PM2 既有能力回归补证

以下各项是对应报告登记的真实回归，不扩大为 R1 新版视觉通过。C/D/E 缺少版本哈希，后续若需严格绑定提交，应重新采集带 provenance 的报告，不能用时间邻近填补版本。

| 用例 / 版本 / 类型 | 前置与步骤 | 预期 | 实际与截图 |
| --- | --- | --- | --- |
| P01 / C / UI + HTTP | 空数据目录创建本地表；编辑时制造竞争版本；显式加载后重存。 | 创建进入记录路由；冲突保留草稿。 | 报告通过；[空态](../../../../migration/project-data-directory-qa/run-aiFSoY/empty.png)、[表冲突](../../../../migration/project-data-directory-qa/run-aiFSoY/conflict.png)。 |
| P02 / C / UI + HTTP | 创建字段，确认真实影响后编辑；创建、编辑业务状态。 | 字段影响需确认；编辑状态定义不改变记录状态。 | 报告通过；无字段/状态定义独立截图，后续持久内容见[记录](../../../../migration/project-data-directory-qa/run-aiFSoY/records.png)。 |
| P03 / C / UI + HTTP | 创建并编辑记录；竞争写入后显式重载；显式修改记录状态；尝试删除被引用状态，再删除无引用状态。 | 记录冲突恢复；引用中状态不能删除，无引用状态可删。 | 报告通过；[记录冲突](../../../../migration/project-data-directory-qa/run-aiFSoY/record-conflict.png)、[删除被阻止](../../../../migration/project-data-directory-qa/run-aiFSoY/status-delete-blocked.png)。 |
| P04 / C / UI + HTTP | 对选定记录确认删除影响并删除；随后读取五个实际页签；设置页编辑表描述。 | 只删除目标记录，保留另一条；各页签显示持久事实。 | 报告通过；[记录](../../../../migration/project-data-directory-qa/run-aiFSoY/records.png)。无每个页签独立截图。 |
| P05 / C / 回执故障 + 重载 | 真实创建已完成但回执丢失；renderer reload 后恢复原操作。 | 不重复插入。 | 报告通过；[持久编辑恢复](../../../../migration/project-data-directory-qa/run-aiFSoY/durable-edit-recovery.png)。 |
| P06 / C / 真重启、工作区、缩放 | 草稿中重启同工作区 sidecar；检查 Escape 保护后保存；200% 打开下拉；完整 Electron 重启；切换两工作区并返回。 | 草稿与持久内容保留，工作区隔离，放大不撑宽。 | 报告通过；[离开保护](../../../../migration/project-data-directory-qa/run-aiFSoY/leave.png)、[200%下拉](../../../../migration/project-data-directory-qa/run-aiFSoY/zoom-200-dropdown.png)、[200%记录弹窗](../../../../migration/project-data-directory-qa/run-aiFSoY/record-modal-200-percent.png)、[重启](../../../../migration/project-data-directory-qa/run-aiFSoY/restarted.png)、[返回工作区](../../../../migration/project-data-directory-qa/run-aiFSoY/workspace-return.png)。 |
| P07 / D / UI + HTTP | 选择当前页记录；耐久批量设状态，再对同一冻结选择清空状态；GET 核对。 | 所选记录状态一致改变并能清空。 | 报告通过；[终态0](../../../../migration/pm2-detail-qa/run-X0tkxr/terminal-0.png)、[终态1](../../../../migration/pm2-detail-qa/run-X0tkxr/terminal-1.png)为本批次留存，不额外猜测各文件与具体子步骤的一一映射。 |
| P08 / D / UI + 面板注入 + 工作簿 | 已应用筛选、选择一个数据列后导出；openpyxl 独立读取；再次使用同一保存目标。 | 工作簿符合筛选与选列；重复目标拒绝覆盖。 | 报告通过；[导出200%](../../../../migration/pm2-detail-qa/run-X0tkxr/export-200-percent.png)。 |
| P09 / D / UI + 面板注入 + 持久事实 | 显式现有字段映射、查看影响后替换；核对代次、状态、旧代次访问和原文件；重启 Electron/sidecar。 | 代次推进、状态重置、旧代次/键返回410；源工作簿字节不变；重启后事实保留。 | 报告通过；[替换200%](../../../../migration/pm2-detail-qa/run-X0tkxr/replace-200-percent.png)、[重连后](../../../../migration/pm2-detail-qa/run-X0tkxr/detail-after-reconnect.png)。 |
| P10 / D / 真工作簿 + UI + 面板注入 | 从目录 UI 导入真实10000行工作簿，观察50行分页并点击下一页。 | 导入完成，每页50行，翻页后首行改变。 | 报告单次实测导入 **4538ms**、翻页 **159ms**；[第二页](../../../../migration/pm2-detail-qa/run-X0tkxr/large-10000-second-page.png)。不是跨平台性能结论。 |
| P11 / E / 原生面板 + UI操作者 | 隔离项目打开原生文件面板并取消；再次打开选择 native.xlsx；打开保存面板并取消。 | 取消为成功null；选中文件返回不透明令牌与显示名，不暴露path。 | 三项断言通过；[操作后](../../../../migration/pm2-native-picker-qa/run-fUMbE7/after-native-picker.png)。截图为面板操作结束状态；没有原生保存发布，也没有用户手测。 |

## 当前未闭合项

- 已配置筛选的视觉复审70分，修复后的完整截图与视觉复验尚未登记。A/B 原报告 `visualReview=pending` 保留原状。
- 复杂高级筛选“应用后实际查询结果”、全部视觉状态及所有跨模块组合，不由草稿截图推定通过。
- 用户手测、Windows、其他架构、打包应用未执行；C/D/E 没有足够版本指纹，不能用本表宣称当前提交的严格全量复验。
- 本次仅整理既有证据，没有新执行 UI、修改原始报告、提交代码或宣布整个 R1 通过。


## 最终修复与补证

2026-09-13：筛选底栏和比较值修复提交5910508、d76cca9；独立工程复核无阻断。run-fldPXw 实际已配置筛选100%为88分、200%为87分，取消/应用可见，关闭原70分问题。原失败图保留。

最终 [run-5V7HL2/result.json](../r1/runs/run-5V7HL2/result.json) 补齐每次重启后的1440×1024视口设置及E4故障来源标记。它重复通过本文A组业务链，包含加载图、五字段四类型、null/空字符串/emoji/长值、零业务列112px、恢复所有列标记消失及200%已配置筛选底栏断言。更早run-fldPXw的重启后错误图仅为原生视口辅助记录，不作固定视口证据。

真实原生窗口200%补证见 [native-filter-200.png](../r1/runs/run-9fS4Kl/native-filter-200.png)：电脑工具点筛选、展开匹配方式，第一次Escape回组合框，第二次回筛选按钮。fixture经API准备且直接路由打开，故只登记原生交互/布局集成范围；不替代UI建表流程。该批次还真实点击浏览器/代理/模型/设置/总览及Studio入口，仅证明入口回归。
