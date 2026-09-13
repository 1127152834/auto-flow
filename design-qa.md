# Gallery R1 Design QA

final result: passed

范围仅R1；R2/R3未验收，用户手测未执行。

来源：原gallery latest/100项目目录、001数据目录、002记录、016新建表、017筛选。实图：acceptance/gallery-r1/runs/run-fLAsGt与run-fzpgVA。原图1487×1058；实际CDP内容视口1440×1024，100%/DPR1；200%为720×512/DPR2，原生窗口尺寸和实际字体在run/result.json逐图记录。菜单改顶部与真实业务数据是已授权差异。未用像素相似度或平均分抵消单页失败。

每对源图/实图在同一次工具调用打开后审查；整页中文、控件与表格均可读，未另造局部裁切作为通过依据。字体层级、间距节奏、颜色令牌、源图清晰度及产品文案分别核验。原016标题选择器失效/取消按钮错误为P2，修正后新截图88分；查询200%重叠越界为P2，真实200%及嵌套键盘复验通过。所有适用GF强制关系通过，五张最终91/90/89/88/89。

无未闭合P0/P1/P2。剩余P3：弹窗留白与字符提示对齐、边框深度、动态表格列比例、筛选箭头和辅助文字细节。按skill不为P3继续循环。文件来源条件未实现的Sheets/外部SQLite不伪造；所需业务能力与额外操作位置均已在page-map登记。

详见 [R1审查](docs/project-management/design-alignment/acceptance/gallery-r1/review.md)、[原图与实图](docs/project-management/design-alignment/acceptance/gallery-r1/comparison.html)、[机器结果](docs/project-management/design-alignment/acceptance/gallery-r1/machine-report.json)。


# Gallery R2 Design QA

final result: passed

实现a08c2fe；原003–007与run-msXqcI每对同工具调用查看。004/005带底部补图，非遮挡修图。逐页86/88/89/91/88，适用GF全部通过。前轮004/005/007因Toast污染、校验按钮外观和英文影响而失败（84/84/80），修正后重新E2E/截图，保留历史。剩余仅辅助字号、边框和局部间距P3。

实际1440×1024/DPR1与200%720×512/DPR2；原生窗口大小、字体与构建哈希在逐图report。真本地来源/UUID与顶部导航为已登记差异，未添加虚构Sheets状态。无未闭合P0/P1/P2；用户未签收基线，Windows/打包未执行。R3尚未验收。

详见[原图对照](docs/project-management/design-alignment/acceptance/gallery-r2/comparison.html)、[审查](docs/project-management/design-alignment/acceptance/gallery-r2/review.md)、[机器报告](docs/project-management/design-alignment/acceptance/gallery-r2/machine-report.json)。
