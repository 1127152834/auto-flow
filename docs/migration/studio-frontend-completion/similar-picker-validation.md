# 相似元素拾取前端闭环

## 实现与合同

沿用冻结reference/WebRPA/backend/app/api/element_picker.py的selected/active/similar包络，pattern/count/indices/minIndex/maxIndex/selector1/selector2字段。发布schema并生成前端类型；有效结果需可替换的{index}、非负安全整数范围和正匹配数，索引不能超范围。无效响应在API边界拒绝，不进入应用对话框。

Mock新增受控的四个相似元素场景，只有拾取开启时可触发；重复查询结果不消费，停止/重新开启清空旧结果，单选与相似结果互斥。该非破坏查询是前端恢复合同，真实后端仍须对应实现。场景按钮只在开发装配，不进入正式节点组件。ConfigPanel现能显示相似轮询业务错误并在后续轮询恢复。

## 验证

新增内存/HTTP协议2项和畸形响应6项，加原属性上下文及新增业务错误恢复合计28通过。新后端12项契约通过。实际UI审查→应用→一次撤销/重做→保存刷新重开通过，见evidence/f4-similar-picker/browser.md。

初次协议测试因缺Mock场景失败；接入生成类型后旧AutoBrowser生命周期夹具缺minIndex/maxIndex导致类型失败，补齐源接口字段，保留关闭后迟到响应不能复制/日志的断言。未降低字段约束。

全量前端142文件1715项、后端502项通过；类型/lint、Ruff/mypy、构建、21脚本及OpenAPI一致性通过。全局会话归属、取消清理重试、错误日志去重、真实定位及正式Electron仍未全部交付；不因此标F4完成。
