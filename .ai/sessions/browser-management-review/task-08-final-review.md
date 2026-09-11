# 任务 8 修复复审报告

- 日期：2026-09-12
- 复审提交：`5d6e4cf`（相对父提交，仅修改 profiles 的 4 个表单实现/测试文件）
- 依据：`task-8-review.md` 中的两个 finding、提交 diff、当前 profiles 实现与测试
- 排除范围：settings、`App`、main/preload、shared API 和后端的并行在途改动；未运行完整桌面端或完整后端测试
- 置信度：高
- 结论：**PASS**

## Findings

无。

## 修复核对

### nullable viewport 往返与交互

- `ProfileFormValues` 新增 `viewportMode: 'browser' | 'preset' | 'custom'`。`toForm()` 将 `viewportJson: null` 映射为 `browser` 加空宽高；schema 在 `browser` 模式跳过尺寸校验；`toWrite()` 将该模式写回 `viewportJson: null`。因此完整编辑链路保持 `null`，不再静默改成固定尺寸。
- 创建默认未改变：`emptyProfileForm` 仍为 `preset`、`1280 × 800`，创建配置仍写入原默认视口对象。
- 非空 viewport 会按是否命中预设映射为 `preset` 或 `custom`。控件支持从“跟随浏览器”选择预设、从“跟随浏览器”开启自定义并填入 `1280 × 800`、从预设开启自定义，以及从自定义关闭后回到匹配预设或首个默认预设。预设下拉的空选项可明确切回“跟随浏览器”；保留的宽高在 `browser` 模式下不会进入 payload。
- 回归测试覆盖 `null → toForm → schema → toWrite → null`、创建/预设既有路径，以及跟随模式切换到预设和自定义。

### 起始 URL 校验

- `isStartUrl()` 在 WHATWG `new URL()` 前要求原始 HTTP(S) 输入具有 `http://` 或 `https://` authority 前缀。`https:example.com`、`https:/example.com`、`https:////example.com` 因此全部在前端被拒绝，不再被 WHATWG 自动修正后误判为合法。
- 标准 `https://example.com/path?q=1`、`http://localhost:3000` 与精确的 `about:blank` 保持通过；非 HTTP(S)、坏端口和缺失 hostname 继续拒绝。
- 独立 Node/Python 探针确认：上述三种输入会被 WHATWG 修正为 `https://example.com/`，但后端采用的 `urllib.parse.urlparse` 语义均得不到 hostname；新增前置检查与当前后端结果一致。

## 验证结果

```text
profiles 聚焦 Vitest：8 files / 53 tests passed
TypeScript：npm run typecheck（tsc --noEmit）通过
profiles 定向 ESLint：npx eslint src/renderer/domains/profiles 通过
git diff --check 5d6e4cf^ 5d6e4cf：通过
URL 独立探针：3 个 WHATWG 自动修正输入拒绝；标准 HTTP(S) 与 about:blank 接受
```

当前工作树含 settings、App、main/preload、shared API、后端等并行未提交改动；本报告未修改或评价这些内容。
