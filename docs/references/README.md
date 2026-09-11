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

## 旧项目

- 路径：`/Users/zhangtiancheng/Documents/projects/browser-automation/autoflow-desktop`
- 当前基线文档：`CONTEXT.md`、`DESIGN.md`
- Python 入口：`backend/src/autoflow/main.py`
- Electron 打包：`electron-builder.yml`
- Python 打包：`backend/autoflow-backend.spec`
