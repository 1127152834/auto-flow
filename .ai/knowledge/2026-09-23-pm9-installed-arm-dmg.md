# PM9 当前 ARM DMG 安装应用验收

日期：2026-09-23。状态：confirmed（本机隔离安装与一次完整重跑；三平台 CI 打包链另行通过），物理安装与发行条件 pending。

来源/验证：`docs/project-management/implementation/pm9/installed-arm-dmg-follow-through.json`；DMG SHA256、`hdiutil verify`、只读挂载并以 `ditto` 复制到临时安装目录；以复制后的应用运行 `smoke-project-management-desktop.mjs`。生产源码 `6d1f1d83`，脚本修正解决终态实例处置：`cleaned` 不再发新 End，`retained_unsaved` 才按现有受限命令显式放弃。真实运行、容量、缩放及重启链通过。

首轮容量阶段在合成日志写入期间一次记录分页等待超时；没有保留页状态，根因未知。第二次全链及 Actions 35822065171 三平台打包桌面链通过，新增失败时的页码/文本/行数/告警诊断，不能据此宣称持续稳定。应用为 ad hoc 签名，未有 Developer ID、公证、Finder/Gatekeeper 与卸载专项。历史 PM6 实网服务账号证据仍有效，但不替代当前打包 Sheets/OAuth 链。`releaseAccepted=false`。

2026-09-23 更新（confirmed，来源 `installed-arm-current-candidate.json` 与本机原始报告）：最终源码 dadb24a1 的 Actions 35833223498 ARM DMG 在本机 `hdiutil verify`、只读挂载和隔离复制后，使用 SHA256 对照发布清单的公开版 145 内核运行原版完整桌面脚本通过。真实 worker、人工声明输入、万条写入、合成日志、缩放、第二窗口和重启保留均通过。前两次尝试的 `KERNEL_NOT_INSTALLED` 与 `LICENSE_INVALID` 来自本机 Pro 内核/许可条件，未作为通过；临时脚本改动已撤回。Finder/Gatekeeper、当前原生面板/凭据、Windows/Intel 实机、签名公证和当前打包实网链仍 pending。前段较早源码结果仍保留历史，不应与本候选混算。
