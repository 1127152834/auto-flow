# PM9 XE-G07 窗口子范围与实现缺口校正

日期：2026-09-23。状态：confirmed（现有能力和缺口核对）；W1–W3为proposed等待确认。来源：项目AU-06/XE-G01/XE-G07、Studio旧R7/R9和迁入规格、632caf6d代码、真实打包探针及 `pm9/studio-window-follow-through.json`。

在已有 `checkStandaloneStudio` 后增加独立命名的 `checkStudioWindowLifecycle`，继续复用生产包/HTTP/worker/CDP/真实Electron窗口，不另造执行器或测试服务。直接断言：Manager重复打开恢复同一最小化窗口且仍只有一窗；Studio renderer不能冒充Manager发起open；同一sidecar；未保存编辑发起原生close后可取消，文档revision未改变；再次close选择保存后继续，既有文档仅revision+1且保留项目授权/参数；重新打开窗口并手动选择同一文档，编辑保持且零Project/只原completed Run。

一次定向打包探针通过；主进程11项（1.19秒）、脚本101项、映射检查4项通过。包含新增窗口断言的完整原版桌面脚本通过；1004条真实worker日志32944ms、五路万行55424ms/0busy、固定1000条合成输入60026ms/最大滞后35ms，均是本机单次观察，不是吞吐承诺。Electron API close/minimize不是物理OS手势；显式重开文档不是自动恢复会话，也不是运行中项目Task两个页面事实一致。

源码事实纠正：`openAutomationStudio()`没有目标参数；控制器只有单独窗口，没有project/automation会话或presentationMode；自动化详情/目录没有指定文档编辑与返回入口。因此AU-06、XE-G01、XE-G07存在implementation_missing，不能继续仅标缺端到端或实机证据。旧计划的停靠要求与新迁入架构边界需明确衔接。完整W1–W3规格和30–90分钟切片已写入docs/superpowers；依据AGENTS架构变更规则提出确认，批准前未实施，不重复索取既有C/R/D1授权。

251条台账现为249条有范围断言、2条未定位（DATA-LIFE-01和DATA-SH-03），206 partial/45 planned/0 verified。73条缺失预定路径全部定位到子范围断言；预定路径未伪造补文件。重叠缺口计数：245生产证据、13实现缺失、10缺测、24外部待验。新增断言不包含在已启动632caf6d矩阵35881272086；不为测试文档增量取消重跑该矩阵。生产代码不变，主目录Studio工作未改；releaseAccepted=false。
