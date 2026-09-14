# 系统路径选择服务合同

2026-09-14，F1 有界批次通过。源对照 reference/WebRPA/backend/app/api/system_dialog.py（冻结5ccb900e）FolderSelectRequest、FileSelectRequest及/select-folder、/select-file。

两条路由仅POST；请求 title/initialDir 可省略或null，文件选择另有fileTypes（每项两个字符串：名称、过滤模式）。现有camelCase和过滤内容保留，不引入Windows对话框代码。

响应success为布尔、path为字符串或null。选择成功带字符串；取消支持冻结版false/null/“用户取消选择”，以及当前消费端已兼容的true/null或空字符串。失败不得携带非空路径，必须有错误信息；取消不能隐藏error。schema-only发布类型，真实宿主尚未实现。

Mock验证方法、请求结构；前端服务层验证响应结构，失败结果保持失败，未确认/非法结果不能回填。端到端宿主确认与取消仍待实际平台验收。

## 验证记录

后端DTO20项，前端新增合同29项（内存与本地HTTP各9项、响应校验11项），与既有路径工具回归共74项通过。全量前端260文件2,988项通过（463.34秒）；不含随后新增WebDAV用例，不用这个结果证明WebDAV新代码完整验收。

Ruff、mypy（202源文件）、TypeScript、ESLint、OpenAPI一致性、49脚本、renderer/main/preload构建通过。49条逐项合同台账，证据见 evidence/f1-path-contract。第一次内存协议测试误用了非允许域名，403来自Mock域名限制；改用既有autoflow-studio.mock后通过，没有放开外部域名。

DTO是schema-only，无新增真实宿主路由。Mock保留原目录、示例文件以及folder/file兼容字段。模块来源标记中的@WebRPA哈希是版本标记，实际冻结源码目录为reference/WebRPA。
