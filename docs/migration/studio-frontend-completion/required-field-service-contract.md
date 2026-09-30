# 必填字段元数据服务与前端恢复

2026-09-14；历史状态：前端接口消费与恢复验收通过；完整节点规则覆盖仍未完成。F1/F2共享配套设施；不新增自动化节点或表单引擎。

## 来源与问题

冻结WebRPA system.py的module-required-fields从ai_assistant_module_schemas.py提取required、conditional_required、desc，并移除已有默认值的必填字段。最初 AutoFlow Mock 接口缺失，useRequiredFields 把失败永久缓存为 {}，且条件及标签缓存不按连接隔离；上述前端缺陷已由原批次修复。2026-09-23 真实包复核发现正式后端尚未注册同一接口，返回 404。

## 合同

GET /api/system/module-required-fields返回schemaRevision、coveredModules、requiredFields、conditionalRequired、fieldLabels。coveredModules明确哪些模块确有规则，未覆盖不能解释成“无必填项”。条件规则是field/default/map，按当前模式补充必填项；0和false是已填写，空字符串、null、undefined、空列表未填写。默认值过滤在服务端完成。

数组/映射/条件字段严格校验，未知覆盖模块的条目或不一致结构拒绝。HTTP失败、HTTP200错误包、非法响应显示规则未加载，保留输入和重试入口；不能改记为零个必填项。相同连接并发请求合并，只缓存成功响应。连接替换或恢复后重新读取，旧响应不得更新新连接的规则；显式重试可刷新缓存。空字段规则与规则未覆盖显示不同状态。

冻结元数据通过AST字面量读取，仅保留已批准 227 节点（284 为早期范围，已 superseded）；不运行旧后端、不复制旧服务基础设施。源规则未覆盖的节点在台账明确保留缺口，不凭字段名字推断必填规则。前端接口消费与提示可完成，不能把源覆盖不足标为 227 节点校验完成。

## 本批测试

建立逐项协议/组件用例：基础必填、各条件分支及默认分支、默认值过滤、零/false、空值、服务标签与回退标签、加载态、失败、重试、成功缓存、并发去重、连接替换/同地址transport替换、旧响应迟到、断线恢复、损坏响应、未覆盖模块。内存与真实HTTP共用返回规则；实际UI核对空URL提示和错误重试。生成类型和后端DTO、目录/script一致性同步验收。

## 2026-09-23 正式接口补齐

状态：正式 HTTP 定向回归通过；打包验收和候选全量结果以 `docs/project-management/implementation/pm9/studio-metadata-follow-through.json` 为准。

正式路由复用 `StudioModuleRequiredFields` DTO、现有实例认证和错误处理；缺失/损坏资源返回 500，不能降级成空规则。OpenAPI 由同一正式路由生成。现有 AST 提取器同时生成开发夹具和后端静态资源，并由 `--check` 检查逐字一致；PyInstaller 显式收集后端 JSON，运行时不需要 reference 源码或开发 Mock。

来源：`reference/WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb`，`backend/app/services/ai_assistant_module_schemas.py`；源文件 SHA256 见 `required-field-source-coverage.json`。沿用已批准源码授权和根目录 `LICENSE.WebRPA`。新增派生目标 `apps/backend/src/autoflow/adapters/http/module-required-fields.json`；同原开发目标一样，仅保留六组 schema 字面量中的 required/conditional_required/desc，过滤 defaults，不引入旧服务或执行依赖。

实际保留范围 227，来源覆盖 69、未覆盖 158。三个项目专用节点不在这份冻结来源范围内，继续显示未覆盖。字段提示元数据不决定节点执行准入，不证明整个配置或执行能力完整。
