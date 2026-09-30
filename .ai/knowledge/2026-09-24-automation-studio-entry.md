# 自动化的 Studio 入口

日期：2026-09-24。状态：confirmed。来源：用户截图、实际窗口可访问性状态、AutomationEditor禁用表达式、workflow_catalog_router的projectId过滤及本机回归。

关联工作流来自 Studio 持久化的当前项目文档。旧入口在未选择workflowId时disabled，用户无法先新建工作流；不是点击事件或窗口IPC失效。用户授权将入口移到关联选择框之后。

在codex/automation-studio-entry（基于最新baseline1bc6b24d）完成有界修复：移除页头重复按钮；无选择时允许传undefined复用既有项目Studio入口，有选择时打开文档；保存/恢复/只读禁用仍保留。主窗口focus重读工作流目录，保持表单草稿，不增加轮询或第二套状态。

先得到3失败/20通过，再得到23通过；相关155项/16文件、typecheck、lint、build通过。隔离Electron+真实后端操作验证：新建自动化空选择打开Studio，Studio新文档保存，原生主窗口focus后下拉出现并选中该文档，草稿名称保留。截图已目视核对。当前用户窗口也已热更新并验证能打开项目Studio，热更新重置的可见名称“测试”已恢复。

证据：docs/project-management/implementation/pm9/automation-studio-entry.json；临时可复跑脚本与截图在.tmp-tests/automation-studio-entry/。未修改后端契约、用户已保存的自动化或主目录并行Studio；releaseAccepted仍false。
