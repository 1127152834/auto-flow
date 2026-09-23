# AM2 镜像与模板验收

日期：2026-09-23；状态：`partial`。审计起点 `3ee61947`；当前完整门槛见[全量验证](2026-09-23-current-full-gates.md)，Google 组件条件见 [gapps-validation.md](gapps-validation.md)。

| 任务 | 状态 | 证据与限制 |
| --- | --- | --- |
| T08 不可变镜像目录 | `passed` | `image_models.py`、`image_catalog.py`、`images.py` 及 unit 测试；引用保护覆盖设备、profile、backup；真实基础 ReDroid 固定 digest `sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b`。 |
| T09 登记/拉取/UI | `partial` | 来源换行/命令选项拒绝契约、服务端镜像元数据核验、ImageManager 自动化和隔离桌面真实登记通过；拉取前限制仓库与引用格式经 RED→GREEN 覆盖。本机 Lima Docker 上自建 ARM64 测试镜像已真实登记并按固定摘要删除，删除后 inspect 不存在。网络 pull、断线摘要核验仍未实测。 |
| T10 模板版本与快照 | `passed`（自动化与本机基础链） | `TemplateManager` 自动化与 `tests/integration/test_android_images_templates.py` 覆盖登记→profile→batch→编辑→tag 变化→原实例 restart 保持原 imageId→引用阻删；隔离桌面已通过真实固定镜像登记和标准模板创建。GApps 候选镜像模板另属 T11。 |
| T11 GApps 实验 | `blocked` | 验证归并函数 unit 通过；没有专用镜像、网络、账号、商店和测试 APK，按要求写为 `blocked`/`not_tested`。 |
| T12 AM2 生命周期 | `partial` | 后端模板/镜像生命周期集成与前端自动化通过，真实登记、标准模板及本机内容删除已验；候选镜像、网络拉取和 GApps 实例链缺少实测。 |

## 自动验证命令摘要

```text
cd apps/backend && uv run pytest tests/contract/test_android_{images,templates}.py tests/unit/test_android_{image_catalog,image_verification,images}.py -q
通过（包含在 Android 聚焦集合 235 passed 中）
```

这组 unit/contract 结果不能证明网络拉取或 Google 登录流程。

## 2026-09-23 增量：拉取边界与真实本机内容删除

`ImageCatalog.pull()` 原先先调用 `runtime.pull_image(reference)`，随后由 `inspect()` 检查格式；非法引用会先触及 Docker。新增可观察失败测试：`repo;unexpected:tag` 在抛 422 前已被记录为一次拉取，未批准的 `unapproved/repo:tag` 曾进入适配器。修复后在拉取前复用格式检查，并将拉取来源限定为 `redroid/redroid` 和 `docker.io/redroid/redroid` 的 tag/仓库摘要引用。本地已有其他镜像仍可按原登记入口检查固定摘要。定向 `pytest`：RED 先后 `1 failed`、`1 failed/1 passed`；GREEN `26 passed, 1 warning`；Ruff `All checks passed!`。新增 `redroid/redroid:13` 与 `docker.io/redroid/redroid@sha256:...` 正向测试。

真实 Mac/Lima 通过 `/tmp/autoflow-am2-image-content-qa-20260923.py` 生成独立小型 Linux ARM64 tar，`docker import --platform linux/arm64` 为唯一自建 QA tag，随后使用生产 `MacAndroidRuntime`、`ImageCatalog` 与 `AndroidImageService` 做实际 inspect、登记、按 imageId 内容删除。输出：`status=passed`、`registered=registered`、`deleted=deleted`、`actualImageAbsent=true`；镜像 ID 为 `sha256:4d0de47ffddbb261627cf590aa017a3d38daad688a7165e775c83b8a9981ec89`。最后再次查询 QA tag 返回 `No such image`。本实验经过真实运行时，但以独立内存资源仓库驱动服务，**不是**桌面或 HTTP 端到端内容删除验收；没有触碰已有 ReDroid 基础镜像。网络拉取与断线结果核实尚未实测。
