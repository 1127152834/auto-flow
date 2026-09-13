# 安卓模块唯一视觉基准

日期：2026-09-13；状态：confirmed。来源：用户在本轮重新附上的四张原型，并明确要求一模一样；原始文件逐字节复制，尺寸与SHA256见manifest.json。

| ID | 画面 | 文件 |
| --- | --- | --- |
| R1 | 资源看板：6台设备、三列、等待任务表 | [原图](01-resource-board.png) |
| R2 | 手动控制台：设备画面、工具条、输入与操作 | [原图](02-manual-console.png) |
| R3 | 创建实例：数量3、环境配置、持久/临时、右侧预览 | [原图](03-create-instances.png) |
| R4 | 工作流占用：只读画面、步骤进度、暂停接管 | [原图](04-workflow-takeover.png) |

这四张图是验收基准，不再沿用上一版“视觉风格相近即可”的判定。生产数据可变，布局、控件、层级、静态文案和对应行为不能擅自省略。手机画面作为视觉测试样本与真实运行画面分别处理，不能把样本冒充在线设备。

规格：../../superpowers/specs/2026-09-13-android-prototype-exact-design.md
实施计划：../../superpowers/plans/2026-09-13-android-prototype-exact-implementation.md
