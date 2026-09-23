# AM1/AM2 桌面实测：镜像目录、实例生命周期与高缩放

- 日期：2026-09-23；状态：`confirmed`（下述本机链）；AM-AC05/06/10/11 整项仍为 `partial`。
- 来源：隔离 worktree 的 Electron 构建、本机独立工作区 `/tmp/autoflow-desktop-qa-userdata-20260923`、真实 Mac/Lima/ReDroid、自建镜像登记及实例。未切换用户现有工作区，也未操作另一项目的 Electron 进程。

桌面实测首先发现两个真实 500：登记镜像成功后，`GET /api/v1/android/management/images` 将内部 `workspaceId/requestId` 送进禁止额外字段的 `ImageRead`；旧 `GET /api/v1/android/environment` 将运行时新增 `checks` 送进旧 DTO。先扩展两项契约测试，输出 `2 failed`；再复用镜像服务已有的公开字段投影，并让旧环境路由只取旧 DTO 字段。定向重跑 `2 passed, 1 warning`。隔离桌面重启 sidecar 后，页面显示 `available` 的 Mac/Lima 诊断及已登记固定摘要镜像，镜像目录错误消失。

通过页面显式建立标准模板，并创建 `QA 长名称与高缩放隔离实例 2026-09-23 01`；实际 ReDroid 从“启动中”到“已就绪”，只读画面和 `create/start` 持久历史可见。页面停止后状态变“已停止”，选择不删除数据后变“数据已保留”，页面恢复后重新“已就绪”。初次链暴露正常 ready/stopped/retained 被计入“需处理”的错误：后端将不适用的常规动作（例如 ready 实例无保留数据可恢复）放进异常 `blockedReasons`。状态规则失败测试输出 `1 failed`；修正后相关后端 `17 passed, 1 warning`，重启 sidecar 的真实卡片在 stopped/retained/ready 均为“需处理 0”。测试实例最后经认证公开 API 指定 `deleteData=true` 永久删除，两个管理列表返回 0，客体按两台自建 deviceId 搜索容器和卷均无结果；未删除本机基础镜像。

长名称布局另在独立第二台自建实例上验证。应用内缩放 125% 可访问页面和实例操作；应用设置仅提供 90/100/110/125%，因而又将应用设为 100%，通过 Electron 原生 `View → Zoom In` 连续五档进入更高缩放。此时 7 段“超长实例名称”在卡片换行，但“已停止”被挤成逐字竖排。先加组件失败测试，输出 `1 failed, 16 passed`；状态标签加 `shrink-0 whitespace-nowrap` 后 `17 passed`、类型检查和桌面构建通过，重载渲染器并重复五档缩放后，视觉复验状态保持横排。随后第三台自建长名称实例在 DevTools 只读测量下，`Actual Size` 的 `devicePixelRatio=2`，提高原生页面倍率后为 `4.147200107574463`，相对基准约 `207.36%`；卡片名称、横排“已停止”、操作按钮及“需处理 0”仍可读。该原生菜单不能精确设置 200%，所以只确认**高于 200% 的实测档位**，不冒称精确 200%；1280×800、1440×900 两种窗口尺寸仍未仪器化验收。第二、三台设备均经认证公开 API 永久删除，客体容器和卷查询均无结果。

验证命令与结果摘要：

```text
uv run --project apps/backend pytest apps/backend/tests/contract/test_android_images.py::test_image_registration_returns_server_inspected_metadata apps/backend/tests/contract/test_android_management_environment.py::test_legacy_environment_route_projects_extended_runtime_checks -q
# RED: 2 failed；GREEN: 2 passed, 1 warning
uv run --project apps/backend pytest apps/backend/tests/unit/test_android_management_state.py::test_normal_lifecycle_states_have_no_attention_blockers -q
# RED: 1 failed；GREEN 包含在状态/镜像/环境集合 17 passed, 1 warning
npm exec --workspace @autoflow/desktop vitest run src/renderer/domains/android/tests/ManagementOverview.test.tsx
# RED: 1 failed, 16 passed；GREEN: 17 passed
npm run typecheck -w @autoflow/desktop
# exit 0
npm run build -w @autoflow/desktop
# exit 0, built in 1m 30s
limactl shell autoflow-redroid -- sudo docker volume ls --format '{{.Name}}' | rg '79e5c533|f790292c'
# 无输出；对应 docker ps -a 名称检查也无输出
```

限制：这一链没有用真实网络断开测试旧快照/控制会话，也未在同一桌面链打开原生窗口；应用设置未提供精确 200% 档位。列表首次出现的“待核实或不可操作”是批量动作默认“启动”对已运行实例的动作特定文案，不代表实例总体状态；此文案仍可改善。全量回归与最终分支审查以随后独立门槛记录为准。
