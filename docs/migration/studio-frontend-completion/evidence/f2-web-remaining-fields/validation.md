# F2.2 网页基础字段和工具入口核销

2026-09-15。来源：唯一剩余清单F2.2、既有节点计算映射明确列出的waitTimeout/savePath/UrlInput入口。没有新增产品行为或执行器。本次无业务代码修改；冻结字段语义沿用当前BasicModuleConfigs/AdvancedModuleConfigs及共享控件。

| 用例ID | 能力、前置、操作 | 界面/请求/状态断言 |
|---|---|---|
| NODE.wait_element.waitTimeout-entry | 新增等待元素节点，默认60；输入0、2.5、{seconds}、空文本、-1、Infinity | 合法值/变量/未完成文本原样存储；负数/非有限值显示无效，不能偷偷钳位；撤销60、重做、复制和Mock保存读取保留配置。运行准入沿用既有静态数值预检证据 |
| NODE.screenshot.path-entry | 新增截图，/before.png；点击选择文件 | 真实ConfigPanel→PathInput→systemApi→受控transport，请求/api/system/select-file及title=选择文件；返回中文/变量路径写savePath，撤销/复制/Mock保存读取一致 |
| NODE.screenshot.path-context | 选择文件等待时分别取消、403失败、切节点、手改路径 | 取消保留原值；403显示权限不足；迟到选择不覆盖新节点或手工路径；两节点数据独立 |
| NODE.open_page.url-tool-entry | 三网页节点，后两节点URL相同；聚焦当前URL并选建议 | 列表去重且排除当前URL；选中仅改当前节点，保留{name}文本；撤销、重做、Mock保存重开一致 |
| NODE.click_element.followNewTab-copy / NODE.input_text.clearBefore-copy | 原分支测试两布尔取值增加复制断言 | 原实际复选框操作、撤销/重做/重开断言保留，复制数据也须相同 |

层级：真实组件/Store/请求消费；初始化数据和历史调用属于组件测试，不标正式Electron E2E。路径服务为明确夹具，不证明原生系统选择框。共享PathInput格式/取消/迟到协议已有集中专项，不在每个入口机械重测。

证据：target.log，2文件39项通过；web-config-remaining-fields.test.tsx及原web-config-branches.test.tsx。未修改或放宽原断言。其它节点字段/高级配置/工具保持单独待核销。
