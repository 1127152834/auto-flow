# F5.1：移除旧独立令牌 UI

2026-09-14。对应正式实施计划 F5.1：WebRPA 旧安全令牌/端口由 AutoFlow 管理，不保留无效控件。

- 原 SecuritySettings 默认宣称本机免验/局域网监听，却调用未实现的切换与重置接口；getAuthToken 恒为空、setAuthToken 空实现。删除这些无效表单与客户端函数。
- 保留安全标签，说明访问鉴权归 AutoFlow 宿主，不在 Studio 提供第二套令牌设置。
- 删除空令牌的 X-WebRPA-Token 构造；现有传输和调用方请求头保留。未改变真实后端/main/preload 鉴权。
- Mock 旧 security 路径返回 410 和明确停用原因，不再返回 enabled:false 来伪造当前系统状态。
- 不删除用户配置或凭据数据。

6 项新增用例修复前 5 失败，修复后与现有鉴权传输和配置回归合计 6 文件 95 项通过。TypeScript、ESLint、49 项脚本、renderer/main/preload 构建通过（33.13 秒）。浏览器只读核验通过。全量结果在完成后记录；真实宿主/platform 验收仍分开。

本批完整回归：277 个前端测试文件、3271 项测试通过（481.17 秒）；后端契约 412 项通过，OpenAPI 一致性和目录检查通过。该结果不代表真实自动化或正式 Electron 验收完成。
