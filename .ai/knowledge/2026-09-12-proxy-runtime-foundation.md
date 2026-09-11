# 代理实施发现的基础设施问题

- 日期：2026-09-12
- 状态：confirmed；在 `codex/proxy-management` 独立分支验证，待浏览器主线串行整合
- 来源：真实 SQLite 连接检查、PyInstaller 构建及可执行文件 smoke

## SQLite 外键

`create_session_factory` 原先未开启 `PRAGMA foreign_keys`，因此表声明里的外键限制在运行连接上不生效。现通过每个 engine connect 回调开启。`tests/integration/test_database_foreign_keys.py` 同时打开两个 session，验证两条物理连接都开启外键，并验证非法外键插入抛出 `IntegrityError`。

浏览器配置代理引用目前仍含 JSON 字段，开启 SQLite 外键不能替代针对这些字段的应用层引用保护。代理扩展和成员表的外键也不能证明浏览器启动入口已完成联调。

## PyInstaller 迁移资源

`npm run backend:build` 原来可成功，但运行打包后的 sidecar 会报缺失 `script_location`。原因是 `autoflow-backend.spec` 没有包含 `alembic.ini` 和 `migrations` 数据文件。添加资源后再次构建，以下验证在本机 macOS arm64 通过：

```bash
node scripts/smoke-sidecar.mjs --executable apps/backend/dist/autoflow-backend/autoflow-backend
npm run smoke:desktop
```

后者验证开发 Electron 启动真实 sidecar、认证连接及窗口结束后 sidecar 退出；不能替代完整安装包的桌面启动和 Windows/macOS Intel CI。

## 原生凭据打包

构建分析清单包含 `keyring.backends.macOS`、keyring metadata 和 SOCKS 依赖 `socksio`；本轮没有读写真实账户密钥。实际授权交互与跨平台凭据操作仍需要相应平台集成测试。
