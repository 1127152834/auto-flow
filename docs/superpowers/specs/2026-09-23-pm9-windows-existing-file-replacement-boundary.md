# Windows 现有文件替换边界（S4 补充提案）

日期：2026-09-23。状态：proposed，尚未改变已批准的 S4 覆盖/追加契约。来源：[S4 规格](2026-09-21-pm9-runtime-capability-completion.md)、[原生实验](../../project-management/implementation/pm9/completion-gaps.md)、[读取子片证据](../../project-management/implementation/pm9/windows-existing-output-read.json)、Microsoft 的 [CreateFileW 共享规则](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)、[ReplaceFileW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew) 与 [FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info)。

## 已证实的边界

批准的契约要求：给定任意现有输出路径及读取时的 `expected_identity`，更新/追加必须同时保证旧目标身份未变、同卷原子发布、失败不破坏原文件，也不能替换外部并发写入的文件。

原生实验在持有不共享写入/删除的旧目标句柄时，`FileRenameInfoEx` 替换 flags 1/3 分别失败，旧文件未变；持有父目录句柄能阻止该目录改名，但不能把旧目标身份作为系统替换操作的前置条件。`ReplaceFileW` 按路径重新打开旧文件并请求 `DELETE` 权限；`FILE_RENAME_INFO` 的替换参数没有期望文件 ID。结合 Windows 共享规则，推论是：继续持有禁止删除的旧句柄会阻止替换，先释放句柄再按路径替换会留下外部进程调换目标的竞争窗口。该推论只排除目前查证的 API 组合，不宣称 Windows 一切文件系统机制均不可能做到。

## 当前决策与后续切片

在原批准契约下，现有文件覆盖/追加继续返回 501。现有文件**读取**已作为独立子片在 Windows 原生句柄与真实 worker 验证，不据此开放写入。

若必须在 Windows 提供可重复导出，建议单独批准“版本化输出”：每次写入由现有新文件发布机制生成唯一不可变路径，应用账本的逻辑输出引用指向最新版本；既有用户路径不被覆盖。这会改变用户可见的保存路径、再次导出和打开方式，须先冻结 API/UI 契约，再做真实 worker、失败清理、并发、恢复、打包链验证。另一种选择是保留现有文件写入的 501 并明确产品限制。不能把放宽路径检查或先验 `stat` 后盲替换当作 S4 完成。

这个提案只解决 S4 剩余写入合同的取舍；L1–L3 与 M1–M3 各自仍按已提交的方案及授权状态处理。`releaseAccepted=false`。
