# PM9 当前 ARM DMG 安装应用验收

日期：2026-09-23。状态：confirmed（本机隔离安装与一次完整重跑），其他平台及发行条件 pending。

来源/验证：`docs/project-management/implementation/pm9/installed-arm-dmg-follow-through.json`；DMG SHA256、`hdiutil verify`、只读挂载并以 `ditto` 复制到临时安装目录；以复制后的应用运行 `smoke-project-management-desktop.mjs`。生产源码 `6d1f1d83`，脚本修正解决终态实例处置：`cleaned` 不再发新 End，`retained_unsaved` 才按现有受限命令显式放弃。真实运行、容量、缩放及重启链通过。

首轮容量阶段在合成日志写入期间一次记录分页等待超时；没有保留页状态，根因未知。第二次全链通过，新增失败时的页码/文本/行数/告警诊断，不能据此宣称持续稳定。应用为 ad hoc 签名，未有 Developer ID、公证、Finder/Gatekeeper 与卸载专项。历史 PM6 实网服务账号证据仍有效，但不替代当前打包 Sheets/OAuth 链。`releaseAccepted=false`。
