# 留存清理配套：实施前核对

2026-09-14，源码已核对，尚未实现本页修复。

来源：冻结 reference/WebRPA/backend/app/api/retention.py、services/retention_manager.py；当前 GlobalConfigDialog.RetentionSettings、api.ts retentionApi、api/mock-settings.ts。

- 源 GET /config 返回 success/config/usage；POST /config 只合并非 null 字段；GET /usage 返回 success/usage。
- 源 POST /cleanup 返回 success/recordings/data，各有 removed 与 freedMB；当前 Mock 没有这两个清理摘要。
- 当前 UI 保存和清理忽略 res.success，接口失败仍提示成功；首次读取错误没有退出加载与重试。
- 当前表单 Number('') 变 0；无有限/整数/负值校验；清理间隔 0 的源实现还会回落到 6/至少 1 小时，含义不明确。
- 当前保存与清理分别 disable，仍可并发；缺少连接/迟到回执保护；未提交策略可能被读取覆盖；未接设置离开检查。
- AutoFlow 当前 Mock 默认 false/30天/0MB/30天/0MB/24小时，源默认 true/14天/1024MB/30天/512MB/6小时。后续实现先保留当前 AutoFlow 默认并记录差异，不能无声改变既有用户策略。
- 源实际清理范围包含运行录像与采集结果；不因此恢复排除的 Excel/文件自动化节点。真实后端必须以登记运行产物为边界，不能照搬源 ROOT_DATA_DIR 扫描或吞掉删除错误。

下一步：独立 RetentionSettings 组件、严格配置/用量/清理回执、非负整数与正清理间隔、单操作占用、连接隔离、保存/放弃/取消、明确 Mock 结果。现阶段不对实际文件执行清理。
