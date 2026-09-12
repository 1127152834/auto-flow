# 控件统一 T3

- 日期：2026-09-12；状态：implemented，本机自动结果 confirmed，人工IME/跨平台仍待执行。
- 用户授权：T0–T2后要求继续；本批按先前约定仅执行T3，没有自动分派智能体或改动主目录。
- 起点：a932626，独立 codex/ui-controls-plan。只读确认主目录17e0870在共享components/styles上相对T0无增量。
- 产出：Button/IconButton、Input/Textarea/SearchInput/PasswordInput、Spinner、FormField render-prop、FieldGroup、TextControlCases。新Search/Password API尚未接入领域，现有消费者继承共享Input/Button样式。
- 兼容：所有既有真实表单提交点显式type=submit；Input保留事件/ref/数字字符串；密码显隐默认关闭；旧FormField children路径待T12移除。
- 修正：全局font:inherit移入Tailwind基础层，字号实测由16修复至14/12；FormField content-start修复有/无提示字段错位；测试的alert定位限定到对应案例。
- 最终验证：53文件/289测试；类型/lint/build；令牌10/结构3；真实Electron9组通过。生产JS无lab代码/样本，CSS61个令牌存在；225个保护源码hash不变。
- 真实页面：独立sidecar正常，浏览器新建配置表单打开/样式/焦点/取消通过，未保存配置。
- 未决：UI-G0-01在125%缩放出现一次内层Dialog提前关闭，后续两轮/三轮诊断及最终两轮通过，根因未知。保留事件诊断与更严格断言，不宣称修复；T5前必须收口。T4可独立继续。
- 手动中文IME、剪贴板、Windows、VoiceOver/NVDA和全系统真实业务回归未执行。
- 报告：docs/design-system/verification/text-controls.md。下一步T4，不把当前组件批次完成等同专项完成。
