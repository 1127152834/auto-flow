# 安卓页面适度紧凑调整

- 日期：2026-09-30
- 状态：confirmed（样式、交互回归及构建验证）
- 来源：用户提供创建安卓实例页面截图，要求字号和布局稍微紧凑、避免拥挤。
- 基线：2c9ca001；范围仅 Android CSS，不改业务、接口或运行时。

## 调整和可观察对照

保留双栏及三段表单，正文 16→14px，主标题 30→26px，分区标题 21→18px，输入高度 42→38px，底栏 89→72px。取消 691px 固定面板最小高度，合并旧重复覆盖规则，适度减小段落、标签列和预览图尺寸。数量控件窄屏不再拉满一行，复选框保持 16px、数量按钮保持 36px 宽、提交按钮 40px 高。

在 1440×992 CSS 像素窗口：调整前文档高 1034px，表单底边 924px 超过固定底栏顶边 903px；调整后文档高 992px，表单底边约 833px，底栏顶边 920px，三段表单与确认项完整可见。详见 before.json / after.json 和 create-before.jpg / create-after.jpg。

1280×800 展开更多设置后，滚动并勾选确认项成功；确认项底边约 685px、底栏顶边 728px，无横向溢出。744×900 单列布局无横向溢出；增加数量成功，预览同步更新，磁盘确认按既有行为重置；数量控件宽 128px。资源看板及控制页视觉检查无布局回归。

## 实际验证

| 命令/检查 | 输出摘要 |
| --- | --- |
| `npm --workspace @autoflow/desktop test -- src/renderer/domains/android/tests --maxWorkers=2` | 14 files / 206 tests passed，19.91s |
| `npm run typecheck` | tsc --noEmit，退出 0 |
| `npm run lint` | eslint .，退出 0 |
| `npm run build` | main / preload / renderer 构建成功，renderer 32.81s，退出 0 |
| `git diff --check` | 无空白错误 |
| 浏览器实际渲染 | 1440×992、1280×800、744×900；展开设置、数量变更、确认勾选、看板与控制页 |

完整输出为同目录 tests.log、typecheck.log、lint.log、build.log。构建出现依赖包 PURE 注释提示，测试出现 Node localStorage 实验提示，均未导致失败。

## 边界与风险

无本次样式交付阻塞项。截图采用明确标记的视觉验收样例，展示真实页面组件，但连接状态和设备内容为 fixture；不是 Mac/Lima/ReDroid 真实实例验收。未启动模拟器或执行创建请求，未复验后端完整 AM1–AM4。小窗口或展开设置仍需纵向滚动。用户已打开的 Electron 窗口需重新加载/重启才能读取新构建。
