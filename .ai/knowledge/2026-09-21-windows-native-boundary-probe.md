# Windows 原生边界实验

日期：2026-09-21。状态：proposed（原生实验待 CI）；来源：S4 已批准规格、本机源码、Microsoft 原生 API 文档。

- 项目 worker 正常终止已有 asyncio 保留进程句柄及 bootstrap kill-on-close Job；不替换为 PID taskkill。父退出回调改为当前 worker 自身退出，由 Job 关闭负责后代。
- 增加同一 OpenProcess 句柄上的 GetProcessTimes/TerminateProcess/WaitForSingleObject 检查，错 birth 不终止，身份不可读/终止拒绝/退出未证实保留失败。当前尚未接入重启清理，不能宣称 Windows 孤儿恢复完成。
- 原生 Windows 测试创建实际进程，错误 birth 必须存活，匹配 birth 后必须确认退出。本机仅规则测试通过，不能替代 Windows 证据。
- 文件实验用原生 CreateFileW 持有拒绝写/删除的目标及暂存句柄，检查 FileRenameInfoEx flags 1/3 是否允许安全替换，并验证父目录拒绝改名。结果由现有 CI 的显式 pm9NativeProbe 模式输出 artifact；不因此移除 ARTIFACT_PLATFORM_UNSUPPORTED。

参考：
- https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-fscc/4217551b-d2c0-42cb-9dc1-69a716cf6d0c
- https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle

脚本 `scripts/pm9-windows-native-probe.py` 是边界可行性实验，不是第二套文件实现；完成实验后应删除或转为最小原生回归。
