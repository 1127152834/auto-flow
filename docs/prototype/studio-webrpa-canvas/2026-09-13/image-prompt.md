# Canvas prototype generation prompts

Method: built-in image_gen. The first call used the original WebRPA screenshot and AutoFlow profile screenshot; the second refined the generated prototype against the original layout. These prompts produce a static UI proposal, not executable code.

## Initial prompt

Create ONE high fidelity Chinese desktop workflow canvas UI prototype image for AutoFlow, using the attached WebRPA screenshot as the authoritative layout/style reference. This is a narrowly scoped visual adaptation, NOT a redesign and NOT three alternatives.

Reference roles:
Image 1 (WebRPA 展示图1.png) = authoritative window anatomy, original compact toolbar, left module library, canvas widgets, original compact flow-node shape, dashed orthogonal connections, group containers, right inspector, bottom logs. Match its panel boundaries and positions.
Image 2 (AutoFlow profiles.png) = COLORS AND VISUAL TEMPERATURE ONLY, never copy its page layout/navigation into the Studio. Its actual tokens: canvas #f1eee7, surface #fbfaf7, subtle #f6f3ee, border #d8d3c9, stronger border #c7c0b5, text #34322e, secondary #625e57, clay primary #8d4e2f, clay hover #88492c, clay tint #f2e3d7, sage #71866b / #4f694a / tint #e6ece2.

Output: a single flat, crisp, complete app screenshot, wide landscape with the SAME aspect ratio as Image1 (2229 x 1200); render at high resolution, ideally about 3072px wide preserving aspect. No device mockup, no outer presentation board, no captions outside UI, no photographic texture, no gradients added, no tilted perspective. Chinese text must be exceptionally legible. Date context 2026-09-13 if needed, but no dates necessary. This is a mockup, no claims about real completed runs.

LOCK THE WEBRPA SHELL GEOMETRY:
- One compact full-width top toolbar approximately 5% height. Preserve its horizontal groups and original button shapes/heights, small line icons, separators and flow-name input. Brand at left becomes AutoFlow in dark clay with a small understated two-square logo inspired by Image2; no new navigation.
- Left module library occupies about 15.5% width between toolbar and bottom logs.
- Central dotted canvas about 65% width; right inspector about 19.5% width.
- Full-width bottom log region begins at the same ~64.5% image-height boundary as Image1. It spans BELOW ALL THREE columns, not merely the middle canvas.
- The canvas overlay module count stays top-left, module search stays top-center, operation hint pill stays top-right. Vertical zoom/fit/lock controls stay canvas bottom-left. Mini-map stays canvas bottom-right. The floating “流程图 / 模块条” switch remains centered near the BOTTOM OF CANVAS ABOVE the log divider. Do NOT relocate this to the top toolbar. Keep original subtle dot grid.
- Keep WebRPA rounded category rows, compact menu buttons, slight shadows, original density. Do not replace with large AutoFlow dashboard cards. COLOR remapping only for component surfaces; clay instead of original saturated blue, sage for success/run, muted sand/terracotta and sage for node categories. Very restrained desaturated semantic tints so categories remain distinct; no neon or saturated rainbow.

TOP TOOLBAR:
AutoFlow | input “商品信息采集” | sage green “运行 F5” with dropdown | clay solid “保存” | neutral warm “打开” | warm tonal “导出” with dropdown | small menu/undo controls in original footprint.
Right aligned original-size controls “自动化浏览器”, “录制” with dropdown, “全局配置”, ellipsis.
REMOVE previously excluded “工作流仓库” and “版本” controls. No publish/version/enterprise or desktop Windows controls. Leave natural flexible toolbar space rather than adding invented management controls.

LEFT LIBRARY:
Original header “模块库”, small secondary “拖拽到画布添加”; do NOT claim total catalog count542 because migration scope is not fixed.
Same original segmented “内置 / 自定义”, 内置 selected clay.
Same original search field “搜索模块/拼音/英文...” and favorite star.
Original category-row style with chevrons and small colored dots:
“常用模块”
“网页导航”
“网页元素交互”
“网页元素查询”
“网页数据采集”
“流程控制”
“变量操作”
“数据处理”
Keep row spacing and scroll area matching Image1, not an invented navigation sidebar. One category may be expanded only if it fits without crowding.

CANVAS example graph:
Use nine ORIGINAL-style compact horizontal module cards, top/bottom circular connection handles and small orange side handles as in Image1, subtle dashed orthogonal connectors. Show module count “模块数量 9”. Use a readable fit-to-canvas zoom, do not draw giant modern cards or pictorial workflow blocks.
Flow is an illustrative nine-node data collection workflow:
top “打开网页” with tiny second line “https://example.com/products”
then “循环执行” with source-style green “循环” and warm red “完成” outputs;
body branch contains “提取数据” (SELECTED, thin clay outline), “字符串操作”, “判断条件”, then two small parallel branches “列表追加” and “打印日志” (skip), with return routes to loop represented cleanly;
done branch runs “网页截图” then final “打印日志”.
Keep all cards and connectors fully within visible canvas. Preserve source grouping treatment: a subtle warm tinted dashed group box around data-processing nodes with small colored group header “商品信息处理”. Add the original sticky-note shape to the left of graph, titled “便签” with short content “逐条采集商品名称，整理后追加到结果列表。” Keep original style and roomy canvas whitespace. No extra Start/End node types or invented tabs. The exact example graph is illustrative, not a new product feature.

RIGHT PANEL selected state, grounded in actual original ConfigPanel/GetElementInfoConfig:
Match original inspector header (small square node icon, title “提取数据”, a tiny type badge “get_element_info”, disable/delete/collapse icons). Form has original compact stacked labels and warm-white inputs, thin borders:
“节点备注” = “读取商品名称”
“元素选择器” = “.product-title”
small source-style crosshair pick button adjacent to selector, and small “测试” button if space permits
“获取属性” dropdown = “文本内容”
“存储到变量” = “product_name”
“存储到数据表列” = “商品名称”
collapsed section row “错误处理”
“超时时间 (秒)” = “60”
“运行超时后” dropdown = “停止流程”
These are example values, NOT new defaults. Do not add an Apply/Save panel footer because original fields update immediately. No oversized sections.

BOTTOM:
Preserve original full-width tab strip, original icons/count badges and horizontal filter strip. Tabs left “执行日志” (selected clay), “数据表格”, “全局变量”, “图像资源”. Omit Excel resources, AI diagnosis and floating AI assistant because scope is not yet confirmed.
Right controls “简洁日志”, “下载”, trash icon, collapse chevron.
Below tabs the original search/filter/page-size controls: “搜索日志...”, “筛选”, “显示 100条”, “1/1”.
Log body should be calm with a few mock editor info entries only, NOT fabricated successful execution:
“14:30:01 INFO 已打开流程：商品信息采集”
“14:30:03 INFO 已选择模块：提取数据”
“14:30:05 INFO 流程尚未运行”
Use original small monospaced time and colored level badge, thin row accents; large remaining blank surface as in original.
Absolutely preserve WebRPA panel order, toolbar density, card silhouettes, controls positions and relative panel sizes. Match original first, then apply exact warm AutoFlow palette. ONE image.

## Layout refinement prompt

Edit the first attached AutoFlow workflow prototype image with one precise layout correction. The second attached WebRPA screenshot is the layout ruler. Keep the AutoFlow warm clay/sage/off-white palette, typography, original-style controls, Chinese copy, selected node, 9-node sample graph, forms and app identity from the first image unchanged.

The horizontal boundary above the full-width bottom execution-log tabs is currently at about 76% of image height. It MUST be at 64.5% of total image height, matching the WebRPA reference. This is the only required change in layout.
Preserve the same output aspect ratio 2229:1200. Keep top toolbar about5% height, left library~15.5% width, right inspector~19.5% width, and the three columns terminate at exactly y=64.5% of full height. Execution logs then occupy the entire bottom35.5% across full width, with tabs and search/filter strip at the top and three existing log lines then comfortable blank whitespace.
Fit the same graph into the now shorter canvas by using a slightly smaller canvas zoom and tighter vertical gaps (as original React Flow fit-to-view would do), retaining node shapes, relationships and all nine nodes. Move the canvas mini-map, zoom controls and bottom-centered “流程图 / 模块条” switch upward to stay immediately above the new y=64.5% divider. Their corner/center positions must remain original. Do not place view switch in the top toolbar.
Right inspector should remain normal compact source form styling. A thin scrollbar may show that lower settings continue below its shorter visible viewport; do not squeeze fonts or remove form fields from the conceptual panel. Library is scrollable, so lower category rows may fall below the divider as in WebRPA.
Keep Chinese characters crisp and exact. Do not redesign nodes, add controls, invent management tabs or change any colors. No sketch texture, no extra gradients. Return one polished flat app screenshot at high resolution. This is visual prototype refinement, not live execution.
