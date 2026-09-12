# 浏览器语言与时区目录

- 日期：2026-09-12
- 状态：已实现
- 范围：正式浏览器配置表单的语言、时区候选项；不涉及自动化执行后端。

## 数据来源与维护

唯一候选目录为 `apps/backend/src/autoflow/infrastructure/filesystem/profile_environment.json`。原有 `domains/profiles/presets.ts` 的 10 种语言和 9 个时区已迁入，补充后共 34 种语言、41 个常用时区。这是常用选项目录，不是完整语言/IANA 数据库，也不是模拟用户或浏览器运行数据。

文件包含 `locales`、`timezones` 两个数组；每项含 `value`、`label`。语言值使用 BCP 47 标记，时区值使用 IANA 标识；界面显示中文名称和实际标识。时区不保存固定 UTC 偏移，夏令时由时区数据库处理。

增加或修改候选项时编辑此 JSON，并运行：

```sh
uv run --directory apps/backend pytest tests/contract/test_profile_environment.py -q
```

此测试会校验目录内所有标识能通过既有 ProfileSpec 规则。文件必须包含非空列表、非空值/标签，且同一列表的值不得重复。JSON 读取或结构检查失败时返回服务错误，不使用前端备用目录。

## 调用与交互

- `GET /api/v1/profiles/environment-options` 使用现有本地服务鉴权，返回真实 JSON 目录。bootstrap 注入文件读取函数，HTTP 层不访问文件系统。
- 读取器每次请求重新读取文件。开发环境修改 JSON 后，关闭并重新打开配置弹窗即可重新查询；已有前端查询缓存按服务实例隔离。
- 正式前端通过生成的 OpenAPI 类型、profiles API 和 TanStack Query 接入。`presets.ts` 不再维护语言、时区目录。
- 下拉框始终展示全部候选项，不按当前值过滤；“自定义…”切换到手动输入，“选择预设”返回列表。
- 跟随浏览器、自定义标记和旧配置中未列入目录的合法值均保留。目录不是保存时的白名单，每个配置仍选择一个语言和一个时区。
- 加载和错误状态明确显示；失败可重试，已有值和草稿不被清空或替换。
- JSON 已加入 PyInstaller 数据文件。发布包更新目录需重新构建后端，源码目录的修改不会改变已经安装的版本。

## 验证

- 后端 profile 契约测试：目录与文件一致、动态读取、标识有效、鉴权、OpenAPI 契约、文件损坏/缺失、非默认及自定义值保存后读回。
- 前端 profiles 测试：接口候选项进入正式弹窗、完整列表选择、自定义切换、未列入目录的旧值保留、加载/错误/重试、保存请求中的实际值、校验错误焦点。
- `scripts/smoke-browser-management.mjs` 已加入目录接口检查；macOS arm64 PyInstaller 产物通过真实 HTTP 冒烟，确认 JSON 在冻结包中可读。
- 前端 lint/typecheck/build、后端 Ruff/mypy、OpenAPI 一致性检查通过。
- 桌面 GUI 手工验收尚未完成：当前同路径运行多个 Electron 实例，UI 工具定位到原有模型管理窗口，未操作该窗口中的草稿。Windows 打包本轮未运行。
