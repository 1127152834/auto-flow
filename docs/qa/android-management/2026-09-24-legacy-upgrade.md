# 旧版本真实临时实例与数据库向前升级

2026-09-24；confirmed；旧版本a92f0688→产品修复0f6f8fac；真实链passed。使用独立旧版本git worktree、现有Python环境、生产HTTP和Mac/Lima/ReDroid；旧后端真实创建SQLite和临时实例，未伪造数据库记录，未恢复工作流执行链。

命令：`uv run --project apps/backend python docs/qa/android-management/scripts/legacy-upgrade-smoke.py --allow-device-mutation --old-checkout /private/tmp/autoflow-android-legacy-qa --output /private/tmp/android-legacy-upgrade-green.json`，exit0。复现须先将a92f0688检出到该独立目录。脚本明确要求设备变更opt-in，只删除它自己临时workspace中的资源。

## 实际RED与根因

[真实RED JSON](2026-09-24-legacy-upgrade/real-red.json)和[失败输出](2026-09-24-legacy-upgrade/real-red.log)：旧后端批次请求未保存sourceDeviceId，当前HTTP schema补null；持久请求精确比较误判冲突，升级后原batchId重放返回409/ANDROID_REQUEST_CONFLICT。数据库迁移和数据保留本身通过。测试自有容器/卷全部清理。

0f6f8fac仅在batch比较时将缺失sourceDeviceId与null视作无来源，不修改历史记录。SQLite关闭重开→当前HTTP回归覆盖旧persistent/temporary、当前null、具体来源ID；来源变化或显式true磁盘确认仍409，新temporary请求仍拒绝。[实施报告](2026-09-24-legacy-upgrade/implementation.md)包含实际RED2failed/4passed→GREEN6passed、Android540passed及命令输出。

## 实际GREEN

[真实GREEN JSON](2026-09-24-legacy-upgrade/real-green.json)和[输出](2026-09-24-legacy-upgrade/real-green.log)：旧迁移head0019_recording_commands向前迁移至am01_management_operations。升级前后deviceId、containerId、volumeId、imageId、temporary类型、creationConfig完全相同；模板revision和镜像身份保留。启动原实例后数据探针一致，原batchId返回202及相同目标，新temporary请求409/ANDROID_TEMPORARY_DISABLED。测试资源容器/卷0。

这关闭旧版本数据库/真实临时实例向前兼容的证据缺口。T12同一次发布停用入口→重新启用的完整桌面组合链仍未执行；历史RED缺失不能用本次新回归追认。真实桌面仍受Mac锁屏阻塞，整体验收partial。

前端1050文件hash与78bf8c92全量5689passed时一致，无新增文件；[hash及受保护Studio文件](2026-09-24-legacy-upgrade/source-preservation.json)。本次产品改动不涉及OpenAPI形状、迁移或前端。最终后端全量、独立复审及构建结果见[当前验收报告](2026-09-24-final-acceptance.md)。
