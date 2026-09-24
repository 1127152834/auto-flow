# 213 节点验收核销（2026-09-24）

状态：**未全部验收完成**。沿用能力台账，204 个节点已有有效验收证据；9 个节点仍缺完整原生验收。639 个节点验收槽位中630通过、9待验收。本次没有把待验收节点改为通过，也没有恢复14个已删除通知节点。

唯一逐节点台账：`docs/migration/studio-frontend-completion/capabilities.json`。本目录是本次执行证据，不是新计划。详见 [result.json](result.json)。

## 本次已执行

| 层级 | 结果 | 证据/边界 |
|---|---|---|
| 全部工作流节点族单元及冻结源差分 | 1,462通过，165.92秒 | [输出](node-families.txt)；含测试替身和纯算法比较，不能当1,462项原生E2E |
| 9个剩余节点专项规则、差分、worker | 52通过，18.90秒 | [输出](nine-node-regression.txt)；与上一行存在重叠，不累加为独立覆盖数 |
| 213节点/639槽位来源映射、证据路径与范围护栏 | 77通过，1.78秒 | [输出](mapping-scope.txt)；检验登记完整性，不证明所有实机通过 |
| 生产执行器注册 | 12通过，0.44秒 | [输出](registry.txt)；画布工具/原版注册机制按现有规则区分 |
| 正式unsigned macOS arm64包：热键、鼠标、图像 | 三者均完成UI配置→保存→原生正常关窗→重开→2秒超时失败→UI停止 | JSON逐项链接见result.json；不是 BrowserWindow.destroy；不是正向触发通过 |
| 真实屏幕图像执行器 | 实际Pillow采集、OpenCV匹配成功，输出(716,502)、置信度0.9825196862220764，image_event变量一致 | 源码生产执行器直接调用；不替代正式窗口正向E2E |

正式包异常路径：
- [图像](../formal-desktop-platform-electron-UPhEVj/result.json)
- [热键](../formal-desktop-platform-electron-M920se/result.json)
- [鼠标](../formal-desktop-platform-electron-GjPT25/result.json)：额外捕获实际worker PID，停止后用进程存在性检查确认退出。

脚本沿用 `scripts/smoke-studio-backend-b6-desktop-platform.mjs`。`AUTOFLOW_NATIVE_TRIGGER=hotkey_trigger|mouse_trigger|image_trigger` 启用对应节点，`AUTOFLOW_NATIVE_NEGATIVE_ONLY=1` 只跑异常链路并输出 **partial-negative-paths-only**。不设置此变量时，正向触发仍是硬断言，失败即报告失败，未删除或放宽原断言。脚本经 `node --check` 及真实执行验证；生产代码没有修改，因此没有重复冻结和打包。

复现示例：

```sh
AUTOFLOW_NATIVE_TRIGGER=mouse_trigger AUTOFLOW_NATIVE_NEGATIVE_ONLY=1 node scripts/smoke-studio-backend-b6-desktop-platform.mjs --executable apps/desktop/dist/mac-arm64/AutoFlow.app/Contents/MacOS/AutoFlow
```

出现 `saved-close-studio-through-native-ui` 时用真实系统关闭按钮关闭测试Studio；脚本从主窗口重开并继续。正向模式出现 `running-await-native-event` 后，必须实际提供全局输入或屏幕目标。图像夹具由脚本生成，Retina须显示为模板实际物理像素大小；PNG不包含用户信息。脚本自动清理独立临时工作区，不使用真实用户数据库。

## 失败与阻塞（全部保留）

- 热键/鼠标正向90秒超时：不能判断为产品已通过。独立pynput监听器确认可信且run loop在运行，但工具向应用发送的按键/点击没有出现在全局监听中（25秒窗口均为0事件，见[input-diagnostic.txt](input-diagnostic.txt)）。仍需实体键盘与鼠标输入验证；没有通过注入回调假装触发。
- 一次鼠标重开时测试脚本点击到尚在变动的工具栏，打开了导出面板。脚本现等待原生关闭点击完成、连接恢复和布局稳定；后续三个正常重开成功。保留失败目录`tGka9w`。
- 图像正式包四次正向运行超时：最高匹配度约8.6–9.5%；实际屏幕采集对照也未匹配到预期目标。工具能读取图片窗口，并不保证该图片在整屏采集时处于前台。后来在无测试窗口遮挡时生产执行器匹配成功。正式包的正向成功、区域、多显示器仍未通过，不能用源码探针补标。
- 本地HTML夹具被浏览器URL安全策略拒绝，未通过其他浏览器或HTTP转发绕过。后改用系统预览打开静态PNG，避免执行HTML。
- `shutdown_system`、`lock_screen`、`sound_trigger`、`printer_call`需要Windows环境；声音节点监听扬声器输出峰值，打印还需要对应设备。未执行本机关机/锁屏；Mac拒绝分支不计Windows成功。
- `face_trigger`、`gesture_trigger`需要摄像头真实目标和权限。仅确认设备存在，没有拍摄用户、修改摄像头权限或用虚拟回调核销。

已向用户请求Windows环境、实体输入和摄像头目标配合，尚未收到结果。全部失败目录、各次错误及剩余9项逐节点说明由result.json索引。macOS Intel/Windows没有实测，不标通过。
