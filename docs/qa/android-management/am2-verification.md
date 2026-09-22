# AM2 镜像与模板验收

审计基线：`b828daf9`；当前聚焦后端 `159 passed, 1 warning`、前端 Android `13 files, 45 passed`；Google 组件条件见 [gapps-validation.md](gapps-validation.md)。

| 任务 | 状态 | 证据与限制 |
| --- | --- | --- |
| T08 不可变镜像目录 | `passed` | `image_models.py`、`image_catalog.py`、`images.py` 及 unit 测试；引用保护覆盖设备、profile、backup；真实基础 ReDroid 固定 digest `sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b`。 |
| T09 登记/拉取/UI | `blocked` | 来源换行/命令选项拒绝契约、ImageManager 自动化和前端 Android 聚焦回归通过；网络 pull、断线摘要核验和内容删除实机受网络/运行时条件限制，仍 blocked。 |
| T10 模板版本与快照 | `blocked` | `TemplateManager` 自动化与 `tests/integration/test_android_images_templates.py` 已通过，覆盖登记→profile→batch→编辑→tag 变化→原实例 restart 保持原 imageId→引用阻删；真实镜像/网络条件仍 blocked。 |
| T11 GApps 实验 | `blocked` | 验证归并函数 unit 通过；没有专用镜像、网络、账号、商店和测试 APK，按要求写为 `blocked`/`not_tested`。 |
| T12 AM2 生命周期 | `blocked` | 后端模板/镜像生命周期集成与前端自动化证据已通过；候选镜像、网络拉取和 GApps 实例的真实验收条件不足，保持 blocked。 |

## 自动验证命令摘要

```text
cd apps/backend && uv run pytest tests/contract/test_android_{images,templates}.py tests/unit/test_android_{image_catalog,image_verification,images}.py -q
通过（包含在 Android 聚焦集合 159 passed 中）
```

这组 unit/contract 结果不能证明网络拉取或 Google 登录流程。
