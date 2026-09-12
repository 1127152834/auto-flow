# 控件使用点明细

- 日期：2026-09-12；状态：confirmed（只读静态盘点，不代表视觉验收）。
- 主线已提交基准：c7c3021；main-working 为盘点时主目录工作树，最新已含语言/时区目录、代理协议及模型品牌资源提交；未接入自动化草稿单列。
- 方法：TypeScript AST；仅统计 JSX 起始/自闭标签，不数闭标签；map 中一处源码可能对应多个运行控件；作用域根据 main.tsx 的相对静态 import/export 传递可达性，不等同于所有导出都实际渲染。忽略测试文件和 tests 目录。
- 相对路径以 apps/desktop/src/renderer/ 为共同前缀；行号以对应快照为准，SHA-256 见同名 JSON。共享内部实现和领域调用分别列出，不相加当作屏幕控件数量。

## committed

| 文件:行 | 标签 | 作用域 | 类型/语义/滚动 |
|---|---|---|---|
| app/App.tsx:141 | State | app-runtime |  |
| app/App.tsx:143 | div | app-runtime | "status" |
| app/App.tsx:143 | div | app-runtime | "alert" |
| app/App.tsx:143 | button | app-runtime | "button" |
| app/ApplicationHeader.tsx:12 | button | app-runtime | "button" |
| app/ApplicationHeader.tsx:13 | button | app-runtime | "button" |
| app/ApplicationHeader.tsx:13 | span | app-runtime | "status" |
| domains/dashboard/components/DashboardCards.tsx:26 | button | app-runtime | "button" |
| domains/dashboard/pages/DashboardPage.tsx:9 | div | app-runtime | "status" / "正在加载资源概况" |
| domains/dashboard/pages/DashboardPage.tsx:9 | section | app-runtime | "alert" |
| domains/dashboard/pages/DashboardPage.tsx:9 | Button | app-runtime |  |
| domains/kernels/components/DeleteKernelDialog.tsx:22 | AlertDialog | app-runtime |  |
| domains/kernels/components/DeleteKernelDialog.tsx:23 | AlertDialogContent | app-runtime |  |
| domains/kernels/components/DeleteKernelDialog.tsx:24 | AlertDialogTitle | app-runtime |  |
| domains/kernels/components/DeleteKernelDialog.tsx:25 | AlertDialogDescription | app-runtime |  |
| domains/kernels/components/DeleteKernelDialog.tsx:26 | div | app-runtime | "alert" |
| domains/kernels/components/DeleteKernelDialog.tsx:26 | Button | app-runtime | "button" |
| domains/kernels/components/DeleteKernelDialog.tsx:27 | p | app-runtime | "alert" |
| domains/kernels/components/DeleteKernelDialog.tsx:29 | AlertDialogCancel | app-runtime |  |
| domains/kernels/components/DeleteKernelDialog.tsx:29 | Button | app-runtime | "button" |
| domains/kernels/components/DeleteKernelDialog.tsx:30 | AlertDialogAction | app-runtime |  |
| domains/kernels/components/DeleteKernelDialog.tsx:30 | Button | app-runtime | "button" |
| domains/kernels/components/KernelManagerDialog.tsx:202 | Dialog | app-runtime |  |
| domains/kernels/components/KernelManagerDialog.tsx:203 | DialogContent | app-runtime | scroll container |
| domains/kernels/components/KernelManagerDialog.tsx:207 | DialogTitle | app-runtime |  |
| domains/kernels/components/KernelManagerDialog.tsx:207 | DialogDescription | app-runtime |  |
| domains/kernels/components/KernelManagerDialog.tsx:208 | Button | app-runtime | "button" / "关闭内核管理" |
| domains/kernels/components/KernelManagerDialog.tsx:211 | div | app-runtime | "alert" |
| domains/kernels/components/KernelManagerDialog.tsx:211 | Button | app-runtime | "button" |
| domains/kernels/components/KernelManagerDialog.tsx:232 | Button | app-runtime | "button" |
| domains/kernels/components/KernelManagerDialog.tsx:235 | Button | app-runtime | "button" |
| domains/kernels/components/KernelManagerDialog.tsx:237 | p | app-runtime | "alert" |
| domains/kernels/components/KernelManagerDialog.tsx:238 | p | app-runtime | "alert" |
| domains/kernels/components/KernelManagerDialog.tsx:239 | p | app-runtime | "alert" |
| domains/kernels/components/KernelManagerDialog.tsx:240 | p | app-runtime | "status" |
| domains/kernels/components/KernelOperationStatus.tsx:32 | div | app-runtime | "status" |
| domains/kernels/components/KernelOperationStatus.tsx:37 | div | app-runtime | "progressbar" / "内核安装进度" |
| domains/kernels/components/KernelOperationStatus.tsx:41 | p | app-runtime | "alert" |
| domains/kernels/components/KernelOperationStatus.tsx:42 | Button | app-runtime | "button" |
| domains/kernels/components/KernelOperationStatus.tsx:43 | Button | app-runtime | "button" |
| domains/kernels/components/KernelReleaseList.tsx:66 | Button | app-runtime | "button" |
| domains/kernels/components/KernelReleaseList.tsx:67 | Button | app-runtime | "button" |
| domains/kernels/components/KernelReleaseList.tsx:68 | Button | app-runtime | "button" |
| domains/kernels/components/KernelReleaseList.tsx:69 | Button | app-runtime | "button" |
| domains/kernels/components/LicensePanel.tsx:43 | Button | app-runtime | "button" |
| domains/kernels/components/LicensePanel.tsx:47 | Input | app-runtime | "password" |
| domains/kernels/components/LicensePanel.tsx:48 | Button | app-runtime | "submit" |
| domains/kernels/components/LicensePanel.tsx:50 | p | app-runtime | "alert" |
| domains/kernels/components/LicensePanel.tsx:51 | p | app-runtime | "alert" |
| domains/models/components/ModelDeleteDialog.tsx:11 | Modal | app-runtime |  |
| domains/models/components/ModelDeleteDialog.tsx:11 | Button | app-runtime | "button" |
| domains/models/components/ModelDeleteDialog.tsx:11 | Button | app-runtime | "button" |
| domains/models/components/ModelDeleteDialog.tsx:12 | p | app-runtime | "alert" |
| domains/models/components/ModelDirectory.tsx:16 | Button | app-runtime |  |
| domains/models/components/ModelDirectory.tsx:16 | Button | app-runtime |  |
| domains/models/components/ModelDirectory.tsx:17 | Input | app-runtime | "搜索模型" |
| domains/models/components/ModelDirectory.tsx:17 | select | app-runtime | "模型状态" |
| domains/models/components/ModelDirectory.tsx:18 | div | app-runtime | scroll container |
| domains/models/components/ModelDirectory.tsx:18 | table | app-runtime |  |
| domains/models/components/ModelDirectory.tsx:19 | Button | app-runtime | {`${model.displayName} 测试模型`} |
| domains/models/components/ModelDirectory.tsx:19 | DropdownMenu | app-runtime |  |
| domains/models/components/ModelDirectory.tsx:19 | DropdownMenuTrigger | app-runtime |  |
| domains/models/components/ModelDirectory.tsx:19 | Button | app-runtime | {`${model.displayName} 更多操作`} |
| domains/models/components/ModelDirectory.tsx:19 | DropdownMenuContent | app-runtime |  |
| domains/models/components/ModelDirectory.tsx:19 | DropdownMenuItem | app-runtime |  |
| domains/models/components/ModelDirectory.tsx:19 | DropdownMenuItem | app-runtime |  |
| domains/models/components/ModelDirectory.tsx:19 | DropdownMenuSeparator | app-runtime |  |
| domains/models/components/ModelDirectory.tsx:19 | DropdownMenuItem | app-runtime |  |
| domains/models/components/ModelEditor.tsx:59 | Modal | app-runtime |  |
| domains/models/components/ModelEditor.tsx:59 | Button | app-runtime | "button" |
| domains/models/components/ModelEditor.tsx:59 | Button | app-runtime | "button" |
| domains/models/components/ModelEditor.tsx:61 | FormField | app-runtime |  |
| domains/models/components/ModelEditor.tsx:61 | Button | app-runtime | "button" / "刷新模型目录" |
| domains/models/components/ModelEditor.tsx:62 | Button | app-runtime | "button" |
| domains/models/components/ModelForm.tsx:24 | p | app-runtime | "alert" |
| domains/models/components/ModelForm.tsx:25 | FormField | app-runtime |  |
| domains/models/components/ModelForm.tsx:25 | Input | app-runtime |  |
| domains/models/components/ModelForm.tsx:26 | FormField | app-runtime |  |
| domains/models/components/ModelForm.tsx:27 | Input | app-runtime | "模型标识" |
| domains/models/components/ModelForm.tsx:27 | Button | app-runtime | "button" / "复制模型标识" |
| domains/models/components/ModelForm.tsx:27 | span | app-runtime | "status" |
| domains/models/components/ModelForm.tsx:29 | FormField | app-runtime |  |
| domains/models/components/ModelForm.tsx:29 | Input | app-runtime | "上下文窗口" |
| domains/models/components/ModelForm.tsx:31 | button | app-runtime | "button" / {`移除标签 ${tag}`} |
| domains/models/components/ModelForm.tsx:32 | input | app-runtime | "自定义标签" |
| domains/models/components/ModelForm.tsx:34 | details | app-runtime |  |
| domains/models/components/ModelForm.tsx:34 | summary | app-runtime |  |
| domains/models/components/ModelForm.tsx:34 | FormField | app-runtime |  |
| domains/models/components/ModelForm.tsx:34 | Textarea | app-runtime |  |
| domains/models/components/ModelIdInput.tsx:11 | Input | app-runtime | "模型标识" |
| domains/models/components/ModelIdInput.tsx:12 | div | app-runtime | "listbox" / "模型目录" / scroll container |
| domains/models/components/ModelIdInput.tsx:13 | button | app-runtime | "option" |
| domains/models/components/ModelTestPanel.tsx:8 | Button | app-runtime | "button" |
| domains/models/components/ModelTestPanel.tsx:10 | div | app-runtime | "alert" |
| domains/models/components/ModelTestPanel.tsx:10 | div | app-runtime | "status" |
| domains/models/components/ModelTestPanel.tsx:10 | details | app-runtime |  |
| domains/models/components/ModelTestPanel.tsx:10 | summary | app-runtime |  |
| domains/models/components/ProviderCatalogStep.tsx:12 | Input | app-runtime | "搜索供应商目录" |
| domains/models/components/ProviderCatalogStep.tsx:15 | button | app-runtime | "button" |
| domains/models/components/ProviderCatalogStep.tsx:18 | button | app-runtime | "button" |
| domains/models/components/ProviderConnectionStep.tsx:15 | div | app-runtime | "alert" |
| domains/models/components/ProviderConnectionStep.tsx:18 | FormField | app-runtime |  |
| domains/models/components/ProviderConnectionStep.tsx:18 | Input | app-runtime |  |
| domains/models/components/ProviderConnectionStep.tsx:19 | FormField | app-runtime |  |
| domains/models/components/ProviderConnectionStep.tsx:19 | Select | app-runtime |  |
| domains/models/components/ProviderConnectionStep.tsx:21 | FormField | app-runtime |  |
| domains/models/components/ProviderConnectionStep.tsx:21 | Input | app-runtime |  |
| domains/models/components/ProviderConnectionStep.tsx:22 | FormField | app-runtime |  |
| domains/models/components/ProviderConnectionStep.tsx:22 | Input | app-runtime | "password" |
| domains/models/components/ProviderConnectionStep.tsx:23 | FormField | app-runtime |  |
| domains/models/components/ProviderConnectionStep.tsx:23 | Textarea | app-runtime |  |
| domains/models/components/ProviderConnectionStep.tsx:24 | Switch | app-runtime | "启用供应商" |
| domains/models/components/ProviderDeleteDialog.tsx:13 | Modal | app-runtime |  |
| domains/models/components/ProviderDeleteDialog.tsx:14 | Button | app-runtime |  |
| domains/models/components/ProviderDeleteDialog.tsx:15 | Button | app-runtime |  |
| domains/models/components/ProviderDeleteDialog.tsx:18 | p | app-runtime | "alert" |
| domains/models/components/ProviderDetail.tsx:23 | Button | app-runtime |  |
| domains/models/components/ProviderDetail.tsx:23 | Button | app-runtime |  |
| domains/models/components/ProviderDetail.tsx:24 | DropdownMenu | app-runtime |  |
| domains/models/components/ProviderDetail.tsx:24 | DropdownMenuTrigger | app-runtime |  |
| domains/models/components/ProviderDetail.tsx:24 | Button | app-runtime | "供应商更多操作" |
| domains/models/components/ProviderDetail.tsx:24 | DropdownMenuContent | app-runtime |  |
| domains/models/components/ProviderDetail.tsx:24 | DropdownMenuItem | app-runtime |  |
| domains/models/components/ProviderDetail.tsx:24 | DropdownMenuSeparator | app-runtime |  |
| domains/models/components/ProviderDetail.tsx:24 | DropdownMenuItem | app-runtime |  |
| domains/models/components/ProviderModelsStep.tsx:15 | Input | app-runtime | "搜索发现的模型" |
| domains/models/components/ProviderModelsStep.tsx:15 | Button | app-runtime | "button" |
| domains/models/components/ProviderModelsStep.tsx:16 | div | app-runtime | scroll container |
| domains/models/components/ProviderModelsStep.tsx:16 | Checkbox | app-runtime | {`选择 ${model.displayName}`} |
| domains/models/components/ProviderSidebar.tsx:14 | Button | app-runtime | "添加供应商" |
| domains/models/components/ProviderSidebar.tsx:15 | Input | app-runtime | "搜索供应商" |
| domains/models/components/ProviderSidebar.tsx:17 | button | app-runtime | "button" |
| domains/models/components/ProviderWizard.tsx:62 | Button | app-runtime |  |
| domains/models/components/ProviderWizard.tsx:62 | Button | app-runtime |  |
| domains/models/components/ProviderWizard.tsx:62 | Button | app-runtime |  |
| domains/models/components/ProviderWizard.tsx:62 | Button | app-runtime |  |
| domains/models/components/ProviderWizard.tsx:62 | Button | app-runtime |  |
| domains/models/components/ProviderWizard.tsx:62 | Button | app-runtime |  |
| domains/models/components/ProviderWizard.tsx:62 | Button | app-runtime |  |
| domains/models/components/ProviderWizard.tsx:62 | Button | app-runtime |  |
| domains/models/components/ProviderWizard.tsx:62 | Button | app-runtime |  |
| domains/models/components/ProviderWizard.tsx:64 | Modal | app-runtime |  |
| domains/models/components/ProviderWizard.tsx:69 | div | app-runtime | "alert" |
| domains/models/pages/ModelManagementPage.tsx:41 | Button | app-runtime | "添加模型供应商" |
| domains/models/pages/ModelManagementPage.tsx:42 | div | app-runtime | "alert" |
| domains/models/pages/ModelManagementPage.tsx:42 | Button | app-runtime |  |
| domains/models/pages/ModelManagementPage.tsx:43 | div | app-runtime | "status" |
| domains/models/pages/ModelManagementPage.tsx:43 | div | app-runtime | "alert" |
| domains/models/pages/ModelManagementPage.tsx:43 | Button | app-runtime |  |
| domains/models/pages/ModelManagementPage.tsx:43 | Button | app-runtime |  |
| domains/profiles/components/AdvancedFields.tsx:13 | details | app-runtime |  |
| domains/profiles/components/AdvancedFields.tsx:14 | summary | app-runtime |  |
| domains/profiles/components/AdvancedFields.tsx:21 | FormField | app-runtime |  |
| domains/profiles/components/AdvancedFields.tsx:22 | Textarea | app-runtime |  |
| domains/profiles/components/AdvancedFields.tsx:24 | FormField | app-runtime |  |
| domains/profiles/components/AdvancedFields.tsx:25 | Textarea | app-runtime |  |
| domains/profiles/components/BasicFields.tsx:14 | FormField | app-runtime |  |
| domains/profiles/components/BasicFields.tsx:15 | Input | app-runtime |  |
| domains/profiles/components/BasicFields.tsx:17 | FormField | app-runtime |  |
| domains/profiles/components/BasicFields.tsx:18 | Input | app-runtime |  |
| domains/profiles/components/BasicFields.tsx:21 | FormField | app-runtime |  |
| domains/profiles/components/BasicFields.tsx:22 | Input | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:50 | FormField | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:51 | Input | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:51 | datalist | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:53 | FormField | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:54 | Input | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:54 | datalist | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:60 | Switch | app-runtime | "自定义尺寸" |
| domains/profiles/components/EnvironmentFields.tsx:77 | FormField | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:78 | Input | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:81 | FormField | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:82 | Input | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:84 | Select | app-runtime | "视口预设" |
| domains/profiles/components/EnvironmentFields.tsx:88 | p | app-runtime | "alert" |
| domains/profiles/components/EnvironmentFields.tsx:91 | FormField | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:92 | Select | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:94 | FormField | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:95 | Select | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:98 | FormField | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:99 | Input | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:99 | datalist | app-runtime |  |
| domains/profiles/components/KernelProxyFields.tsx:45 | p | app-runtime | "alert" |
| domains/profiles/components/KernelProxyFields.tsx:50 | Select | app-runtime | "浏览器内核" |
| domains/profiles/components/KernelProxyFields.tsx:58 | Button | app-runtime | "button" |
| domains/profiles/components/KernelProxyFields.tsx:60 | p | app-runtime | "alert" |
| domains/profiles/components/KernelProxyFields.tsx:62 | FormField | app-runtime |  |
| domains/profiles/components/KernelProxyFields.tsx:63 | Select | app-runtime |  |
| domains/profiles/components/KernelProxyFields.tsx:66 | p | app-runtime | "alert" |
| domains/profiles/components/KernelProxyFields.tsx:68 | FormField | app-runtime |  |
| domains/profiles/components/KernelProxyFields.tsx:69 | Select | app-runtime |  |
| domains/profiles/components/KernelProxyFields.tsx:75 | FormField | app-runtime |  |
| domains/profiles/components/KernelProxyFields.tsx:76 | Select | app-runtime |  |
| domains/profiles/components/KernelProxyFields.tsx:81 | FormField | app-runtime |  |
| domains/profiles/components/KernelProxyFields.tsx:82 | Select | app-runtime |  |
| domains/profiles/components/KernelProxyFields.tsx:101 | Switch | app-runtime | {label} |
| domains/profiles/components/ProfileActionDialog.tsx:67 | Dialog | app-runtime |  |
| domains/profiles/components/ProfileActionDialog.tsx:68 | DialogContent | app-runtime |  |
| domains/profiles/components/ProfileActionDialog.tsx:69 | DialogTitle | app-runtime |  |
| domains/profiles/components/ProfileActionDialog.tsx:70 | DialogDescription | app-runtime |  |
| domains/profiles/components/ProfileActionDialog.tsx:71 | div | app-runtime | "alert" |
| domains/profiles/components/ProfileActionDialog.tsx:71 | Button | app-runtime | "button" |
| domains/profiles/components/ProfileActionDialog.tsx:73 | FormField | app-runtime |  |
| domains/profiles/components/ProfileActionDialog.tsx:74 | Input | app-runtime |  |
| domains/profiles/components/ProfileActionDialog.tsx:80 | p | app-runtime | "alert" |
| domains/profiles/components/ProfileActionDialog.tsx:83 | Button | app-runtime | "button" |
| domains/profiles/components/ProfileActionDialog.tsx:84 | Button | app-runtime | "submit" |
| domains/profiles/components/ProfileFormDialog.tsx:168 | Dialog | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:169 | DialogContent | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:171 | DialogTitle | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:172 | DialogDescription | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:174 | div | app-runtime | "alert" |
| domains/profiles/components/ProfileFormDialog.tsx:174 | Button | app-runtime | "button" |
| domains/profiles/components/ProfileFormDialog.tsx:176 | form | app-runtime | scroll container |
| domains/profiles/components/ProfileFormDialog.tsx:178 | p | app-runtime | "alert" |
| domains/profiles/components/ProfileFormDialog.tsx:179 | Tabs | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:180 | TabsList | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:181 | TabsTrigger | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:182 | TabsTrigger | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:183 | TabsTrigger | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:184 | TabsTrigger | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:186 | TabsContent | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:187 | TabsContent | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:188 | TabsContent | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:197 | TabsContent | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:203 | Button | app-runtime | "button" |
| domains/profiles/components/ProfileFormDialog.tsx:204 | Button | app-runtime | "submit" |
| domains/profiles/components/ProfileList.tsx:37 | Button | app-runtime | "button" / {`编辑 ${profile.name}`} |
| domains/profiles/components/ProfileList.tsx:38 | Button | app-runtime | "button" / {`复制 ${profile.name}`} |
| domains/profiles/components/ProfileList.tsx:39 | Button | app-runtime | "button" / {`重新生成 ${profile.name} 的指纹`} |
| domains/profiles/components/ProfileList.tsx:40 | Button | app-runtime | "button" / {`删除 ${profile.name}`} |
| domains/profiles/components/UnsavedChangesDialog.tsx:18 | AlertDialog | app-runtime |  |
| domains/profiles/components/UnsavedChangesDialog.tsx:19 | AlertDialogContent | app-runtime |  |
| domains/profiles/components/UnsavedChangesDialog.tsx:20 | AlertDialogTitle | app-runtime |  |
| domains/profiles/components/UnsavedChangesDialog.tsx:21 | AlertDialogDescription | app-runtime |  |
| domains/profiles/components/UnsavedChangesDialog.tsx:23 | AlertDialogCancel | app-runtime |  |
| domains/profiles/components/UnsavedChangesDialog.tsx:23 | Button | app-runtime |  |
| domains/profiles/components/UnsavedChangesDialog.tsx:24 | AlertDialogAction | app-runtime |  |
| domains/profiles/components/UnsavedChangesDialog.tsx:24 | Button | app-runtime |  |
| domains/profiles/pages/BrowserManagementPage.tsx:77 | Button | app-runtime | "button" |
| domains/profiles/pages/BrowserManagementPage.tsx:84 | Input | app-runtime | "search" |
| domains/profiles/pages/BrowserManagementPage.tsx:86 | Select | app-runtime | "代理模式筛选" |
| domains/profiles/pages/BrowserManagementPage.tsx:94 | p | app-runtime | "status" |
| domains/profiles/pages/BrowserManagementPage.tsx:95 | div | app-runtime | "alert" |
| domains/profiles/pages/BrowserManagementPage.tsx:95 | Button | app-runtime | "button" |
| domains/profiles/pages/BrowserManagementPage.tsx:97 | div | app-runtime | "status" / "正在加载浏览器配置" |
| domains/profiles/pages/BrowserManagementPage.tsx:98 | section | app-runtime | "alert" |
| domains/profiles/pages/BrowserManagementPage.tsx:98 | Button | app-runtime | "button" |
| domains/profiles/pages/BrowserManagementPage.tsx:99 | section | app-runtime | "status" |
| domains/profiles/pages/BrowserManagementPage.tsx:99 | Button | app-runtime | "button" |
| domains/profiles/pages/BrowserManagementPage.tsx:100 | section | app-runtime | "status" |
| domains/profiles/pages/BrowserManagementPage.tsx:106 | Button | app-runtime | "button" |
| domains/profiles/pages/BrowserManagementPage.tsx:108 | Button | app-runtime | "button" |
| domains/profiles/pages/BrowserManagementPage.tsx:124 | Toaster | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:33 | Button | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:38 | div | app-runtime | scroll container |
| domains/proxies/components/LocalProxyGroups.tsx:39 | table | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | Button | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | AlertDialog | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | AlertDialogTrigger | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | Button | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | AlertDialogContent | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | AlertDialogTitle | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | AlertDialogDescription | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | AlertDialogCancel | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | Button | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | AlertDialogAction | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | Button | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:111 | Dialog | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:112 | DialogContent | app-runtime | scroll container |
| domains/proxies/components/LocalProxyGroups.tsx:113 | DialogTitle | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:114 | DialogDescription | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:117 | FormField | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:117 | Input | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:118 | FormField | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:118 | Input | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:122 | Input | app-runtime | "搜索组成员" |
| domains/proxies/components/LocalProxyGroups.tsx:122 | Select | app-runtime | "筛选成员健康" |
| domains/proxies/components/LocalProxyGroups.tsx:123 | div | app-runtime | scroll container |
| domains/proxies/components/LocalProxyGroups.tsx:124 | input | app-runtime | "checkbox" |
| domains/proxies/components/LocalProxyGroups.tsx:132 | Button | app-runtime | "button" / {`上移 ${label}`} |
| domains/proxies/components/LocalProxyGroups.tsx:132 | Button | app-runtime | "button" / {`下移 ${label}`} |
| domains/proxies/components/LocalProxyGroups.tsx:132 | Button | app-runtime | "button" / {`移除 ${label}`} |
| domains/proxies/components/LocalProxyGroups.tsx:135 | div | app-runtime | "alert" |
| domains/proxies/components/LocalProxyGroups.tsx:135 | Button | app-runtime | "button" |
| domains/proxies/components/LocalProxyGroups.tsx:136 | DialogClose | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:136 | Button | app-runtime | "button" |
| domains/proxies/components/LocalProxyGroups.tsx:136 | Button | app-runtime | "submit" |
| domains/proxies/components/ProxyConnection.tsx:45 | Button | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:70 | Button | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:73 | Button | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:74 | AlertDialog | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:75 | AlertDialogTrigger | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:75 | Button | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:76 | AlertDialogContent | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:77 | AlertDialogTitle | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:78 | AlertDialogDescription | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:80 | AlertDialogCancel | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:80 | Button | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:81 | AlertDialogAction | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:81 | Button | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:87 | p | app-runtime | "alert" |
| domains/proxies/components/ProxyConnection.tsx:128 | Dialog | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:129 | DialogContent | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:130 | DialogTitle | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:131 | DialogDescription | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:133 | FormField | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:134 | Input | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:139 | Input | app-runtime | {showKey ? 'text' : 'password'} |
| domains/proxies/components/ProxyConnection.tsx:140 | Button | app-runtime | "button" |
| domains/proxies/components/ProxyConnection.tsx:143 | p | app-runtime | "alert" |
| domains/proxies/components/ProxyConnection.tsx:146 | DialogClose | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:146 | Button | app-runtime | "button" |
| domains/proxies/components/ProxyConnection.tsx:147 | Button | app-runtime | "submit" |
| domains/proxies/components/ProxyDetailDrawer.tsx:62 | Dialog | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:63 | DialogContent | app-runtime | scroll container |
| domains/proxies/components/ProxyDetailDrawer.tsx:66 | DialogTitle | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:67 | DialogDescription | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:69 | Button | app-runtime | "关闭代理详情" |
| domains/proxies/components/ProxyDetailDrawer.tsx:71 | Tabs | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:72 | TabsList | app-runtime | scroll container |
| domains/proxies/components/ProxyDetailDrawer.tsx:73 | TabsTrigger | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:74 | TabsTrigger | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:75 | TabsTrigger | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:76 | TabsTrigger | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:78 | TabsContent | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:81 | Button | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:84 | Input | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:85 | Switch | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:86 | Button | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:100 | p | app-runtime | "alert" |
| domains/proxies/components/ProxyDetailDrawer.tsx:107 | TabsContent | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:111 | AlertDialog | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:112 | AlertDialogTrigger | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:112 | Button | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:113 | AlertDialogContent | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:114 | AlertDialogTitle | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:115 | AlertDialogDescription | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:116 | AlertDialogCancel | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:116 | Button | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:116 | AlertDialogAction | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:116 | Button | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:119 | Button | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:127 | TabsContent | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:130 | Select | app-runtime | "凭据协议" |
| domains/proxies/components/ProxyDetailDrawer.tsx:148 | TabsContent | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:192 | Dialog | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:193 | DialogContent | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:194 | DialogTitle | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:195 | DialogDescription | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:196 | Input | app-runtime | "搜索地点" |
| domains/proxies/components/ProxyDetailDrawer.tsx:196 | Select | app-runtime | "地点运营商" |
| domains/proxies/components/ProxyDetailDrawer.tsx:197 | div | app-runtime | scroll container |
| domains/proxies/components/ProxyDetailDrawer.tsx:198 | input | app-runtime | "radio" |
| domains/proxies/components/ProxyDetailDrawer.tsx:201 | Button | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:201 | Button | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:208 | Select | app-runtime | "轮换模式" |
| domains/proxies/components/ProxyDetailDrawer.tsx:212 | Switch | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:212 | Input | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:216 | Button | app-runtime |  |
| domains/proxies/components/ProxyFleet.tsx:61 | Input | app-runtime |  |
| domains/proxies/components/ProxyFleet.tsx:63 | Select | app-runtime | "健康状态" |
| domains/proxies/components/ProxyFleet.tsx:69 | Select | app-runtime | "运营商" |
| domains/proxies/components/ProxyFleet.tsx:73 | Select | app-runtime | "城市" |
| domains/proxies/components/ProxyFleet.tsx:84 | div | app-runtime | scroll container |
| domains/proxies/components/ProxyFleet.tsx:85 | table | app-runtime |  |
| domains/proxies/components/ProxyFleet.tsx:109 | Button | app-runtime |  |
| domains/proxies/components/ProxyFleet.tsx:110 | Button | app-runtime |  |
| domains/proxies/components/ProxyFleet.tsx:123 | Button | app-runtime |  |
| domains/proxies/components/ProxyFleet.tsx:123 | Button | app-runtime |  |
| domains/proxies/pages/ProxyManagementPage.tsx:42 | ProxyPageSkeleton | app-runtime |  |
| domains/proxies/pages/ProxyManagementPage.tsx:45 | div | app-runtime | "alert" |
| domains/proxies/pages/ProxyManagementPage.tsx:47 | Button | app-runtime |  |
| domains/proxies/pages/ProxyManagementPage.tsx:111 | Toaster | app-runtime |  |
| domains/proxies/pages/ProxyManagementPage.tsx:117 | div | app-runtime | "status" / "正在加载代理管理" |
| domains/settings/components/DiagnosticDialog.tsx:43 | Modal | app-runtime |  |
| domains/settings/components/DiagnosticDialog.tsx:43 | Button | app-runtime |  |
| domains/settings/components/DiagnosticDialog.tsx:43 | Button | app-runtime |  |
| domains/settings/components/DiagnosticDialog.tsx:45 | Checkbox | app-runtime | "添加最近日志" |
| domains/settings/components/DiagnosticDialog.tsx:46 | p | app-runtime | "status" |
| domains/settings/components/DiagnosticDialog.tsx:46 | div | app-runtime | "alert" |
| domains/settings/components/DiagnosticDialog.tsx:46 | Button | app-runtime |  |
| domains/settings/components/DiagnosticDialog.tsx:46 | div | app-runtime | "alert" |
| domains/settings/components/DiagnosticDialog.tsx:46 | pre | app-runtime | scroll container |
| domains/settings/pages/SettingsPage.tsx:42 | main | app-runtime | "status" |
| domains/settings/pages/SettingsPage.tsx:43 | p | app-runtime | "alert" |
| domains/settings/pages/SettingsPage.tsx:43 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:45 | div | app-runtime | "alert" |
| domains/settings/pages/SettingsPage.tsx:45 | div | app-runtime | "alert" |
| domains/settings/pages/SettingsPage.tsx:45 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:45 | div | app-runtime | "status" |
| domains/settings/pages/SettingsPage.tsx:46 | Tabs | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:46 | TabsList | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:46 | TabsTrigger | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:46 | TabsTrigger | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:46 | TabsTrigger | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:47 | TabsContent | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:47 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:47 | button | app-runtime | "button" |
| domains/settings/pages/SettingsPage.tsx:48 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:49 | Select | app-runtime | "界面缩放" |
| domains/settings/pages/SettingsPage.tsx:49 | Select | app-runtime | "减少动效" |
| domains/settings/pages/SettingsPage.tsx:50 | TabsContent | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:50 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:50 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:50 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:50 | code | app-runtime | scroll container |
| domains/settings/pages/SettingsPage.tsx:50 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:51 | TabsContent | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:51 | button | app-runtime | "button" |
| domains/settings/pages/SettingsPage.tsx:51 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:51 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:52 | Modal | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:52 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:52 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:52 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:52 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:52 | div | app-runtime | "alert" |
| domains/settings/pages/SettingsPage.tsx:52 | Toaster | app-runtime |  |
| shared/components/FormField.tsx:13 | p | shared-runtime | "alert" |
| shared/components/Modal.tsx:36 | Dialog | shared-runtime |  |
| shared/components/Modal.tsx:37 | DialogContent | shared-runtime |  |
| shared/components/Modal.tsx:65 | DialogTitle | shared-runtime |  |
| shared/components/Modal.tsx:66 | DialogDescription | shared-runtime |  |
| shared/components/Modal.tsx:68 | DialogClose | shared-runtime |  |
| shared/components/Modal.tsx:69 | Button | shared-runtime | "button" / {closeDisabled ? '正在处理，请稍候' : '关闭'} |
| shared/components/Modal.tsx:74 | div | shared-runtime | "region" / {`${title}内容`} / scroll container |
| shared/components/ResourceState.tsx:7 | section | not-main-entry | "status" |
| shared/components/ResourceState.tsx:8 | section | not-main-entry | "alert" |
| shared/components/ResourceState.tsx:8 | Button | not-main-entry |  |
| shared/components/ResourceState.tsx:9 | section | not-main-entry | "status" |
| shared/components/State.tsx:11 | section | shared-runtime | "status" |
| shared/components/Toaster.tsx:22 | div | shared-runtime | "status" |
| shared/components/Toaster.tsx:22 | Button | shared-runtime | "关闭通知" |
| shared/components/ui/alert-dialog.tsx:10 | AlertDialogPrimitive.Portal | shared-runtime |  |
| shared/components/ui/alert-dialog.tsx:10 | AlertDialogPrimitive.Overlay | shared-runtime |  |
| shared/components/ui/alert-dialog.tsx:10 | AlertDialogPrimitive.Content | shared-runtime |  |
| shared/components/ui/button.tsx:13 | button | shared-runtime |  |
| shared/components/ui/dialog.tsx:7 | DialogPrimitive.Root | shared-runtime |  |
| shared/components/ui/dialog.tsx:11 | DialogPrimitive.Close | shared-runtime |  |
| shared/components/ui/dialog.tsx:13 | DialogPrimitive.Title | shared-runtime |  |
| shared/components/ui/dialog.tsx:14 | DialogPrimitive.Description | shared-runtime |  |
| shared/components/ui/dialog.tsx:19 | DialogPrimitive.Portal | shared-runtime |  |
| shared/components/ui/dialog.tsx:20 | DialogPrimitive.Overlay | shared-runtime |  |
| shared/components/ui/dialog.tsx:21 | DialogPrimitive.Content | shared-runtime |  |
| shared/components/ui/dropdown-menu.tsx:7 | DropdownMenuPrimitive.Portal | shared-runtime |  |
| shared/components/ui/dropdown-menu.tsx:7 | DropdownMenuPrimitive.Content | shared-runtime |  |
| shared/components/ui/dropdown-menu.tsx:8 | DropdownMenuPrimitive.Item | shared-runtime |  |
| shared/components/ui/dropdown-menu.tsx:9 | DropdownMenuPrimitive.Separator | shared-runtime |  |
| shared/components/ui/input.tsx:5 | input | shared-runtime |  |
| shared/components/ui/select-radix.tsx:8 | SelectPrimitive.Trigger | not-main-entry |  |
| shared/components/ui/select-radix.tsx:9 | SelectPrimitive.Portal | not-main-entry |  |
| shared/components/ui/select-radix.tsx:9 | SelectPrimitive.Content | not-main-entry |  |
| shared/components/ui/select-radix.tsx:10 | SelectPrimitive.Item | not-main-entry |  |
| shared/components/ui/select.tsx:4 | select | shared-runtime |  |
| shared/components/ui/tabs.tsx:5 | TabsPrimitive.List | shared-runtime |  |
| shared/components/ui/tabs.tsx:6 | TabsPrimitive.Trigger | shared-runtime |  |
| shared/components/ui/tabs.tsx:7 | TabsPrimitive.Content | shared-runtime |  |
| shared/components/ui/textarea.tsx:5 | textarea | shared-runtime |  |
| shared/components/ui/tooltip.tsx:7 | TooltipPrimitive.Portal | not-main-entry |  |
| shared/components/ui/tooltip.tsx:7 | TooltipPrimitive.Content | not-main-entry |  |
## main-working

| 文件:行 | 标签 | 作用域 | 类型/语义/滚动 |
|---|---|---|---|
| app/App.tsx:141 | State | app-runtime |  |
| app/App.tsx:143 | div | app-runtime | "status" |
| app/App.tsx:143 | div | app-runtime | "alert" |
| app/App.tsx:143 | button | app-runtime | "button" |
| app/ApplicationHeader.tsx:12 | button | app-runtime | "button" |
| app/ApplicationHeader.tsx:13 | button | app-runtime | "button" |
| app/ApplicationHeader.tsx:13 | span | app-runtime | "status" |
| domains/automation/studio/pages/StudioPage.tsx:43 | button | not-main-entry | "button" |
| domains/automation/studio/pages/StudioPage.tsx:44 | Button | not-main-entry |  |
| domains/automation/studio/pages/StudioPage.tsx:44 | Button | not-main-entry |  |
| domains/automation/studio/pages/StudioPage.tsx:48 | button | not-main-entry | "button" / "添加节点" |
| domains/automation/studio/pages/StudioPage.tsx:49 | Input | not-main-entry |  |
| domains/automation/studio/pages/StudioPage.tsx:50 | button | not-main-entry | "button" |
| domains/automation/studio/pages/StudioPage.tsx:56 | button | not-main-entry | "button" |
| domains/automation/studio/pages/StudioPage.tsx:56 | button | not-main-entry | "button" |
| domains/automation/studio/pages/StudioPage.tsx:60 | aside | not-main-entry | "节点配置" / scroll container |
| domains/automation/studio/pages/StudioPage.tsx:60 | Input | not-main-entry |  |
| domains/automation/studio/pages/StudioPage.tsx:60 | Input | not-main-entry |  |
| domains/automation/studio/pages/StudioPage.tsx:60 | Input | not-main-entry |  |
| domains/automation/studio/pages/StudioPage.tsx:60 | select | not-main-entry |  |
| domains/automation/studio/pages/StudioPage.tsx:60 | Input | not-main-entry |  |
| domains/automation/studio/pages/StudioPage.tsx:60 | Input | not-main-entry |  |
| domains/automation/studio/pages/StudioPage.tsx:62 | button | not-main-entry | "button" |
| domains/dashboard/components/DashboardCards.tsx:26 | button | app-runtime | "button" |
| domains/dashboard/pages/DashboardPage.tsx:9 | div | app-runtime | "status" / "正在加载资源概况" |
| domains/dashboard/pages/DashboardPage.tsx:9 | section | app-runtime | "alert" |
| domains/dashboard/pages/DashboardPage.tsx:9 | Button | app-runtime |  |
| domains/kernels/components/DeleteKernelDialog.tsx:22 | AlertDialog | app-runtime |  |
| domains/kernels/components/DeleteKernelDialog.tsx:23 | AlertDialogContent | app-runtime |  |
| domains/kernels/components/DeleteKernelDialog.tsx:24 | AlertDialogTitle | app-runtime |  |
| domains/kernels/components/DeleteKernelDialog.tsx:25 | AlertDialogDescription | app-runtime |  |
| domains/kernels/components/DeleteKernelDialog.tsx:26 | div | app-runtime | "alert" |
| domains/kernels/components/DeleteKernelDialog.tsx:26 | Button | app-runtime | "button" |
| domains/kernels/components/DeleteKernelDialog.tsx:27 | p | app-runtime | "alert" |
| domains/kernels/components/DeleteKernelDialog.tsx:29 | AlertDialogCancel | app-runtime |  |
| domains/kernels/components/DeleteKernelDialog.tsx:29 | Button | app-runtime | "button" |
| domains/kernels/components/DeleteKernelDialog.tsx:30 | AlertDialogAction | app-runtime |  |
| domains/kernels/components/DeleteKernelDialog.tsx:30 | Button | app-runtime | "button" |
| domains/kernels/components/KernelManagerDialog.tsx:202 | Dialog | app-runtime |  |
| domains/kernels/components/KernelManagerDialog.tsx:203 | DialogContent | app-runtime | scroll container |
| domains/kernels/components/KernelManagerDialog.tsx:207 | DialogTitle | app-runtime |  |
| domains/kernels/components/KernelManagerDialog.tsx:207 | DialogDescription | app-runtime |  |
| domains/kernels/components/KernelManagerDialog.tsx:208 | Button | app-runtime | "button" / "关闭内核管理" |
| domains/kernels/components/KernelManagerDialog.tsx:211 | div | app-runtime | "alert" |
| domains/kernels/components/KernelManagerDialog.tsx:211 | Button | app-runtime | "button" |
| domains/kernels/components/KernelManagerDialog.tsx:232 | Button | app-runtime | "button" |
| domains/kernels/components/KernelManagerDialog.tsx:235 | Button | app-runtime | "button" |
| domains/kernels/components/KernelManagerDialog.tsx:237 | p | app-runtime | "alert" |
| domains/kernels/components/KernelManagerDialog.tsx:238 | p | app-runtime | "alert" |
| domains/kernels/components/KernelManagerDialog.tsx:239 | p | app-runtime | "alert" |
| domains/kernels/components/KernelManagerDialog.tsx:240 | p | app-runtime | "status" |
| domains/kernels/components/KernelOperationStatus.tsx:32 | div | app-runtime | "status" |
| domains/kernels/components/KernelOperationStatus.tsx:37 | div | app-runtime | "progressbar" / "内核安装进度" |
| domains/kernels/components/KernelOperationStatus.tsx:41 | p | app-runtime | "alert" |
| domains/kernels/components/KernelOperationStatus.tsx:42 | Button | app-runtime | "button" |
| domains/kernels/components/KernelOperationStatus.tsx:43 | Button | app-runtime | "button" |
| domains/kernels/components/KernelReleaseList.tsx:66 | Button | app-runtime | "button" |
| domains/kernels/components/KernelReleaseList.tsx:67 | Button | app-runtime | "button" |
| domains/kernels/components/KernelReleaseList.tsx:68 | Button | app-runtime | "button" |
| domains/kernels/components/KernelReleaseList.tsx:69 | Button | app-runtime | "button" |
| domains/kernels/components/LicensePanel.tsx:43 | Button | app-runtime | "button" |
| domains/kernels/components/LicensePanel.tsx:47 | Input | app-runtime | "password" |
| domains/kernels/components/LicensePanel.tsx:48 | Button | app-runtime | "submit" |
| domains/kernels/components/LicensePanel.tsx:50 | p | app-runtime | "alert" |
| domains/kernels/components/LicensePanel.tsx:51 | p | app-runtime | "alert" |
| domains/models/components/ModelDeleteDialog.tsx:11 | Modal | app-runtime |  |
| domains/models/components/ModelDeleteDialog.tsx:11 | Button | app-runtime | "button" |
| domains/models/components/ModelDeleteDialog.tsx:11 | Button | app-runtime | "button" |
| domains/models/components/ModelDeleteDialog.tsx:12 | p | app-runtime | "alert" |
| domains/models/components/ModelDirectory.tsx:16 | Button | app-runtime |  |
| domains/models/components/ModelDirectory.tsx:16 | Button | app-runtime |  |
| domains/models/components/ModelDirectory.tsx:17 | Input | app-runtime | "搜索模型" |
| domains/models/components/ModelDirectory.tsx:17 | select | app-runtime | "模型状态" |
| domains/models/components/ModelDirectory.tsx:18 | div | app-runtime | scroll container |
| domains/models/components/ModelDirectory.tsx:18 | table | app-runtime |  |
| domains/models/components/ModelDirectory.tsx:19 | Button | app-runtime | {`${model.displayName} 测试模型`} |
| domains/models/components/ModelDirectory.tsx:19 | DropdownMenu | app-runtime |  |
| domains/models/components/ModelDirectory.tsx:19 | DropdownMenuTrigger | app-runtime |  |
| domains/models/components/ModelDirectory.tsx:19 | Button | app-runtime | {`${model.displayName} 更多操作`} |
| domains/models/components/ModelDirectory.tsx:19 | DropdownMenuContent | app-runtime |  |
| domains/models/components/ModelDirectory.tsx:19 | DropdownMenuItem | app-runtime |  |
| domains/models/components/ModelDirectory.tsx:19 | DropdownMenuItem | app-runtime |  |
| domains/models/components/ModelDirectory.tsx:19 | DropdownMenuSeparator | app-runtime |  |
| domains/models/components/ModelDirectory.tsx:19 | DropdownMenuItem | app-runtime |  |
| domains/models/components/ModelEditor.tsx:59 | Modal | app-runtime |  |
| domains/models/components/ModelEditor.tsx:59 | Button | app-runtime | "button" |
| domains/models/components/ModelEditor.tsx:59 | Button | app-runtime | "button" |
| domains/models/components/ModelEditor.tsx:61 | FormField | app-runtime |  |
| domains/models/components/ModelEditor.tsx:61 | Button | app-runtime | "button" / "刷新模型目录" |
| domains/models/components/ModelEditor.tsx:62 | Button | app-runtime | "button" |
| domains/models/components/ModelForm.tsx:24 | p | app-runtime | "alert" |
| domains/models/components/ModelForm.tsx:25 | FormField | app-runtime |  |
| domains/models/components/ModelForm.tsx:25 | Input | app-runtime |  |
| domains/models/components/ModelForm.tsx:26 | FormField | app-runtime |  |
| domains/models/components/ModelForm.tsx:27 | Input | app-runtime | "模型标识" |
| domains/models/components/ModelForm.tsx:27 | Button | app-runtime | "button" / "复制模型标识" |
| domains/models/components/ModelForm.tsx:27 | span | app-runtime | "status" |
| domains/models/components/ModelForm.tsx:29 | FormField | app-runtime |  |
| domains/models/components/ModelForm.tsx:29 | Input | app-runtime | "上下文窗口" |
| domains/models/components/ModelForm.tsx:31 | button | app-runtime | "button" / {`移除标签 ${tag}`} |
| domains/models/components/ModelForm.tsx:32 | input | app-runtime | "自定义标签" |
| domains/models/components/ModelForm.tsx:34 | details | app-runtime |  |
| domains/models/components/ModelForm.tsx:34 | summary | app-runtime |  |
| domains/models/components/ModelForm.tsx:34 | FormField | app-runtime |  |
| domains/models/components/ModelForm.tsx:34 | Textarea | app-runtime |  |
| domains/models/components/ModelIdInput.tsx:11 | Input | app-runtime | "模型标识" |
| domains/models/components/ModelIdInput.tsx:12 | div | app-runtime | "listbox" / "模型目录" / scroll container |
| domains/models/components/ModelIdInput.tsx:13 | button | app-runtime | "option" |
| domains/models/components/ModelTestPanel.tsx:8 | Button | app-runtime | "button" |
| domains/models/components/ModelTestPanel.tsx:10 | div | app-runtime | "alert" |
| domains/models/components/ModelTestPanel.tsx:10 | div | app-runtime | "status" |
| domains/models/components/ModelTestPanel.tsx:10 | details | app-runtime |  |
| domains/models/components/ModelTestPanel.tsx:10 | summary | app-runtime |  |
| domains/models/components/ProviderCatalogStep.tsx:12 | Input | app-runtime | "搜索供应商目录" |
| domains/models/components/ProviderCatalogStep.tsx:15 | button | app-runtime | "button" |
| domains/models/components/ProviderCatalogStep.tsx:18 | button | app-runtime | "button" |
| domains/models/components/ProviderConnectionStep.tsx:15 | div | app-runtime | "alert" |
| domains/models/components/ProviderConnectionStep.tsx:18 | FormField | app-runtime |  |
| domains/models/components/ProviderConnectionStep.tsx:18 | Input | app-runtime |  |
| domains/models/components/ProviderConnectionStep.tsx:19 | FormField | app-runtime |  |
| domains/models/components/ProviderConnectionStep.tsx:19 | Select | app-runtime |  |
| domains/models/components/ProviderConnectionStep.tsx:21 | FormField | app-runtime |  |
| domains/models/components/ProviderConnectionStep.tsx:21 | Input | app-runtime |  |
| domains/models/components/ProviderConnectionStep.tsx:22 | FormField | app-runtime |  |
| domains/models/components/ProviderConnectionStep.tsx:22 | Input | app-runtime | "password" |
| domains/models/components/ProviderConnectionStep.tsx:23 | FormField | app-runtime |  |
| domains/models/components/ProviderConnectionStep.tsx:23 | Textarea | app-runtime |  |
| domains/models/components/ProviderConnectionStep.tsx:24 | Switch | app-runtime | "启用供应商" |
| domains/models/components/ProviderDeleteDialog.tsx:13 | Modal | app-runtime |  |
| domains/models/components/ProviderDeleteDialog.tsx:14 | Button | app-runtime |  |
| domains/models/components/ProviderDeleteDialog.tsx:15 | Button | app-runtime |  |
| domains/models/components/ProviderDeleteDialog.tsx:18 | p | app-runtime | "alert" |
| domains/models/components/ProviderDetail.tsx:23 | Button | app-runtime |  |
| domains/models/components/ProviderDetail.tsx:23 | Button | app-runtime |  |
| domains/models/components/ProviderDetail.tsx:24 | DropdownMenu | app-runtime |  |
| domains/models/components/ProviderDetail.tsx:24 | DropdownMenuTrigger | app-runtime |  |
| domains/models/components/ProviderDetail.tsx:24 | Button | app-runtime | "供应商更多操作" |
| domains/models/components/ProviderDetail.tsx:24 | DropdownMenuContent | app-runtime |  |
| domains/models/components/ProviderDetail.tsx:24 | DropdownMenuItem | app-runtime |  |
| domains/models/components/ProviderDetail.tsx:24 | DropdownMenuSeparator | app-runtime |  |
| domains/models/components/ProviderDetail.tsx:24 | DropdownMenuItem | app-runtime |  |
| domains/models/components/ProviderModelsStep.tsx:15 | Input | app-runtime | "搜索发现的模型" |
| domains/models/components/ProviderModelsStep.tsx:15 | Button | app-runtime | "button" |
| domains/models/components/ProviderModelsStep.tsx:16 | div | app-runtime | scroll container |
| domains/models/components/ProviderModelsStep.tsx:16 | Checkbox | app-runtime | {`选择 ${model.displayName}`} |
| domains/models/components/ProviderSidebar.tsx:14 | Button | app-runtime | "添加供应商" |
| domains/models/components/ProviderSidebar.tsx:15 | Input | app-runtime | "搜索供应商" |
| domains/models/components/ProviderSidebar.tsx:17 | button | app-runtime | "button" |
| domains/models/components/ProviderWizard.tsx:62 | Button | app-runtime |  |
| domains/models/components/ProviderWizard.tsx:62 | Button | app-runtime |  |
| domains/models/components/ProviderWizard.tsx:62 | Button | app-runtime |  |
| domains/models/components/ProviderWizard.tsx:62 | Button | app-runtime |  |
| domains/models/components/ProviderWizard.tsx:62 | Button | app-runtime |  |
| domains/models/components/ProviderWizard.tsx:62 | Button | app-runtime |  |
| domains/models/components/ProviderWizard.tsx:62 | Button | app-runtime |  |
| domains/models/components/ProviderWizard.tsx:62 | Button | app-runtime |  |
| domains/models/components/ProviderWizard.tsx:62 | Button | app-runtime |  |
| domains/models/components/ProviderWizard.tsx:64 | Modal | app-runtime |  |
| domains/models/components/ProviderWizard.tsx:69 | div | app-runtime | "alert" |
| domains/models/pages/ModelManagementPage.tsx:41 | Button | app-runtime | "添加模型供应商" |
| domains/models/pages/ModelManagementPage.tsx:42 | div | app-runtime | "alert" |
| domains/models/pages/ModelManagementPage.tsx:42 | Button | app-runtime |  |
| domains/models/pages/ModelManagementPage.tsx:43 | div | app-runtime | "status" |
| domains/models/pages/ModelManagementPage.tsx:43 | div | app-runtime | "alert" |
| domains/models/pages/ModelManagementPage.tsx:43 | Button | app-runtime |  |
| domains/models/pages/ModelManagementPage.tsx:43 | Button | app-runtime |  |
| domains/profiles/components/AdvancedFields.tsx:13 | details | app-runtime |  |
| domains/profiles/components/AdvancedFields.tsx:14 | summary | app-runtime |  |
| domains/profiles/components/AdvancedFields.tsx:21 | FormField | app-runtime |  |
| domains/profiles/components/AdvancedFields.tsx:22 | Textarea | app-runtime |  |
| domains/profiles/components/AdvancedFields.tsx:24 | FormField | app-runtime |  |
| domains/profiles/components/AdvancedFields.tsx:25 | Textarea | app-runtime |  |
| domains/profiles/components/BasicFields.tsx:14 | FormField | app-runtime |  |
| domains/profiles/components/BasicFields.tsx:15 | Input | app-runtime |  |
| domains/profiles/components/BasicFields.tsx:17 | FormField | app-runtime |  |
| domains/profiles/components/BasicFields.tsx:18 | Input | app-runtime |  |
| domains/profiles/components/BasicFields.tsx:21 | FormField | app-runtime |  |
| domains/profiles/components/BasicFields.tsx:22 | Input | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:55 | p | app-runtime | "status" |
| domains/profiles/components/EnvironmentFields.tsx:56 | div | app-runtime | "alert" |
| domains/profiles/components/EnvironmentFields.tsx:58 | Button | app-runtime | "button" |
| domains/profiles/components/EnvironmentFields.tsx:61 | EnvironmentOptionField | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:62 | EnvironmentOptionField | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:67 | Switch | app-runtime | "自定义尺寸" |
| domains/profiles/components/EnvironmentFields.tsx:84 | FormField | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:85 | Input | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:88 | FormField | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:89 | Input | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:91 | Select | app-runtime | "视口预设" |
| domains/profiles/components/EnvironmentFields.tsx:95 | p | app-runtime | "alert" |
| domains/profiles/components/EnvironmentFields.tsx:98 | FormField | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:99 | Select | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:101 | FormField | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:102 | Select | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:105 | FormField | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:106 | Input | app-runtime |  |
| domains/profiles/components/EnvironmentFields.tsx:106 | datalist | app-runtime |  |
| domains/profiles/components/EnvironmentOptionField.tsx:41 | FormField | app-runtime |  |
| domains/profiles/components/EnvironmentOptionField.tsx:42 | Input | app-runtime |  |
| domains/profiles/components/EnvironmentOptionField.tsx:42 | Select | app-runtime |  |
| domains/profiles/components/EnvironmentOptionField.tsx:57 | Button | app-runtime | "button" / {`选择${label}预设`} |
| domains/profiles/components/KernelProxyFields.tsx:45 | p | app-runtime | "alert" |
| domains/profiles/components/KernelProxyFields.tsx:50 | Select | app-runtime | "浏览器内核" |
| domains/profiles/components/KernelProxyFields.tsx:58 | Button | app-runtime | "button" |
| domains/profiles/components/KernelProxyFields.tsx:60 | p | app-runtime | "alert" |
| domains/profiles/components/KernelProxyFields.tsx:62 | FormField | app-runtime |  |
| domains/profiles/components/KernelProxyFields.tsx:63 | Select | app-runtime |  |
| domains/profiles/components/KernelProxyFields.tsx:66 | p | app-runtime | "alert" |
| domains/profiles/components/KernelProxyFields.tsx:68 | FormField | app-runtime |  |
| domains/profiles/components/KernelProxyFields.tsx:69 | Select | app-runtime |  |
| domains/profiles/components/KernelProxyFields.tsx:75 | FormField | app-runtime |  |
| domains/profiles/components/KernelProxyFields.tsx:76 | Select | app-runtime |  |
| domains/profiles/components/KernelProxyFields.tsx:81 | FormField | app-runtime |  |
| domains/profiles/components/KernelProxyFields.tsx:82 | Select | app-runtime |  |
| domains/profiles/components/KernelProxyFields.tsx:101 | Switch | app-runtime | {label} |
| domains/profiles/components/ProfileActionDialog.tsx:67 | Dialog | app-runtime |  |
| domains/profiles/components/ProfileActionDialog.tsx:68 | DialogContent | app-runtime |  |
| domains/profiles/components/ProfileActionDialog.tsx:69 | DialogTitle | app-runtime |  |
| domains/profiles/components/ProfileActionDialog.tsx:70 | DialogDescription | app-runtime |  |
| domains/profiles/components/ProfileActionDialog.tsx:71 | div | app-runtime | "alert" |
| domains/profiles/components/ProfileActionDialog.tsx:71 | Button | app-runtime | "button" |
| domains/profiles/components/ProfileActionDialog.tsx:73 | FormField | app-runtime |  |
| domains/profiles/components/ProfileActionDialog.tsx:74 | Input | app-runtime |  |
| domains/profiles/components/ProfileActionDialog.tsx:80 | p | app-runtime | "alert" |
| domains/profiles/components/ProfileActionDialog.tsx:83 | Button | app-runtime | "button" |
| domains/profiles/components/ProfileActionDialog.tsx:84 | Button | app-runtime | "submit" |
| domains/profiles/components/ProfileFormDialog.tsx:169 | Dialog | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:170 | DialogContent | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:172 | DialogTitle | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:173 | DialogDescription | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:175 | div | app-runtime | "alert" |
| domains/profiles/components/ProfileFormDialog.tsx:175 | Button | app-runtime | "button" |
| domains/profiles/components/ProfileFormDialog.tsx:177 | form | app-runtime | scroll container |
| domains/profiles/components/ProfileFormDialog.tsx:179 | p | app-runtime | "alert" |
| domains/profiles/components/ProfileFormDialog.tsx:180 | Tabs | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:181 | TabsList | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:182 | TabsTrigger | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:183 | TabsTrigger | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:184 | TabsTrigger | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:185 | TabsTrigger | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:187 | TabsContent | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:188 | TabsContent | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:194 | TabsContent | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:203 | TabsContent | app-runtime |  |
| domains/profiles/components/ProfileFormDialog.tsx:209 | Button | app-runtime | "button" |
| domains/profiles/components/ProfileFormDialog.tsx:210 | Button | app-runtime | "submit" |
| domains/profiles/components/ProfileList.tsx:37 | Button | app-runtime | "button" / {`编辑 ${profile.name}`} |
| domains/profiles/components/ProfileList.tsx:38 | Button | app-runtime | "button" / {`复制 ${profile.name}`} |
| domains/profiles/components/ProfileList.tsx:39 | Button | app-runtime | "button" / {`重新生成 ${profile.name} 的指纹`} |
| domains/profiles/components/ProfileList.tsx:40 | Button | app-runtime | "button" / {`删除 ${profile.name}`} |
| domains/profiles/components/UnsavedChangesDialog.tsx:18 | AlertDialog | app-runtime |  |
| domains/profiles/components/UnsavedChangesDialog.tsx:19 | AlertDialogContent | app-runtime |  |
| domains/profiles/components/UnsavedChangesDialog.tsx:20 | AlertDialogTitle | app-runtime |  |
| domains/profiles/components/UnsavedChangesDialog.tsx:21 | AlertDialogDescription | app-runtime |  |
| domains/profiles/components/UnsavedChangesDialog.tsx:23 | AlertDialogCancel | app-runtime |  |
| domains/profiles/components/UnsavedChangesDialog.tsx:23 | Button | app-runtime |  |
| domains/profiles/components/UnsavedChangesDialog.tsx:24 | AlertDialogAction | app-runtime |  |
| domains/profiles/components/UnsavedChangesDialog.tsx:24 | Button | app-runtime |  |
| domains/profiles/pages/BrowserManagementPage.tsx:77 | Button | app-runtime | "button" |
| domains/profiles/pages/BrowserManagementPage.tsx:84 | Input | app-runtime | "search" |
| domains/profiles/pages/BrowserManagementPage.tsx:86 | Select | app-runtime | "代理模式筛选" |
| domains/profiles/pages/BrowserManagementPage.tsx:94 | p | app-runtime | "status" |
| domains/profiles/pages/BrowserManagementPage.tsx:95 | div | app-runtime | "alert" |
| domains/profiles/pages/BrowserManagementPage.tsx:95 | Button | app-runtime | "button" |
| domains/profiles/pages/BrowserManagementPage.tsx:97 | div | app-runtime | "status" / "正在加载浏览器配置" |
| domains/profiles/pages/BrowserManagementPage.tsx:98 | section | app-runtime | "alert" |
| domains/profiles/pages/BrowserManagementPage.tsx:98 | Button | app-runtime | "button" |
| domains/profiles/pages/BrowserManagementPage.tsx:99 | section | app-runtime | "status" |
| domains/profiles/pages/BrowserManagementPage.tsx:99 | Button | app-runtime | "button" |
| domains/profiles/pages/BrowserManagementPage.tsx:100 | section | app-runtime | "status" |
| domains/profiles/pages/BrowserManagementPage.tsx:106 | Button | app-runtime | "button" |
| domains/profiles/pages/BrowserManagementPage.tsx:108 | Button | app-runtime | "button" |
| domains/profiles/pages/BrowserManagementPage.tsx:124 | Toaster | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:33 | Button | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:38 | div | app-runtime | scroll container |
| domains/proxies/components/LocalProxyGroups.tsx:39 | table | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | Button | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | AlertDialog | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | AlertDialogTrigger | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | Button | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | AlertDialogContent | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | AlertDialogTitle | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | AlertDialogDescription | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | AlertDialogCancel | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | Button | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | AlertDialogAction | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:44 | Button | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:111 | Dialog | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:112 | DialogContent | app-runtime | scroll container |
| domains/proxies/components/LocalProxyGroups.tsx:113 | DialogTitle | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:114 | DialogDescription | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:117 | FormField | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:117 | Input | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:118 | FormField | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:118 | Input | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:122 | Input | app-runtime | "搜索组成员" |
| domains/proxies/components/LocalProxyGroups.tsx:122 | Select | app-runtime | "筛选成员健康" |
| domains/proxies/components/LocalProxyGroups.tsx:123 | div | app-runtime | scroll container |
| domains/proxies/components/LocalProxyGroups.tsx:124 | input | app-runtime | "checkbox" |
| domains/proxies/components/LocalProxyGroups.tsx:132 | Button | app-runtime | "button" / {`上移 ${label}`} |
| domains/proxies/components/LocalProxyGroups.tsx:132 | Button | app-runtime | "button" / {`下移 ${label}`} |
| domains/proxies/components/LocalProxyGroups.tsx:132 | Button | app-runtime | "button" / {`移除 ${label}`} |
| domains/proxies/components/LocalProxyGroups.tsx:135 | div | app-runtime | "alert" |
| domains/proxies/components/LocalProxyGroups.tsx:135 | Button | app-runtime | "button" |
| domains/proxies/components/LocalProxyGroups.tsx:136 | DialogClose | app-runtime |  |
| domains/proxies/components/LocalProxyGroups.tsx:136 | Button | app-runtime | "button" |
| domains/proxies/components/LocalProxyGroups.tsx:136 | Button | app-runtime | "submit" |
| domains/proxies/components/ProxyConnection.tsx:45 | Button | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:70 | Button | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:73 | Button | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:74 | AlertDialog | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:75 | AlertDialogTrigger | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:75 | Button | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:76 | AlertDialogContent | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:77 | AlertDialogTitle | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:78 | AlertDialogDescription | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:80 | AlertDialogCancel | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:80 | Button | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:81 | AlertDialogAction | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:81 | Button | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:87 | p | app-runtime | "alert" |
| domains/proxies/components/ProxyConnection.tsx:128 | Dialog | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:129 | DialogContent | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:130 | DialogTitle | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:131 | DialogDescription | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:133 | FormField | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:134 | Input | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:139 | Input | app-runtime | {showKey ? 'text' : 'password'} |
| domains/proxies/components/ProxyConnection.tsx:140 | Button | app-runtime | "button" |
| domains/proxies/components/ProxyConnection.tsx:143 | p | app-runtime | "alert" |
| domains/proxies/components/ProxyConnection.tsx:146 | DialogClose | app-runtime |  |
| domains/proxies/components/ProxyConnection.tsx:146 | Button | app-runtime | "button" |
| domains/proxies/components/ProxyConnection.tsx:147 | Button | app-runtime | "submit" |
| domains/proxies/components/ProxyDetailDrawer.tsx:63 | Dialog | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:64 | DialogContent | app-runtime | scroll container |
| domains/proxies/components/ProxyDetailDrawer.tsx:67 | DialogTitle | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:68 | DialogDescription | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:70 | Button | app-runtime | "关闭代理详情" |
| domains/proxies/components/ProxyDetailDrawer.tsx:72 | Tabs | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:73 | TabsList | app-runtime | scroll container |
| domains/proxies/components/ProxyDetailDrawer.tsx:74 | TabsTrigger | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:75 | TabsTrigger | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:76 | TabsTrigger | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:77 | TabsTrigger | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:79 | TabsContent | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:82 | Select | app-runtime | "检测协议" |
| domains/proxies/components/ProxyDetailDrawer.tsx:86 | Button | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:89 | Input | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:90 | Switch | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:91 | Button | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:107 | p | app-runtime | "alert" |
| domains/proxies/components/ProxyDetailDrawer.tsx:114 | TabsContent | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:118 | AlertDialog | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:119 | AlertDialogTrigger | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:119 | Button | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:120 | AlertDialogContent | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:121 | AlertDialogTitle | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:122 | AlertDialogDescription | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:123 | AlertDialogCancel | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:123 | Button | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:123 | AlertDialogAction | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:123 | Button | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:126 | Button | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:134 | TabsContent | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:137 | Select | app-runtime | "凭据协议" |
| domains/proxies/components/ProxyDetailDrawer.tsx:155 | TabsContent | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:199 | Dialog | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:200 | DialogContent | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:201 | DialogTitle | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:202 | DialogDescription | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:203 | Input | app-runtime | "搜索地点" |
| domains/proxies/components/ProxyDetailDrawer.tsx:203 | Select | app-runtime | "地点运营商" |
| domains/proxies/components/ProxyDetailDrawer.tsx:204 | div | app-runtime | scroll container |
| domains/proxies/components/ProxyDetailDrawer.tsx:205 | input | app-runtime | "radio" |
| domains/proxies/components/ProxyDetailDrawer.tsx:208 | Button | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:208 | Button | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:215 | Select | app-runtime | "轮换模式" |
| domains/proxies/components/ProxyDetailDrawer.tsx:219 | Switch | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:219 | Input | app-runtime |  |
| domains/proxies/components/ProxyDetailDrawer.tsx:223 | Button | app-runtime |  |
| domains/proxies/components/ProxyFleet.tsx:61 | Input | app-runtime |  |
| domains/proxies/components/ProxyFleet.tsx:63 | Select | app-runtime | "健康状态" |
| domains/proxies/components/ProxyFleet.tsx:69 | Select | app-runtime | "运营商" |
| domains/proxies/components/ProxyFleet.tsx:73 | Select | app-runtime | "城市" |
| domains/proxies/components/ProxyFleet.tsx:84 | div | app-runtime | scroll container |
| domains/proxies/components/ProxyFleet.tsx:85 | table | app-runtime |  |
| domains/proxies/components/ProxyFleet.tsx:109 | Button | app-runtime |  |
| domains/proxies/components/ProxyFleet.tsx:110 | Button | app-runtime |  |
| domains/proxies/components/ProxyFleet.tsx:123 | Button | app-runtime |  |
| domains/proxies/components/ProxyFleet.tsx:123 | Button | app-runtime |  |
| domains/proxies/pages/ProxyManagementPage.tsx:42 | ProxyPageSkeleton | app-runtime |  |
| domains/proxies/pages/ProxyManagementPage.tsx:45 | div | app-runtime | "alert" |
| domains/proxies/pages/ProxyManagementPage.tsx:47 | Button | app-runtime |  |
| domains/proxies/pages/ProxyManagementPage.tsx:111 | Toaster | app-runtime |  |
| domains/proxies/pages/ProxyManagementPage.tsx:117 | div | app-runtime | "status" / "正在加载代理管理" |
| domains/settings/components/DiagnosticDialog.tsx:43 | Modal | app-runtime |  |
| domains/settings/components/DiagnosticDialog.tsx:43 | Button | app-runtime |  |
| domains/settings/components/DiagnosticDialog.tsx:43 | Button | app-runtime |  |
| domains/settings/components/DiagnosticDialog.tsx:45 | Checkbox | app-runtime | "添加最近日志" |
| domains/settings/components/DiagnosticDialog.tsx:46 | p | app-runtime | "status" |
| domains/settings/components/DiagnosticDialog.tsx:46 | div | app-runtime | "alert" |
| domains/settings/components/DiagnosticDialog.tsx:46 | Button | app-runtime |  |
| domains/settings/components/DiagnosticDialog.tsx:46 | div | app-runtime | "alert" |
| domains/settings/components/DiagnosticDialog.tsx:46 | pre | app-runtime | scroll container |
| domains/settings/pages/SettingsPage.tsx:42 | main | app-runtime | "status" |
| domains/settings/pages/SettingsPage.tsx:43 | p | app-runtime | "alert" |
| domains/settings/pages/SettingsPage.tsx:43 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:45 | div | app-runtime | "alert" |
| domains/settings/pages/SettingsPage.tsx:45 | div | app-runtime | "alert" |
| domains/settings/pages/SettingsPage.tsx:45 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:45 | div | app-runtime | "status" |
| domains/settings/pages/SettingsPage.tsx:46 | Tabs | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:46 | TabsList | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:46 | TabsTrigger | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:46 | TabsTrigger | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:46 | TabsTrigger | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:47 | TabsContent | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:47 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:47 | button | app-runtime | "button" |
| domains/settings/pages/SettingsPage.tsx:48 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:49 | Select | app-runtime | "界面缩放" |
| domains/settings/pages/SettingsPage.tsx:49 | Select | app-runtime | "减少动效" |
| domains/settings/pages/SettingsPage.tsx:50 | TabsContent | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:50 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:50 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:50 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:50 | code | app-runtime | scroll container |
| domains/settings/pages/SettingsPage.tsx:50 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:51 | TabsContent | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:51 | button | app-runtime | "button" |
| domains/settings/pages/SettingsPage.tsx:51 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:51 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:52 | Modal | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:52 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:52 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:52 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:52 | Button | app-runtime |  |
| domains/settings/pages/SettingsPage.tsx:52 | div | app-runtime | "alert" |
| domains/settings/pages/SettingsPage.tsx:52 | Toaster | app-runtime |  |
| shared/components/FormField.tsx:13 | p | shared-runtime | "alert" |
| shared/components/Modal.tsx:36 | Dialog | shared-runtime |  |
| shared/components/Modal.tsx:37 | DialogContent | shared-runtime |  |
| shared/components/Modal.tsx:65 | DialogTitle | shared-runtime |  |
| shared/components/Modal.tsx:66 | DialogDescription | shared-runtime |  |
| shared/components/Modal.tsx:68 | DialogClose | shared-runtime |  |
| shared/components/Modal.tsx:69 | Button | shared-runtime | "button" / {closeDisabled ? '正在处理，请稍候' : '关闭'} |
| shared/components/Modal.tsx:74 | div | shared-runtime | "region" / {`${title}内容`} / scroll container |
| shared/components/ResourceState.tsx:7 | section | not-main-entry | "status" |
| shared/components/ResourceState.tsx:8 | section | not-main-entry | "alert" |
| shared/components/ResourceState.tsx:8 | Button | not-main-entry |  |
| shared/components/ResourceState.tsx:9 | section | not-main-entry | "status" |
| shared/components/State.tsx:11 | section | shared-runtime | "status" |
| shared/components/Toaster.tsx:22 | div | shared-runtime | "status" |
| shared/components/Toaster.tsx:22 | Button | shared-runtime | "关闭通知" |
| shared/components/ui/alert-dialog.tsx:10 | AlertDialogPrimitive.Portal | shared-runtime |  |
| shared/components/ui/alert-dialog.tsx:10 | AlertDialogPrimitive.Overlay | shared-runtime |  |
| shared/components/ui/alert-dialog.tsx:10 | AlertDialogPrimitive.Content | shared-runtime |  |
| shared/components/ui/button.tsx:13 | button | shared-runtime |  |
| shared/components/ui/dialog.tsx:7 | DialogPrimitive.Root | shared-runtime |  |
| shared/components/ui/dialog.tsx:11 | DialogPrimitive.Close | shared-runtime |  |
| shared/components/ui/dialog.tsx:13 | DialogPrimitive.Title | shared-runtime |  |
| shared/components/ui/dialog.tsx:14 | DialogPrimitive.Description | shared-runtime |  |
| shared/components/ui/dialog.tsx:19 | DialogPrimitive.Portal | shared-runtime |  |
| shared/components/ui/dialog.tsx:20 | DialogPrimitive.Overlay | shared-runtime |  |
| shared/components/ui/dialog.tsx:21 | DialogPrimitive.Content | shared-runtime |  |
| shared/components/ui/dropdown-menu.tsx:7 | DropdownMenuPrimitive.Portal | shared-runtime |  |
| shared/components/ui/dropdown-menu.tsx:7 | DropdownMenuPrimitive.Content | shared-runtime |  |
| shared/components/ui/dropdown-menu.tsx:8 | DropdownMenuPrimitive.Item | shared-runtime |  |
| shared/components/ui/dropdown-menu.tsx:9 | DropdownMenuPrimitive.Separator | shared-runtime |  |
| shared/components/ui/input.tsx:5 | input | shared-runtime |  |
| shared/components/ui/select-radix.tsx:8 | SelectPrimitive.Trigger | not-main-entry |  |
| shared/components/ui/select-radix.tsx:9 | SelectPrimitive.Portal | not-main-entry |  |
| shared/components/ui/select-radix.tsx:9 | SelectPrimitive.Content | not-main-entry |  |
| shared/components/ui/select-radix.tsx:10 | SelectPrimitive.Item | not-main-entry |  |
| shared/components/ui/select.tsx:4 | select | shared-runtime |  |
| shared/components/ui/tabs.tsx:5 | TabsPrimitive.List | shared-runtime |  |
| shared/components/ui/tabs.tsx:6 | TabsPrimitive.Trigger | shared-runtime |  |
| shared/components/ui/tabs.tsx:7 | TabsPrimitive.Content | shared-runtime |  |
| shared/components/ui/textarea.tsx:5 | textarea | shared-runtime |  |
| shared/components/ui/tooltip.tsx:7 | TooltipPrimitive.Portal | not-main-entry |  |
| shared/components/ui/tooltip.tsx:7 | TooltipPrimitive.Content | not-main-entry |  |

## 实施后附录（2026-09-12，confirmed）

上方是设计时快照。当前用量与实际行号以 `verification/ui-controls-audit.json` 的 controls 数组为准，范围/复用决定见 `verification/domain-controls.md`；以此覆盖快照中的 native Select、FormField clone、ResourceState 和未迁移状态。脚本同时记录 reachable、development、unconnected，不能把代理 prototype 或声明文件计入真实页面。
