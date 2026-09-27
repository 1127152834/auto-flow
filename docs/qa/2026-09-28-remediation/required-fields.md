# 代理节点必填元数据

日期：2026-09-28。状态：confirmed（元数据与准入检查）；供应商真实切换不在本次证据内。

F-01 根因：三个代理节点已获批准并实现，但导出器硬编码 213 项且只读冻结 WebRPA 字段；当前生产元数据因此漏项。修复 scripts/export-studio-required-fields.py，明确保留 213 个来源节点，再叠加 3 个 AutoFlow 原生节点。新增规则不会覆盖冻结源；manifest 单列 nativeModules、nativeSource。生成后端字面量和前端 JSON 保持一致，--check 只读验证三个生成目标。

规则来自 ProxyControlExecutor.execute 与 ProxyControlConfig：所有代理节点 target=specified 时要求 proxyId，默认 current 不要求显式代理；切换地点始终要求 locationId；其余有默认值的次数、间隔、时限继续由执行器验证正值。元数据用于配置缺失提示，不假称其完成所有类型与授权校验。

修复前 required-fields-before.log 保存生成器与范围失败；proxy-required-before.log 保存 6 项缺字段/中文标签失败。修复后 required-fields-after.log 为 6 项脚本检查通过，proxy-required-after.log 为 4 文件 / 20 项前端检查通过，proxy-required-backend.log 为 23 项真实 HTTP 契约与生产 worker 相关检查通过。前端边界测试采用本地元数据，worker 代理网关使用既有边界替身，不计供应商实网验收。

测试维护仅更新有批准范围和实际 registry 支撑的数量及规则；213 个冻结条目仍逐字段对照独立 AST oracle，明确断言三个原生节点不存在于冻结源，排除节点仍不得重入。没有删除来源、许可或生成一致性断言。对应提交为本文件首次引入的提交。
