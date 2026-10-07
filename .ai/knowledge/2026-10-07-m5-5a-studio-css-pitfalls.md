# Studio 窗口的样式陷阱（M5 5A 实测发现）

- 日期：2026-10-07；状态：confirmed（在 `npm --workspace @autoflow/desktop run studio:preview` 的真实 Chromium 里实测，页面 `studio.html`）
- 来源：5A 的 S7 实测，对照源码核对；这些问题单靠 jsdom 单测测不出来

## 1. Studio 窗口不加载 `styles/index.css`

`studio.html` 的入口 `studio.tsx` 只引入 `domains/workflows/styles/webrpa.css` 与 `autoflow.css`（`webrpa.css` 再 `@import` Tailwind 与 `styles/tokens.css`）。
放在 `styles/index.css` 或 `controls.css` 里的全局规则**不会进入 Studio**。S2a 最初把 `data-motion` 压制规则写在 `index.css`，实测 Studio 里"减少/关闭"完全无效；
现已抽成 `styles/motion.css`，由 `index.css` 与 `webrpa.css` 共同 `@import`，契约测试 `motion.contract.test.ts` 守住两处都引入。
**以后凡是要在 Studio 生效的全局样式，必须经 `webrpa.css` 的导入链。**

## 2. `webrpa.css` 里有一条不在 CSS 层里的 `* { border-color: hsl(var(--border)); }`

Tailwind v4 的工具类在 `@layer utilities`，不在层里的规则优先级更高，所以 Studio 里**所有普通的边框颜色类**（`border-info`、`border-<色系>-<色阶>`、`border-line` 等）都被它压过，
只有带 `!` 的（`!border-info`）才生效。原 WebRPA 代码到处写 `!border-…` 正是这个原因。已知后果：S2b 的类别细色条最初显示成浅米色；运行外圈同理（已改内联主题变量与 `!border-info`）。
**5D 做调色类迁移前必须先处理这条规则**（放进 `@layer base`，或统一加 `!`），否则迁移到语义类后边框颜色仍然无效。

## 3. 本应用的字号刻度不是 Tailwind 默认值

`tokens.css` 里 `--text-xs: 11px`、`--text-sm: 12px`、`--text-base: 13px`。所以 `text-sm` 是 12px，不是 14px；规格要求"正文 ≥ 13px"时要用显式像素（`text-[13px]`、`text-[14px]`）或 `text-base`。
S2b 最初的"标题 text-sm"实测只有 12px，且比 13px 的摘要还小，已改成 14px；单测只断言类名，测不出这类问题，应以实测的计算样式为准。

## 4. 浏览器预览窗格隐藏时 CSS 过渡不会推进

内置浏览器窗格在后台（`document.visibilityState === 'hidden'`）时，`transition`/`animation` 的 `currentTime` 停在 0，会让"折叠后宽度没变"看起来像缺陷。
测量布局时把 `document.documentElement.dataset.motion = 'off'`（过渡归零）即可得到稳定结果，这同时验证了"关闭"档。

## 5. 实测数字（1440×900 / 1280×800，开关通过 URL `?flag.newStudioLayout=1` 打开）

| 状态 | 画布面积 / 窗口 | 备注 |
|---|---|---|
| 旧布局（开关关），1440×900 | 35.2% | 工具栏换行到 81px，底部 256px，右栏展开 |
| 新布局，1440×900，空闲、未选中节点、右栏不渲染、底部状态条 | **72.1%**（1182×790） | 工具栏 48px 单行，无横向溢出；满足 AC5-02 的 ≥ 60% |
| 新布局，1440×900，选中节点（左 256 + 右 320） | 52.6% | 只记录数字，不设硬断言（决定 D4） |
| 新布局，1280×800，空闲 | **68.9%**（1022×691） | 工具栏 48px 单行；最右按钮右缘 1268px < 1280，无溢出 |
| 新布局，1280×800，左栏折叠为 48px 窄条 | 82.9%（1230×691） | |
| 动效 full → reduce → off（Studio 窗口） | — | `animate-spin`/`animate-pulse`/节点外圈内联动画/logo 动画：full 为 infinite；reduce 为 none、过渡 0.12s；off 为 none、过渡 1e-6s |
