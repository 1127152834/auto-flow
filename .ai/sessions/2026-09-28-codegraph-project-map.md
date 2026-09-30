# CodeGraph 与项目地图

- 日期：2026-09-28。
- 状态：confirmed（索引及文档范围）。
- 来源：用户要求检查 CodeGraph、缺失时安装并制作项目地图；CodeGraph CLI/MCP 实查与当前工作区源码。
- 结果：本机已有 CodeGraph 0.9.9 和 MCP，AutoFlow 尚未初始化；执行 `codegraph init` 建立索引，CLI 状态与 MCP 查询成功。状态快照为 2,153 文件、40,611 节点、119,718 关系。
- 产物：[项目地图](../../docs/PROJECT_MAP.md)，覆盖运行关系、业务定位、Studio/项目 worker 入口、契约、测试与索引维护；原目录文档增加入口与过时描述标记。
- 本机 `.codegraph/` 已忽略，不增加产品依赖；在新工作区运行 `codegraph init .`，必要时 `codegraph sync .`。
- superseded：早期文档中“Studio 仅 Mock / 没有真实后端”的当前状态描述；当前装配、认证 HTTP、worker 与运行服务已存在。历史验收结果不因此扩大。
- 边界：未修改业务代码，未重新进行产品全量测试、平台或发行验收；原有未提交工作保持原状。
- 验证：仓库结构测试 4/4 通过；地图及本记录共 46 个本地链接存在；2 张 Mermaid 图语法解析通过；`git diff --check` 通过；数据库、daemon PID/socket 均命中忽略规则；CLI 符号/调用者查询和 MCP 查询成功。
- 后续同步：同一工作区存在其他任务改动，最终 `codegraph sync .` / `status .` 为 up to date（2,154 文件、40,622 节点、119,735 关系）；正文数字保留初始化后的 MCP 快照，不作为固定规模承诺。
