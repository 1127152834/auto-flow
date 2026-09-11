# 模型分支合入 baseline

- 日期：2026-09-12
- 状态：confirmed；用户授权合并，隔离合并验收通过。
- 输入：baseline b45ca84、model fe3672a；共同祖先ad08bdb。合并保留双亲历史，不squash、不推送。
- 隔离：在`autoflow-merge-models`处理冲突、安装独立依赖、测试和打包；验收后的提交用于快进baseline。
- 冲突解决：保留proxy/kernel装配与IPC，添加model服务；共享HTTP客户端支持两个现行错误信封；重新生成OpenAPI；记忆与文档按段落合并。
- 迁移：新增0003_merge_proxy_models汇合两边0002；不改写已执行迁移。空库、0001、proxy0002、model0002四条升级路径通过且记录保留。
- 验证：接入浏览器06153ca及代理预算修复4a91407后304后端、128前端、7脚本测试通过；ruff/mypy/typecheck/lint/OpenAPI/构建通过；macOS arm64开发与打包Electron完整模型流程、子进程清理通过。
- 工作区保护：合并前记录原目录12个未提交/未跟踪文件的SHA-256；Vite已有改动与合入内容字节一致，原automation/浏览器草稿不纳入提交。落地后由主代理核对原文件内容。
- 能力边界：未验证Windows/macOSx64、真实模型供应商和ProxyPanel实网；本次不实现其他线程尚未提交的全局页面。
- 详见 [合并验收](../../docs/migration/model-management-baseline-merge.md)。

- 并发协调：首次快进被Git因Task7未提交共享文件安全中止；随后接入其06153ca检查点，保留BrowserApiError、请求/流生命周期与ApiProvider，模型外部调用显式60秒预算。原checkout快进需等待该任务复审窗口，不覆盖正在编辑的文件。

- 最终兼容修复：保留4a91407的proxy创建连接/换Key/同步/探测60秒预算；实际共享客户端慢headers和body测试通过。

- 落地结果（confirmed，来源：Git fast-forward与SHA-256检查）：浏览器Task7最终独立复审PASS后开放共享文件窗口，原检出codex/architecture-baseline已从4a91407快进到2ae2648；fe3672a是其祖先。原20个未提交/未跟踪文件逐一SHA-256相同，index为空；既有Vite改动与目标字节相同并进入历史，其余automation/settings/浏览器草稿保持未提交。未推送远端。
