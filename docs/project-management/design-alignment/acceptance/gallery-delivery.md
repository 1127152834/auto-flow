# 项目管理 Gallery 对齐交付入口

日期：2026-09-14。工作区：`/Users/zhangtiancheng/Documents/projects/autoflow-project-management-implementation`；分支：`codex/project-management-implementation`。本轮连续范围为G0、R1、R2、R3，PM3未开始。主项目与旧项目保持只读，未将实施分支合并回主线。

唯一视觉基准为主项目 `docs/references/project-management-prototypes-2026-09-13/gallery.html`。全局左侧菜单改现有顶部导航；内容区沿原图，不能用B0衍生图替代。页面所需真实数据、未开放能力不按演示图伪造。

| 阶段 | 交付 | 截图对照与结果 | 手动验收 |
|---|---|---|---|
| R1 | 原项目目录/最近卡片、统一项目头、数据目录、记录工具与查询浮层 | [逐图对照](gallery-r1/comparison.html) · [机器报告](gallery-r1/machine-report.json) | [R1手册](gallery-r1/manual-test.md) |
| R2 | 原型记录整页新增/详情/编辑、自有日期控件、未保存/删除确认及受控外链 | [逐图对照](gallery-r2/comparison.html) · [机器报告](gallery-r2/machine-report.json) | [R2手册](gallery-r2/manual-test.md) |
| R3 | 字段整体草稿、右侧编辑与影响抽屉、原子保存、真实状态引用、来源和设置；Excel/批状态完整回归 | [逐图对照](gallery-r3/comparison.html) · [机器报告](gallery-r3/machine-report.json) · [审查修复](gallery-r3/review.md) | [R3手册](gallery-r3/manual-test.md) |

## 启动当前隔离版本

在实施工作区执行：

```bash
npm run build
node scripts/qa-project-alignment-r3.mjs --manual
```

该工具创建自己带标记的临时工作区，经真实UI准备基本资料后保持应用打开，并打印两份合成Excel路径和异常复现命令。使用手册逐条操作；用户手测全部初始为“未执行”。需要重新验项目目录或记录页时，退出本工具后按R1/R2手册启动各自隔离工具。工具不使用用户业务工作区。

## 提交和边界

- R1实现 `a6a0e8e`，证据 `8ccf969`。
- R2实现 `a08c2fe`，证据 `c2a2002`，归档格式 `eccde15`。
- R3后端 `e467035`，组件/页面 `b2d1543`，真实部分结果缺陷修复 `800fb01`；证据单独提交。

最终工程与端到端结果以R3报告为准；R1/R2旧报告保持其历史版本，不改写旧截图的构建哈希。截图评分为人工定性审查，不是像素相似度，也不是用户认可。

本机为macOS arm64；Windows、其他架构、打包版本和用户手测未执行。字段删除、整表删除、Sheets同步、自动化配置引用等仍按业务里程碑保留明确“暂未开放”；不为还原演示图编造可用操作。主线Studio已独立推进，后续合并须核对迁移分叉、生成类型和共享文件，不直接覆盖主目录。
