# 页面脚本测试服务消费

日期：2026-09-14；状态：confirmed（有界前端及协议）；来源：冻结WebRPA InjectJsEditorDialog、当前代码、专项与全量测试。

将主线程伪DOM测试替换成服务请求；稳定ID、上下文修订、原请求恢复、取消及取消/完成竞争、明确Mock结果。复用现有HTTP连接与生成模型，无新执行引擎或依赖。测试记录见docs/migration/studio-frontend-completion/browser-script-test-validation.md。

真实后端、同URL epoch、工作区宿主清理未完成。下一项继续输出变量重命名与撤销一致性；不改变284节点范围，不引入i18n。无关模型/UI/教学改动保留。
