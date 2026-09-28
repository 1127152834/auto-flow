# 原生 End 配置验收：发现 UI-03

日期2026-09-28；状态confirmed（范围内真实观察，不是最终验收通过）。应用为dae16113源码打包，构建指纹见../packaged-end-v2.command.json。全部操作使用原生CUA；native-evidence仅只读抓取真实页面文本/截图。专属session与工作区身份见session.json，退出核对见exit-check.json。

1. 前序packaged-end-4iM7ci/result.json已经真实执行两次Run，保存登录、整应用重启、真实HTTP Cookie复用与下游无请求通过。此次重新启动并原生进入“保存登录”任务详情，页面显示End已完成、原定业务成功、环境清理已确认；截图/文本end-persistent-after-restart-main.*。
2. 原生从自动化“打开Studio”进入6b2e9cdf-38f0-472f-a3be-273bc11a97fe，选择End。虽然该运行config.retainEnvironment=true已实际保存环境，初始复选框却未选（end-config-before-edit-studio.*）。
3. 原生勾选保留并修改新环境名称，点击保存。首次输入因原生文本输入产生空白，保留实际保存revision2；随后用原生setValue确认字段为“原生 End 保存重载验收”，保存revision3。未用API纠正或写SQLite。节点备注同时显示同名的现有字段复用现象也保留在截图。
4. 只读SQLite（end-saved-sqlite.json）证明config.name仍是“打包真实登录”，外层data.name是新值。runtime.py364优先取data.config，ConfigPanel却读取selectedNode.data，形成真实配置分歧。不能把UI显示“已保存”算作执行值已更新。
5. 本次实例由原生Cmd+Q关闭，应用PID200和工作区匹配进程均不存在。用户另一实例未触碰；SQLite保留供修复后复验。

修复跟踪：计划Task6共享配置读写一致性；修复后必须重验回显、保存、重开、完整重启及真实执行结果，不只更新QA夹具为flat结构规避问题。
