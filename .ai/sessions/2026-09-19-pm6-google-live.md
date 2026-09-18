# 2026-09-19 PM6 实网 Google Sheets 验收

- 日期：2026-09-19
- 来源：用户提供的服务账号 JSON + 已授权测试 Spreadsheet
- 状态：confirmed
- 工作区：`/Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm6`
- 分支：`codex/project-management-pm6`

## 结论

PM6 的服务账号路径在真实 Google 上跑通：真实 Electron 界面点击 → 真实 FastAPI sidecar → 真实
`HttpxSheetsTransport` → `sheets.googleapis.com` v4 → 真实系统凭据库。10 个检查点全过，11 张截图。

证据：`docs/project-management/implementation/pm6/google-live/2026-09-18T16-05-05-012Z/`。

## 实网抓出的缺陷（替身轮没抓到）

`apps/desktop/src/renderer/domains/project-data/sheets-api.ts` 的 `disconnect()` 没传 HTTP 动词，
`command.submit` 默认 POST，而 `/sheets/connections/{connectionId}` 只注册 DELETE → 405。界面只显示
「操作失败，请重试」，用户既删不掉凭据也无法诊断。

这是同一类缺陷的第三例：第一例是 `putBinding` 用 POST 打只接受 PUT 的路由，第二例是拉取/推送后
记录页不重取。共同点是**替身不校验方法或状态**，所以单元测试全绿而真实界面必然失败。

修复：传 `'DELETE'`。`sheets-api.test.ts` 补两条动词断言（`disconnect`、`removeBinding`），
临时还原修复后 `disconnect` 一例确实失败。

## 边界与未执行

- Google API 约束：`PUT .../values/{range}` 的 body **不能带 `range` 字段**，否则 400
  `Request range does not match value's range`。脚本只发 `{majorDimension, values}`。
- 未执行：OAuth 桌面应用授权流程、Windows、其他架构、打包、用户手测。
- 凭据只存在于 `/tmp/pm6-google-sa.json`（600 权限），不进仓库、日志、截图或提交；证据 JSON 已核对无密钥材料。
- 远端只写 `工作表2!B2` 并在结束时清空；独立复核整表无 PM6 测试标记残留。

## 复核

`project-data` 域 65 文件 / 684 测试、typecheck、lint、build、`test:structure` 4/4 全绿。
