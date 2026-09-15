# F2.2 共享高级配置实际入口核销

2026-09-15。已完成本切片组件/规则与 Mock 保存验收，非整个节点配置或 Electron 验收。逐项 ID、前置、操作、请求与断言见 `evidence/f2-common-advanced/cases.json`。

## 本切片已核销

- 实际 ConfigPanel 的备注、错误处理四模式、目标排除自身、错误重试次数/间隔、耗尽后停止/继续。
- 超时后三选项、重试耗尽双选项、固定/指数退避及次数/间隔关联显隐；隐藏字段保留。
- 修改进入共享历史，撤销/重做/导出重开；实际 Mock 保存读取后重新挂载回显；切换节点后的旧字段失焦不写入新节点。
- 外层超时/次数/延迟非法原文按既有 NumberInput 行为保留并提示。
- 模块条错误处理的两数值输入与配置面板使用同一个已有 NumberInput。变量引用、非法原文不转换成 NaN。

## 已确认必要适配

冻结 `reference/WebRPA/frontend/src/components/workflow/ConfigPanel.tsx` 的 errorPolicy.maxRetries / interval 在 onChange 中用 Math.max 强制数字；源模块条使用 parseInt / parseFloat。迁入后这与已批准的“NumberInput 保留未完成草稿和变量引用”冲突：真实 ConfigPanel 输入 `1abc` 将 NaN 写入文档，两项红测实际失败。

本次仅移除两处强转，模块条复用已有控件；ErrorPolicy 两字段类型容纳 number|string，不修改 Store 历史/保存逻辑，不用类型断言掩盖错误。既有 staticNumberPreflight 在启用 retry-self/retry-from 时检查嵌套字段，分别要求次数至少1的整数、间隔非负有限数，问题定位 `data.errorPolicy.maxRetries/interval`。停/继续时不校验未启用字段；变量引用仍交给服务，不增加表达式执行器。属于 AutoFlow 必要适配，不是改变错误处理模式或另造执行器。

同批网页字段核销发现的索引要求接入同一预检：switch_tab 的默认/index模式 tabIndex、switch_iframe 默认/index模式 iframeIndex 为非负整数；wait_element.waitTimeout 为非负有限数。非索引模式忽略遗留索引，模板保留，超时允许小数。另外 wait_page_load.timeout 依照表单 min=1 单独校验，0拒绝、1及2.5通过。合计对应14项规则测试；网页节点界面入口由并行网页专项验收，不在此重复声明。

## 实际验证

- 初始23项高级分支测试通过；补非法值红测后23通过/2失败，失败值为NaN，见 before.log。
- 修复后的54项新测试与现有数值/启动预检联合：3文件107项通过，4.26秒，见 after.log。
- 首次联合虽然92断言通过，但旧 static-number-preflight 测试挂载新增 Profile 选择器时缺 localStorage，产生1个未处理异常，未计作通过。仅补其 hoisted 存储夹具，保留原断言，最终联合无该错误；原失败见 related-initial-error.log。
- 本次6文件ESLint通过，结果见 lint.log。最终全局TypeScript检查只有并行CredentialSettings.tsx:107联合类型推断错误，见types.log；本切片文件未报告类型错误，但不宣称全局类型通过，由主任务整合修复后重跑。全量回归与构建由主任务在合并功能块后统一执行，此处未重复运行。
- 没有正式Electron或真实浏览器自动化证据。本切片保存使用真实前端组件与Mock服务处理器，不代表真实后端持久化。
