# redroid 参考源码导入

- 日期：2026-09-13。
- 状态：confirmed。
- 来源：用户明确要求将 JinHisAndy/RedroidManager 和 ayasa520/redroid-script 纳入 `reference`；上游 URL 见 [参考索引](../../reference/README.md)。
- 本地目录：`reference/RedroidManager`、`reference/redroid-script`。
- 固定 commit：分别为 `853b786b29430886ae8db58eb2d9e3432e0c8684`、`a4951b782fc8e06c845d9553bf07bb643fd8c158`，与此前源码调研版本一致。
- 存储：浅克隆，保留独立 `.git`，detached HEAD；沿用 WebRPA 模式，由父仓库 `.gitignore` 忽略源码，索引提供重新克隆与版本恢复命令。
- 许可：两个仓库的源码许可证均为 MIT，原始 LICENSE 已保留；下载组件适用其各自条款。
- 验证：检查 origin URL、HEAD、工作区干净状态、许可证文件、父仓库忽略规则及文档 diff；未执行上游安装脚本或运行 Android。
- 范围：只增加本地参考源码与索引，不代表选型已正式确定或业务功能已集成。
