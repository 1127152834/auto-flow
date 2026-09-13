# B0 图稿简报与原图对应

- 日期：2026-09-13；状态：待用户视觉验收，业务规格继续沿用已确认设计。
- 实施基线：`205fa64`，独立分支 `codex/project-management-implementation`。
- 生成方式：内置 `imagegen`，多画板 PNG；不生成 HTML 页面，不修改业务源码。
- [五图清单与哈希](prototypes/manifest.json)、[完整生成提示](prototypes/prompt-set.json)、[交互说明](prototype-interactions.md)、[手动审阅](acceptance/b0/manual-test.md)。

## 视觉基准与使用方式

沿用 `apps/desktop/src/renderer/styles/tokens.css`：canvas `#f1eee7`、surface `#fbfaf7`、正文 `#34322e`、次要文字 `#625e57`、强调 `#8d4e2f`、边框 `#d8d3c9`。正文14/20、辅助12/18、区块16/24、标题24/32；控件40px/紧凑32px；圆角8/12/16px；间距16/24px。

原图决定内容层级和操作载体；实际应用顶部导航决定外壳。旧图的全局左侧栏不采用。详情右侧业务状态是内容，字段抽屉是临时编辑器，都不是导航。每个完整页面按1440×1024逻辑视口构思；PNG是多画板总览，实际像素尺寸逐文件登记，不能据此声称完成1440视口或200%缩放运行验证。表格列、日期和名称均为虚构示例；计数不是性能证据。

图稿表达布局、层级和关键状态；精确路由、字段约束、操作身份、事务、动效和ARIA以已确认规格及交互说明为准。字形的轻微栅格误差不能成为修改产品术语或业务规则的依据。R阶段使用真实组件字体，不把整张PNG贴入页面。

## 五组图稿

| 图稿/画板 | 原图依据 | 保留与调整 | 状态、按钮和返回 |
|---|---|---|---|
| [R1目录](prototypes/r1-directory-overview.png)：R1-A项目目录，R1-B数据表目录，R1-C记录查询工具 | PMUI-5238b479f001、PMUI-ca940d758b68、PMUI-c496e3859302、PMUI-6729305d756d、PMUI-b3bf4542690d | 最近卡片、全部目录入口、数据卡片、紧凑查询；顶部导航替代原侧栏 | 新建项目/表、Excel导入；筛选/排序/显示列的取消和应用、批状态、导出；加载、空、无匹配、刷新失败和保存Toast；返回恢复查询及位置 |
| [R2记录页面](prototypes/r2-record-pages.png)：R2-A详情，R2-B新增，R2-C编辑 | PMUI-d3f6c5774ec4、PMUI-72de4a568a24、PMUI-421c549596d2 | 独立整页，紧凑上下文；普通字段直接编辑；身份只读/创建后固定 | 详情显式保存/清空业务状态，编辑/删除、复制/打开链接；新增/编辑不隐式写状态；取消/保存、新增到详情、编辑返回详情、列表返回恢复 |
| [R2异常](prototypes/r2-record-states.png)：R2-D校验，E离开，F冲突，G核验，H删除，I加载/只读 | PMUI-421c549596d2、PMUI-94895605c22f、PMUI-76a0e5a3361b、PMUI-b3bf4542690d | 原有校验与确认补足未知结果、重连和归档只读；不伪造PM4占用 | 首错定位、继续编辑/放弃、我的修改/最新内容、查询原操作、删除默认取消、删除中禁用、重连保留草稿；同一画板内独立状态卡不是同时出现的页面 |
| [R3字段](prototypes/r3-schema-draft.png)：R3-A字段表，B抽屉，C影响确认，D阻断/核验 | PMUI-378eb24a5f9c、PMUI-c3de19602511、PMUI-eb086d4107db | 字段表+抽屉+统一保存；去掉旧字段删除入口；已实现引用和未接通能力分开 | 应用到草稿不落库；重置草稿/保存字段→影响→确认保存字段；12条/8KiB是合成例；1000条且4MiB有界原子回填，超限/冲突整个候选不保存 |
| [R3文件与批状态](prototypes/r3-file-and-batch-states.png)：R3-E导入，F重导入，G导出，H进度核验，I批设置，J部分完成 | PMUI-cf611c443491、PMUI-73d061eba024、PMUI-d59f5568efae；PM2实际能力补充 | 保留检查/工作表/显式映射/校验/发布/结果；全量细节分步向导承载，图中E为步骤内容汇总；无Sheets新入口 | 来源文件不变、新代次状态清空、导出新文件；关闭进度不取消已接受操作；批设置350条，200修改/100冲突/50未执行；未知结果查询原操作 |

原图的精确路径、原批准状态和hash保留在[原图库覆盖](coverage.json)，不修改原图，不把这次生成稿冒称历史稿。R1使用当前实际Electron数据目录截图作为顶部导航参考，其余四组使用R1生成稿维持视觉一致；内容约束来自上表原图和已确认规格，不声称每张旧图都作为模型附件上传。

## 真实代码复用依据

旧仓固定 `324748abe7095f085b4ffb9467be9cb5c8851a5c`，所有路径前缀 `autoflow-desktop/`。既有[复用审计](../reviews/2026-09-13-prototype-alignment/legacy-reuse.md)已区分固定Git对象和旧工作树裁剪，后续实施按其取证：

- R1：`src/renderer/features/projects/ProjectDialog.tsx`、`pages/ProjectDataPanel.tsx`、`features/project-data/RecordsPanel.tsx` 的目录、返回和查询交互；新系统复用现有PM1/PM2 API。
- R2：`pages/ProjectDataRecordPage.tsx`、`features/project-data/RecordView.tsx`、`RecordEditor.tsx` 与记录可靠性测试；适配新RecordRef、Operation和受控外链桥。
- R3：`features/project-data/FieldSchemaEditor.tsx`、`ExcelImportDialog.tsx`、`ImportPreview.tsx`、`SourceSettingsSection.tsx`；后端 `data_model_service.py`、`excel_service.py` 的交互反例参考，不能覆盖新系统代次和受控文件合同。

当前来源/设置/状态原型继续参照 PMUI-cf611c443491、PMUI-070d7f52a4ae、PMUI-d59f5568efae；B0新增五图专门补足纠偏缺口，并不删除这些既有页面设计。

## 缺图与阶段映射

| 缺口 | B0交付或后续门槛 |
|---|---|
| ALIGN-DATA-01 | R2页面与异常两图；等待用户确认 |
| ALIGN-DATA-02 | R3字段图；等待用户确认 |
| ALIGN-DATA-03 | R3文件与批状态图；等待用户确认 |
| ALIGN-AUTO-01、ALIGN-AUTO-02 | G1后、PM3-A前生成；本次不生成、不标完成 |
| ALIGN-ENV-01 | PM8前生成；本次不生成、不标完成 |

R1–R3业务实现尚未开始。B0确认后先交付R1及其真实应用手测方案，用户验收后才进入R2，依次推进。
