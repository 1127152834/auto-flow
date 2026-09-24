# Google/GApps 镜像验证

2026-09-24状态：`blocked`（confirmed）；验证结果必须保持 `not_tested`/`blocked`，不能因为发现包名而写入 `passed`。

## 当前证据

- `summarize_verification([])` 返回 `not_tested`。
- 包检测、登录条件缺失和必需检查失败的归并逻辑已有 unit 测试。
- [全分支审查修复](2026-09-23-final-review-remediation.md)后，API 的 `verification.state` 只表示技术元数据核验，独立 `validation` 表示谷歌组件验收；前端分别显示。一次元数据通过返回 `validation=not_tested`，请求当前不支持的登录核验返回 `validation=blocked`，不会把组件声明或元数据通过写成 GApps `passed`。
- 早期“缺普通网络和测试APK”的描述已superseded：官方镜像网络拉取/故障恢复和本地测试APK已实测。当前缺少可追溯来源及构建说明的GApps专用候选、测试账号和商店完整访问/下载验证条件；现有magisk镜像名称本身不是GApps证据。
- 因此以下GApps专用链检查均未执行：启动、商店、登录、免费测试应用下载/启动、停机重启、第二实例隔离。普通ReDroid基础启动、APK和双实例隔离的已通过证据不受影响。

## 验收边界

完成验证时应使用新建且带 workspace/device 标签的临时实例，记录候选来源、固定 `imageId`、架构、构建说明、每个 `check_id` 的 `status`、`checked_at`、`evidence_id` 和 `reason`。缺任一外部条件时保留 `blocked`，不得将基础 ReDroid 镜像或包名清单当作 Google 认证结果。
