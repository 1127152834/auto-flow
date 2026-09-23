# Android 数据卷备份采用 Lima 客体侧 tar

- 日期：2026-09-23；状态：`confirmed`。
- 来源与验证：[真实属性和恢复验收](../../docs/qa/android-management/2026-09-23-persistent-metadata-verification.md)，以及对应脚本与 JSON 结果。

Docker `cp` 在本机真实 Docker 卷中未将 `user.autoflow_probe` 写入 tar；普通 ReDroid 停机卷还含 417 项扩展属性，其中 55 项为 POSIX ACL。单纯拒绝属性会让正常实例无法备份。使用 Lima 客体内的 GNU tar 以 PAX 格式归档和还原 xattrs、ACL 与数值 UID/GID；`--selinux` 已启用，但本机未观察到可验证的 SELinux 标签。归档仍经过路径、链接、类型、摘要和清单校验，恢复仍要求持久意图、归属标签及空目标卷。卷根目录以 `data` / `_data` 路径变换保留元数据，变换排除软链接目标；客体实验已验证根权限/属性及硬、软链接往返。两个 Unix socket 是临时运行时端点，归档不保留；其余持久条目在真实新实例中逐路径一致。

格式版本仍为 1，没有改写旧迁移或旧备份。旧 Docker `cp` 备份已经漏掉的属性无法补回；未来若客体 tar 不可用，操作失败而不是退回会静默丢属性的路径。硬中断和容量边界仍需单独验收。
