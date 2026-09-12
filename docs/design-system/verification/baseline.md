# T0 实施基线

- 日期：2026-09-12；状态：confirmed；用户本轮授权开始T0–T2。
- 工作树：`autoflow-ui-controls-plan`；分支`codex/ui-controls-plan`。
- 已将主线`a1f3925`合并到本分支；隔离基线提交`dff88608068e09d28db92551c3d86896dcac4778`。原计划文档3756f7e保留。未更改主目录。
- 已核对5e7bc98：语言/时区/UA统一EnvironmentOptionField、后端维护UA模板；后续不恢复原datalist/前端模板。保留a1f3925代理检测旋转反馈、显式检测协议与品牌资源。
- 主目录automation文档/草稿未提交，未复制。
- 保护清单：[protected-baseline.json](protected-baseline.json)，记录后端、main/preload/IPC、生成契约和领域数据逻辑文件SHA-256；UI实施相对此基线核对，不将合并进来的已有主线变更误报为本任务修改。

| 命令 | 结果 |
|---|---|
| npm ci | 通过；631包安装；原有依赖deprecated/install-script提示保留，未改安装策略 |
| npm run test:structure | 3/3 |
| npm test | 45文件、270测试通过；包括使用自身临时目录的既有sidecar集成测试 |
| npm run typecheck | 通过 |
| npm run lint | 通过 |
| npm run build | 通过；原有Zod PURE注释警告，不是本轮引入 |

本轮后续GUI验证使用独立user-data-dir，不操作共享Electron窗口。Windows与读屏验收尚未执行。
