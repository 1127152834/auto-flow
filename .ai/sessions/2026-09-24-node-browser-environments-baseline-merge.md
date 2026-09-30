# 节点浏览器环境合并 baseline

- 日期：2026-09-24；状态：confirmed（本地无冲突合并；远端结果以 Git/PR 为准）。
- 来源：用户在获知实现、草稿 PR #2 和未通过验收项后明确要求“合并”。
- 目标：codex/architecture-baseline；来源：codex/node-browser-environments@ad2bf2395996f8e2014a2bf34dc1bdd99a4cbb6c。
- 本地目标原为 1bc6b24d，远端原为 c6e02427；两者均为来源分支祖先。沿用此前本地合并历史，不重做历史分支归并，不修改主目录或其他工作区。
- 验证：普通 --no-ff 合并无冲突；加入本记录前，合并索引 tree 与来源提交完全相同。本次只增加合并记录，不修改实现、不重复已执行回归。合并前 diff --check 提示来源已有 project_resource_schemas.py 末尾空行，保留原受测源码。
- 验收沿用 docs/qa/node-browser-environments/2026-09-24/：Windows/Apple Silicon 节点浏览器专项通过；完整 CI 的 Windows test:scripts 失败原因待有效日志授权、ARM mypy 失败、Intel mediapipe 安装阻断，以及本地 baseline OCR 停止耗时失败均未解决。
- 合并不等同于发布验收：releaseAccepted=false；签名、OAuth 与缺失实机证据仍待外部条件。保留来源分支；不发布、不重启用户应用。
