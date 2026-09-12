# PM1 本机真实应用验收

- 日期：2026-09-13；平台：macOS arm64。
- 入口：构建后的 Electron renderer HTML，真实 FastAPI/SQLite 服务。没有使用页面 mock。
- 执行：仓库根目录 `npm run build` 后运行 `node scripts/smoke-project-management.mjs`。
- 数据：脚本独占的两个临时工作区、虚构项目和独立 userData，退出后清理；不读取或修改用户业务数据。
- 机器事实以 [built-html.json](built-html.json) 为准；开发过程截图不作为最终验收基准。

脚本完成新建 A/B、编辑、六页签、名称和描述搜索、55 条真实分页数据、返回位置恢复、外部 PATCH 冲突与显式重新编辑、同工作区服务重连保草稿、双工作区隔离、Electron 完整重启与最近访问持久化。它还检查实际 Tab/Enter/Escape 和自动焦点，以及浏览器、代理、模型、设置、总览与 Studio M1 的入口。

200% 检查通过 Electron 原生 `setZoomFactor(2)`，不是 CSS 缩放；生产设置界面仍保留原有 90/100/110/125% 选项。机器记录同时检查根容器宽度、全页溢出和下拉面板边界。历史上一轮仅测宽度的结果不能代替最终完整边界检查。

| 截图 | 场景 |
|---|---|
| [空目录](built-html-empty.png) | 创建前的真实空数据。 |
| [管理表单](built-html-form.png) | 名称/描述输入与保存操作。 |
| [项目概览](built-html-overview.png) | 真实资料与六页签。 |
| [目录分页](built-html-directory.png) | 批量真实数据和列表滚动。 |
| [编辑冲突](built-html-conflict.png) | 保留脏输入，明确重新编辑入口。 |
| [离开确认](built-html-leave-confirmation.png) | Escape 触发嵌套确认并可继续编辑。 |
| [200% 下拉](built-html-zoom-200-dropdown.png) | 自有面板、受控高度、暖灰与黏土棕视觉。 |
| [应用重启](built-html-restarted.png) | 重启后再次打开项目 A。 |

置信度：以上实际运行范围为高。Windows、macOS x64、安装包和用户里程碑验收均未执行；不将本机开发形态 Electron 运行写成发行包通过。历史 PM0 核验保持原样。
