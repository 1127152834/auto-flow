# 主项目接入行内新增（2026-09-14）

状态：confirmed 实现与整合验证。用户明确要求将侧分支 `361d4fd` 合入主项目。采用独立整合工作区，保留 dcb1831 的 R2/R3 与主线最新 Studio 2f51399。新增迁移汇合、共享路由注册，并修复同工作区重连后 QueryClient 与活跃 observer 分离造成的保存后旧值显示；反例、回归与最终真实 Electron 均验证。

证据：`docs/project-management/design-alignment/acceptance/main-integration/`。主目录采用快进；原分支与其他任务未提交改动必须保留。正常新增使用表内草稿，不再跳转到创建表单；旧 pending 恢复与已有记录编辑不移除。Windows/打包/用户手测/原分支剩余 G4 仍未验收。
