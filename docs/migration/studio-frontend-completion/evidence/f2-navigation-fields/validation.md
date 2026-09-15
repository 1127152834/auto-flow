# F2.2 网页导航配置

来源：唯一剩余清单F2.2及计算映射的七个节点，冻结WebRPA BasicModuleConfigs（2186起SwitchIframeConfig、2267起SwitchTabConfig）。不增加节点或执行器。

- NODE.navigation.load-states：refresh_page、go_back、go_forward、wait_page_load三个等待选项和page_load_complete三个检查选项，经各自ConfigPanel实际入口验证字段及导出重开。不能用open_page的既有通过替代这些入口。
- NODE.switch_tab.modes：七种切换模式；title/url各五种匹配模式；显隐与旧字段保留；三个保存变量字段，文档往返。
- NODE.switch_iframe.modes：index/name/selector三种定位及各目标字段原文，切模式不丢失旧目标，文档往返。
- NODE.switch_tab.index：1abc、1.5、Infinity、空、模板不静默截断；明确小数保留到草稿，由预检拒绝非整数。
- NODE.wait_page_load.timeout：默认60，0显示下限错误，2.5/引用/空文档草稿保持；字段存储timeout。
- NODE.page_load_complete.output：默认page_loaded、中文变量改名写saveToVariable及文档往返。

发现并修复的必要适配：
1. 原版SwitchIframe下拉缺省显示index，而条件直接比较undefined，导致新节点不显示索引框、点击已选index也无法触发改变。使用同一locateBy缺省值控制显示。
2. 原版SwitchTab使用parseInt，1abc和1.5均变1。按已批准数值草稿保留约束，改用现有NumberInput，不自造转换；整数/非负准入由共享staticNumberPreflight验收。

首轮4失败：2项真实截断、1项缺省iframe字段不显示、1项测试把未显式写入的缺省index误认为已序列化。最后一项改为认可缺省index语义（不放宽写入或显隐断言）；其它三项修复业务。before.log保留。最终4文件67项通过，包括既有网页基础字段/分支/工具，见regression.log。14个当前专项不等于14个产品功能或全部导航后端验收。

层级为真实组件/Store配置行为；没有在真实浏览器切页或解析iframe。真实自动化能力仍为后端交接。原生正式窗口/分发包由F6单列。
