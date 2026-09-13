# 安卓设备与工作流原生交接

- 日期：2026-09-13；状态：confirmed。
- 来源：用户确认实施；正式代码、Python/React 测试、真实 Mac API/冻结/打包应用验证。
- 决策：沿用正式工作流快照/单活跃名额/事件/截图产物。Android 子进程只请求固定动作，ADB 及原生窗口由父进程串行持有。
- 资源：专用设备记录、独立容器与卷；稳定安装级 VM 锁跨工作区共用，工作区标签和容器/卷身份每次核验。不把旧 Demo 设备直接登记到正式系统。
- 人工交接：显式节点；run 继续占用设备。关窗不推进；continue 先持久化、收回原生连接、再次确认预算/停止状态才推进。回执按 handoff 保存，旧重复请求只回读。
- 失败处理：不重放超时输入；无法核实 Android 命令完成或旧进程身份就保留 recovery_required。恢复不杀全局 ADB，也不停止 Android。
- 平台：当前 Mac ARM64 + Lima，固定 scrcpy 3.3.4。Windows 返回不可用，不阻止其他模块启动。批量和混合图另行设计。
- 交付：codex/android-workflow-handoff 独立分支与本地 Mac 包；并行 M4 主工作区未被修改。合并时需要显式迁移汇合及契约回归。
- 证据：docs/migration/android-workflow-handoff-validation.md。

## 设备页直接操作入口补充（2026-09-13，confirmed）

来源：用户指出设备卡片点击无反应。原先“设备页仅查看”的范围现已 superseded：新增明确的打开按钮，通过既有运行接口创建仅含一个人工节点的手动会话，并在此次点击对应的会话进入等待后开窗。结束操作复用 continue；无后续自动节点。页面刷新、导航重进和关窗不自动开新会话，不改变占用/清理规则。预算为页面明确提示的 60 分钟。

## M4 与设备管理补充（2026-09-13，confirmed）

来源：用户确认按原型开发设备管理第一版。此前“等待并行 M4 稳定”和“仅准备命令登记设备”的描述已 superseded：接入已提交 M4，使用0008显式迁移汇合；安卓使用共享结构化调度与逐次产物。设备生命周期、保留数据恢复及原生入口集中于正式 Android service/provider，继续保留单运行/VM控制器边界。规格和验证见 docs/superpowers/specs/2026-09-13-android-management-design.md 与 docs/migration/android-management-validation.md。
