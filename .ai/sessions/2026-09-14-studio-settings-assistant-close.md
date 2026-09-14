# Studio AI 配置关闭

新增受控 SettingsCloseHandler，executeClientAction 等待真实关闭决定；Toolbar 旧事件不直接隐藏窗口。配置待决取消/保存失败/重复命令均返回失败。useConfirm 卸载与替换解析旧等待，晚到调用取消，避免命令挂起。

13 项新测试，相关 81 项通过。测试初次 executeClientAction 签名写错已修正，未把这一失败当作功能缺陷证据。后续处理 MCP 连接/离开，保留宿主未验收状态。未启用 i18n，未动其它任务改动。
