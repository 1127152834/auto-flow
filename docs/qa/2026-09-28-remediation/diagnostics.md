# 导入与 Android 诊断修复

日期：2026-09-28。状态：confirmed（以下限定检查），真实打包 UI 验收 pending。

N-04：ExcelImportService 已将 INVALID_PROJECT_DATA 的 rowNumber、columnIndex、field、rule、reason 完整写入操作记录。缺陷在 safeProjectError 只按错误码显示通用说明。现在由共享展示函数校验行列整数、限制字段文本，按已知原因/规则生成中文；columnIndex 从零开始，显示时加一。任意 message、路径、未知 reason 和内部身份不作为 UI 文案。DataOperationStatus 在没有临时 error prop 时直接展示持久 operation.error，重开页面仍可解释失败。

修改 presentation-error.ts、DataOperationStatus.tsx；导入 hook 的持久查询协议保持原样。import-details-before.log 为 2 失败 / 23 通过；import-details-after.log 为 3 文件 / 29 通过，包含重建服务上下文后按原 key 查询失败、不重复导入、列号转换、未知诊断不反射，以及持久错误实际 DOM 显示。此处 API 返回是单元边界数据，不能计真实 XLSX 或原生文件面板验收；最终稳定包仍需补跑该场景。

A-04/A-10：MacAndroidRuntime.environment 原先只检查 Docker 架构与 binder，漏掉生产默认 bridge 的实际网络接口；run 丢弃 stderr，使真正启动失败原因丢失。现在只读 Docker 默认网络配置，并检查实际 bridge 对应的 Linux 网络接口。命令失败保留退出码与至多 2000 字符的已脱敏 stderr；无 stderr、命令启动失败、超时、格式错误有明确说明。原有 AndroidError 通过现有操作记录和 UI 错误链传递，不新增执行器或 VM 管理层。

android-diagnostics-before.log 保存 2 项失败；修复后 android-diagnostics-final.log 为 14 通过，含真实本机子进程非零退出、敏感值脱敏、长错误截断，以及网络缺失/格式错误的边界检查。android-environment-native.json 使用生产环境探测连接当前真实 Lima，仍确认 docker0 不存在，返回 available=false 与明确网络原因。没有启动、重启、重配 VM，没有创建或删除设备。这是诊断真实验证通过，Android 正常启动仍被现有共享 VM 网络阻塞。

AndroidPage 的分配弹层明确执行能力尚未开放，并禁用入队提交；DeviceDetails 不再宣称在 Studio 选择设备即可运行。现有后端 allocate 固定返回 ANDROID_WORKFLOW_RUNTIME_UNAVAILABLE，此改动对齐既有行为。android-ui-after.log 为 3 文件 / 12 通过，包含不可用提示、入队禁用、不发送分配请求，以及原有手动控制与隔离检查。该组为组件测试，不作真设备 UI 验收。

诊断切片 tsc 和 ESLint 见 diagnostics-typecheck.log、diagnostics-eslint.log；后端限定 Ruff/mypy 通过。各项对应本文件及相关修改的独立提交（git log --follow 可检索）。剩余：真实 XLSX 原生导入、应用重启的实际 UI，Android 正常启动和其他平台；没有将未执行计为通过。
