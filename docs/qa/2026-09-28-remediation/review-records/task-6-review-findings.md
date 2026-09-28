# Task6 initial review at23247c28 — three Important

1. ConfigPanel.tsx314-322把模块onChange送入updateNodeConfig，但getNodeConfigData210-217规定label始终outer。BasicModuleConfigs GroupConfig1724-1727/1785-1789、SubflowHeaderConfig1844-1848仍回调写label；nested的config.label会被outerlabel覆盖。显式outer label写入口，subflowName等配置nested，补nested group/subflow回归。
2. aiAssistantSkills603-613及628-638把AI label转name作为备注，但转换后updateNodeConfig会写nested Project End config.name（环境名）而非outer备注。rename_node725-733已有正确outer写法。单/批都将label兼容备注经updateNodeData，真正runtime config经updateNodeConfig；补End AI label/remark回归。
3. GroupNode37-69仍raw读取isSubflow/subflowName/subflowGroupId并updateNodesData写配置；SubflowHeaderNode85-117重复检查/重命名传播raw读写；ModuleNode74-80nested子流程目标查找outer。导致面板与画布样式/重复校验/传播/双击跳转分歧。复用共享配置读写，label/尺寸留outer，补相应nested测试。

Reviewer: /root/studio_config_review. Spec fail, quality Needs fixes, Critical0/Important3/Minor0. Full native/build/default remains root pending. Exact source file root: apps/desktop/src/renderer/domains/workflows/.
