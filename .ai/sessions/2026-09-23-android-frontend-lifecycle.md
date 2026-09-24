# Android 应用响应与预览生命周期

- 日期：2026-09-23；状态：confirmed（本轮修复），目标 active/partial。
- 来源：`codex/android-management-complete`，基线 1399f07b；`docs/qa/android-management/2026-09-23-frontend-validation.md`。
- T15：确定失败核验释放 UI 写入锁，unknown 不释放；APK 保存原 generation。初始操作和核验响应均校验当前设备/会话/generation/端点/访问类型，关闭或卸载后忽略迟到响应。
- T14：可见性确认后才挂载查询，隐藏/禁用取消；等待队列取消不留悬空项；共享可见观察者仍存在时保持请求；跨后端旧画面不覆盖；ObjectURL 释放。
- 环境纠正：默认 Node26.7.0 不满足规格 Node22.x。已通过 npm exec 缓存隔离的 Node22.23.2；未变更锁文件或系统默认版本，指定运行时 Android 14 文件/100 项、类型/lint/OpenAPI/结构/build 通过；全量 415 文件通过/9 失败，脚本 92 通过/3 失败。新增交互失败单独复跑通过，未将它们等同全量通过。
- 完整目标仍未完成；已知软件工作与全量门槛失败继续推进，不标成外部条件 blocked。
