# 外部源码与能力参考

## WebRPA

- 仓库：https://github.com/pmh1314520/WebRPA
- 审查基线：`5ccb900e8dcf1530aae66f676d87593c416c7ebb`
- 许可证文件：https://github.com/pmh1314520/WebRPA/blob/5ccb900e8dcf1530aae66f676d87593c416c7ebb/LICENSE
- 前端依赖：https://github.com/pmh1314520/WebRPA/blob/5ccb900e8dcf1530aae66f676d87593c416c7ebb/frontend/package.json
- 后端依赖：https://github.com/pmh1314520/WebRPA/blob/5ccb900e8dcf1530aae66f676d87593c416c7ebb/backend/requirements.txt

## 使用规则

WebRPA 只作为源码和能力参考。AutoFlow 不运行 WebRPA、不连接 WebRPA、不承诺读取 WebRPA 工作流文件，也不把 WebRPA 当作 npm 或 Python 依赖。

任何直接复制的文件都必须在迁移记录中写明：来源 commit、来源路径、目标路径、改动摘要、许可证和保留/删除的依赖。没有完成记录的代码只能作为参考，不得进入发布包。

## redroid 参考源码

- 日期：2026-09-13；状态：confirmed（用户授权纳入参考目录，已下载并校验）。
- [RedroidManager](../../reference/RedroidManager)：实例生命周期与管理界面参考，固定 commit `853b786b29430886ae8db58eb2d9e3432e0c8684`，MIT。
- [redroid-script](../../reference/redroid-script)：镜像定制与 Magisk 集成参考，固定 commit `a4951b782fc8e06c845d9553bf07bb643fd8c158`，脚本 MIT。
- [来源、许可证与恢复方式](../../reference/README.md)：沿用 WebRPA 的独立 Git 仓库和父仓库忽略规则；未接入运行时。

## 旧项目

- 路径：`/Users/zhangtiancheng/Documents/projects/browser-automation/autoflow-desktop`
- 当前基线文档：`CONTEXT.md`、`DESIGN.md`
- Python 入口：`backend/src/autoflow/main.py`
- Electron 打包：`electron-builder.yml`
- Python 打包：`backend/autoflow-backend.spec`

## ProxyPanel

- 官方产品：https://proxypanel.io/
- 新 API 文档：https://proxypanel.io/developers （登录会话中查看）
- [API 与开发契约](./proxypanel-api-contract.md)：外部能力证据、内部 DTO/路由、错误/操作状态、桌面复制边界和真实样本要求。
- [代理管理设计](../superpowers/specs/2026-09-12-proxy-management-design.md)
- [实施计划](../superpowers/plans/2026-09-12-proxy-management-implementation.md)
- 当前状态：2026-09-12，proposed；已做文档核验，无真实 API Key 调用样本。

## 模型管理源码迁移

- [设计规格](../superpowers/specs/2026-09-12-model-management-design.md)
- [API 与凭据契约](./model-management-api-contract.md)
- [实施计划](../superpowers/plans/2026-09-12-model-management-implementation.md)
- [源码哈希与新工程就绪度](../../.ai/knowledge/2026-09-12-model-management-implementation-readiness.md)
- 日期：2026-09-12。原型及旧布局/交互已确认；规格和计划为 proposed，模型业务尚未开始实现。
- 用户允许直接参考旧模型源码；复用状态机、协议和非秘密字段，按新架构重组。实际复制时登记来源和目标，不把本地源码阅读称为线上供应商验证。
