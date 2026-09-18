# WebRPA 实体与能力盘点

基线：`reference/WebRPA`，固定 commit `5ccb900e8dcf1530aae66f676d87593c416c7ebb`。本清单只读取源码，不把 reference 作为 AutoFlow 运行时依赖。

## 判定规则

- **P0**：AutoFlow Automation Studio 首期应复刻，保留 `module_type`、配置字段、输入输出和流程语义；实现归位到 `apps/backend/src/autoflow/domain|application|executors|infrastructure`。
- **P1**：能力有价值，但在 P0 黄金流程稳定后迁移。
- **后续**：可以迁移，但需要独立依赖、平台适配或产品决策。
- **排除**：按当前已确认约束不进入首期，也不应偷偷作为运行时依赖。

## 一、领域实体（不是节点）

### 工作流与运行

| 实体 | WebRPA 来源 | AutoFlow 处理 | 说明 |
|---|---|---|---|
| `Position` | `backend/app/models/workflow.py` | P0 | 画布坐标 |
| `WorkflowNode` | 同上 | P0 | `id/type/position/data`，保留节点数据契约 |
| `WorkflowEdge` | 同上 | P0 | source/target/handles |
| `Variable` / `VariableType` | 同上 | P0 | 变量解析、类型和作用域 |
| `Workflow` | 同上 | P0 | 当前工作流文档，不引入 revision/publish |
| `ExecutionStatus` / `ExecutionResult` | 同上 | P0 | 映射为 AutoFlow Run |
| `LogLevel` / `LogEntry` | 同上 | P0 | 映射为 RunEvent/日志 |
| `BaseModuleConfig` 与各模块 Config | `backend/app/models/modules.py` | P0/P1 | 迁移时按节点分组，不复制无关字段 |
| `CustomModule*` | `backend/app/models/custom_module.py` | 后续 | 需要自定义节点产品边界 |
| `ScheduledTask*` | `backend/app/models/scheduled_task.py` | 后续 | 调度属于 Manager/application 层 |
| `Chat*`、`Assistant*`、`ToolApproval*` | `backend/app/models/ai_assistant.py` | 排除 | 当前不做 AI 助手 |

### 基础执行实体

| 实体 | 来源 | AutoFlow 处理 |
|---|---|---|
| `ModuleExecutor` | `executors/base.py` | P0，改为 `NodeExecutor`，保留契约 |
| `ModuleResult` | `executors/base.py` | P0，保留 success/message/data/error/duration |
| `ExecutionContext` | `executors/base.py` | P0，去除进程级全局状态，注入 CloakBrowser runtime |
| `ExecutorRegistry` | `executors/base.py` | P0，单一注册表，重复注册 fail-fast |
| `WorkflowExecutor` | `services/workflow_executor.py` | P0，归位为 `AutomationKernel` |
| `BrowserEngine` | `services/browser_engine.py` | 替换为 `CloakBrowserRuntimeAdapter` |
| `Recorder` / `ElementPicker` | `services/recorder.py`、`services/element_picker.py` | P0/P1，归位为浏览器录制和元素拾取应用服务 |

## 二、节点实体清单（573 个唯一 `module_type`）

下面按源码能力域列出全部唯一节点类型。重复实现只列一次；WebRPA 中同一类型在多个文件重复注册的情况，AutoFlow 只保留一个规范实现。

### P0-网页自动化（30）

| moduleType | WebRPA 代表来源 | 执行器类 |
|---|---|---|
| `click_element` | `backend/app/executors/basic.py` | `ClickElementExecutor` |
| `close_page` | `backend/app/executors/basic.py` | `ClosePageExecutor` |
| `download_file` | `backend/app/executors/advanced.py` | `DownloadFileExecutor` |
| `drag_element` | `backend/app/executors/advanced.py` | `DragElementExecutor` |
| `element_exists` | `backend/app/executors/advanced_browser.py` | `ElementExistsExecutor` |
| `element_visible` | `backend/app/executors/advanced_browser.py` | `ElementVisibleExecutor` |
| `get_child_elements` | `backend/app/executors/advanced_browser.py` | `GetChildElementsExecutor` |
| `get_element_info` | `backend/app/executors/basic.py` | `GetElementInfoExecutor` |
| `get_sibling_elements` | `backend/app/executors/advanced_browser.py` | `GetSiblingElementsExecutor` |
| `go_back` | `backend/app/executors/basic.py` | `GoBackExecutor` |
| `go_forward` | `backend/app/executors/basic.py` | `GoForwardExecutor` |
| `handle_dialog` | `backend/app/executors/basic.py` | `HandleDialogExecutor` |
| `hover_element` | `backend/app/executors/basic.py` | `HoverElementExecutor` |
| `input_text` | `backend/app/executors/basic.py` | `InputTextExecutor` |
| `open_page` | `backend/app/executors/basic.py` | `OpenPageExecutor` |
| `page_load_complete` | `backend/app/executors/basic.py` | `PageLoadCompleteExecutor` |
| `refresh_page` | `backend/app/executors/basic.py` | `RefreshPageExecutor` |
| `save_image` | `backend/app/executors/advanced.py` | `SaveImageExecutor` |
| `screenshot` | `backend/app/executors/basic.py` | `ScreenshotExecutor` |
| `scroll_page` | `backend/app/executors/advanced.py` | `ScrollPageExecutor` |
| `select_dropdown` | `backend/app/executors/advanced.py` | `SelectDropdownExecutor` |
| `set_checkbox` | `backend/app/executors/advanced.py` | `SetCheckboxExecutor` |
| `switch_iframe` | `backend/app/executors/basic.py` | `SwitchIframeExecutor` |
| `switch_tab` | `backend/app/executors/switch_tab.py` | `SwitchTabExecutor` |
| `switch_to_main` | `backend/app/executors/basic.py` | `SwitchToMainExecutor` |
| `upload_file` | `backend/app/executors/advanced.py` | `UploadFileExecutor` |
| `use_opened_page` | `backend/app/executors/basic.py` | `UseOpenedPageExecutor` |
| `wait` | `backend/app/executors/basic.py` | `WaitExecutor` |
| `wait_element` | `backend/app/executors/basic.py` | `WaitElementExecutor` |
| `wait_page_load` | `backend/app/executors/basic.py` | `WaitPageLoadExecutor` |

### P0-内核与通用数据（67）

| moduleType | WebRPA 代表来源 | 执行器类 |
|---|---|---|
| `break_loop` | `backend/app/executors/control.py` | `BreakLoopExecutor` |
| `condition` | `backend/app/executors/control.py` | `ConditionExecutor` |
| `continue_loop` | `backend/app/executors/control.py` | `ContinueLoopExecutor` |
| `csv_generate` | `backend/app/executors/string_convert.py` | `CsvGenerateExecutor` |
| `csv_parse` | `backend/app/executors/string_convert.py` | `CsvParseExecutor` |
| `dict_get` | `backend/app/executors/data_structure.py` | `DictGetExecutor` |
| `dict_keys` | `backend/app/executors/data_structure.py` | `DictKeysExecutor` |
| `dict_operation` | `backend/app/executors/data_structure.py` | `DictOperationExecutor` |
| `foreach` | `backend/app/executors/control.py` | `ForeachExecutor` |
| `foreach_dict` | `backend/app/executors/control_extended.py` | `ForeachDictExecutor` |
| `increment_decrement` | `backend/app/executors/basic_variable.py` | `IncrementDecrementExecutor` |
| `infinite_loop` | `backend/app/executors/control_extended.py` | `InfiniteLoopExecutor` |
| `list_average` | `backend/app/executors/math_list_ops.py` | `ListAverageExecutor` |
| `list_cartesian_product` | `backend/app/executors/list_advanced.py` | `ListCartesianProductExecutor` |
| `list_chunk` | `backend/app/executors/list_advanced.py` | `ListChunkExecutor` |
| `list_count` | `backend/app/executors/list_advanced.py` | `ListCountExecutor` |
| `list_difference` | `backend/app/executors/list_advanced.py` | `ListDifferenceExecutor` |
| `list_export` | `backend/app/executors/data_structure.py` | `ListExportExecutor` |
| `list_filter` | `backend/app/executors/list_advanced.py` | `ListFilterExecutor` |
| `list_find` | `backend/app/executors/list_advanced.py` | `ListFindExecutor` |
| `list_flatten` | `backend/app/executors/list_advanced.py` | `ListFlattenExecutor` |
| `list_get` | `backend/app/executors/data_structure.py` | `ListGetExecutor` |
| `list_intersection` | `backend/app/executors/list_advanced.py` | `ListIntersectionExecutor` |
| `list_length` | `backend/app/executors/data_structure.py` | `ListLengthExecutor` |
| `list_map` | `backend/app/executors/list_advanced.py` | `ListMapExecutor` |
| `list_max` | `backend/app/executors/math_list_ops.py` | `ListMaxExecutor` |
| `list_merge` | `backend/app/executors/list_advanced.py` | `ListMergeExecutor` |
| `list_min` | `backend/app/executors/math_list_ops.py` | `ListMinExecutor` |
| `list_operation` | `backend/app/executors/data_structure.py` | `ListOperationExecutor` |
| `list_remove_empty` | `backend/app/executors/list_advanced.py` | `ListRemoveEmptyExecutor` |
| `list_reverse` | `backend/app/executors/list_advanced.py` | `ListReverseExecutor` |
| `list_sample` | `backend/app/executors/list_advanced.py` | `ListSampleExecutor` |
| `list_shuffle` | `backend/app/executors/list_advanced.py` | `ListShuffleExecutor` |
| `list_slice` | `backend/app/executors/math_list_ops.py` | `ListSliceExecutor` |
| `list_sort` | `backend/app/executors/math_list_ops.py` | `ListSortExecutor` |
| `list_sum` | `backend/app/executors/math_list_ops.py` | `ListSumExecutor` |
| `list_to_string_advanced` | `backend/app/executors/string_convert.py` | `ListToStringAdvancedExecutor` |
| `list_union` | `backend/app/executors/list_advanced.py` | `ListUnionExecutor` |
| `list_unique` | `backend/app/executors/math_list_ops.py` | `ListUniqueExecutor` |
| `loop` | `backend/app/executors/control.py` | `LoopExecutor` |
| `math_abs` | `backend/app/executors/math_list_ops.py` | `MathAbsExecutor` |
| `math_base_convert` | `backend/app/executors/math_list_ops.py` | `MathBaseConvertExecutor` |
| `math_clamp` | `backend/app/executors/math_advanced.py` | `MathClampExecutor` |
| `math_exp` | `backend/app/executors/math_advanced.py` | `MathExpExecutor` |
| `math_factorial` | `backend/app/executors/math_advanced.py` | `MathFactorialExecutor` |
| `math_floor` | `backend/app/executors/math_list_ops.py` | `MathFloorExecutor` |
| `math_gcd` | `backend/app/executors/math_advanced.py` | `MathGcdExecutor` |
| `math_lcm` | `backend/app/executors/math_advanced.py` | `MathLcmExecutor` |
| `math_log` | `backend/app/executors/math_advanced.py` | `MathLogExecutor` |
| `math_modulo` | `backend/app/executors/math_list_ops.py` | `MathModuloExecutor` |
| `math_percentage` | `backend/app/executors/math_advanced.py` | `MathPercentageExecutor` |
| `math_permutation` | `backend/app/executors/math_advanced.py` | `MathPermutationExecutor` |
| `math_power` | `backend/app/executors/math_list_ops.py` | `MathPowerExecutor` |
| `math_random_advanced` | `backend/app/executors/math_advanced.py` | `MathRandomAdvancedExecutor` |
| `math_round` | `backend/app/executors/math_list_ops.py` | `MathRoundExecutor` |
| `math_sqrt` | `backend/app/executors/math_list_ops.py` | `MathSqrtExecutor` |
| `math_trig` | `backend/app/executors/math_advanced.py` | `MathTrigExecutor` |
| `regex_extract` | `backend/app/executors/data_structure.py` | `RegexExtractExecutor` |
| `scheduled_task` | `backend/app/executors/control.py` | `ScheduledTaskExecutor` |
| `stop_workflow` | `backend/app/executors/control_extended.py` | `StopWorkflowExecutor` |
| `string_case` | `backend/app/executors/data_structure.py` | `StringCaseExecutor` |
| `string_concat` | `backend/app/executors/data_structure.py` | `StringConcatExecutor` |
| `string_join` | `backend/app/executors/data_structure.py` | `StringJoinExecutor` |
| `string_replace` | `backend/app/executors/data_structure.py` | `StringReplaceExecutor` |
| `string_split` | `backend/app/executors/data_structure.py` | `StringSplitExecutor` |
| `string_substring` | `backend/app/executors/data_structure.py` | `StringSubstringExecutor` |
| `string_trim` | `backend/app/executors/data_structure.py` | `StringTrimExecutor` |

### P1-基础辅助候选（15）

| moduleType | WebRPA 代表来源 | 执行器类 |
|---|---|---|
| `get_time` | `backend/app/executors/basic.py` | `GetTimeExecutor` |
| `group` | `backend/app/executors/basic.py` | `GroupExecutor` |
| `inject_javascript` | `backend/app/executors/basic.py` | `InjectJavaScriptExecutor` |
| `input_prompt` | `backend/app/executors/basic.py` | `InputPromptExecutor` |
| `js_script` | `backend/app/executors/basic.py` | `JsScriptExecutor` |
| `play_music` | `backend/app/executors/basic.py` | `PlayMusicExecutor` |
| `play_sound` | `backend/app/executors/basic.py` | `PlaySoundExecutor` |
| `play_video` | `backend/app/executors/basic.py` | `PlayVideoExecutor` |
| `print_log` | `backend/app/executors/basic.py` | `PrintLogExecutor` |
| `random_number` | `backend/app/executors/basic.py` | `RandomNumberExecutor` |
| `set_variable` | `backend/app/executors/basic.py` | `SetVariableExecutor` |
| `system_notification` | `backend/app/executors/basic.py` | `SystemNotificationExecutor` |
| `text_to_speech` | `backend/app/executors/basic.py` | `TextToSpeechExecutor` |
| `view_image` | `backend/app/executors/basic.py` | `ViewImageExecutor` |
| `wait_image` | `backend/app/executors/basic.py` | `WaitImageExecutor` |

### P1-通用集成候选（131）

| moduleType | WebRPA 代表来源 | 执行器类 |
|---|---|---|
| `api_request` | `backend/app/executors/advanced.py` | `ApiRequestExecutor` |
| `api_trigger` | `backend/app/executors/trigger.py` | `ApiTriggerExecutor` |
| `assert_checkpoint` | `backend/app/executors/advanced_assert.py` | `AssertCheckpointExecutor` |
| `base64` | `backend/app/executors/advanced.py` | `Base64Executor` |
| `click_image_deprecated` | `backend/app/executors/advanced.py` | `_DeprecatedClickImageExecutor` |
| `click_text` | `backend/app/executors/advanced.py` | `ClickTextExecutor` |
| `copy_file` | `backend/app/executors/advanced.py` | `CopyFileExecutor` |
| `create_folder` | `backend/app/executors/advanced.py` | `CreateFolderExecutor` |
| `db_close` | `backend/app/executors/database.py` | `DbCloseExecutor` |
| `db_connect` | `backend/app/executors/database.py` | `DbConnectExecutor` |
| `db_delete` | `backend/app/executors/database.py` | `DbDeleteExecutor` |
| `db_execute` | `backend/app/executors/database.py` | `DbExecuteExecutor` |
| `db_insert` | `backend/app/executors/database.py` | `DbInsertExecutor` |
| `db_query` | `backend/app/executors/database.py` | `DbQueryExecutor` |
| `db_update` | `backend/app/executors/database.py` | `DbUpdateExecutor` |
| `delete_file` | `backend/app/executors/advanced.py` | `DeleteFileExecutor` |
| `element_change_trigger` | `backend/app/executors/trigger.py` | `ElementChangeTriggerExecutor` |
| `email_trigger` | `backend/app/executors/trigger.py` | `EmailTriggerExecutor` |
| `export_log` | `backend/app/executors/advanced.py` | `ExportLogExecutor` |
| `extract_table_data` | `backend/app/executors/table_extract.py` | `ExtractTableDataExecutor` |
| `face_trigger` | `backend/app/executors/trigger.py` | `FaceTriggerExecutor` |
| `file_diff_compare` | `backend/app/executors/utility_tools.py` | `FileDiffCompareExecutor` |
| `file_exists` | `backend/app/executors/advanced.py` | `FileExistsExecutor` |
| `file_hash_compare` | `backend/app/executors/utility_tools.py` | `FileHashCompareExecutor` |
| `file_watcher_trigger` | `backend/app/executors/trigger.py` | `FileWatcherTriggerExecutor` |
| `folder_diff_compare` | `backend/app/executors/utility_tools.py` | `FolderDiffCompareExecutor` |
| `folder_hash_compare` | `backend/app/executors/utility_tools.py` | `FolderHashCompareExecutor` |
| `gesture_trigger` | `backend/app/executors/trigger.py` | `GestureTriggerExecutor` |
| `get_clipboard` | `backend/app/executors/advanced.py` | `GetClipboardExecutor` |
| `get_file_info` | `backend/app/executors/advanced.py` | `GetFileInfoExecutor` |
| `get_mouse_position` | `backend/app/executors/advanced.py` | `GetMousePositionExecutor` |
| `hex_to_cmyk` | `backend/app/executors/utility_tools.py` | `HEXToCMYKExecutor` |
| `hotkey_trigger` | `backend/app/executors/trigger.py` | `HotkeyTriggerExecutor` |
| `hover_image` | `backend/app/executors/advanced.py` | `HoverImageExecutor` |
| `hover_text` | `backend/app/executors/advanced.py` | `HoverTextExecutor` |
| `image_trigger` | `backend/app/executors/trigger.py` | `ImageTriggerExecutor` |
| `json_parse` | `backend/app/executors/advanced.py` | `JsonParseExecutor` |
| `keyboard_action` | `backend/app/executors/advanced.py` | `KeyboardActionExecutor` |
| `list_files` | `backend/app/executors/advanced.py` | `ListFilesExecutor` |
| `lock_screen` | `backend/app/executors/advanced.py` | `LockScreenExecutor` |
| `macro_recorder` | `backend/app/executors/advanced.py` | `MacroRecorderExecutor` |
| `md5_encrypt` | `backend/app/executors/utility_tools.py` | `MD5EncryptExecutor` |
| `mongodb_connect` | `backend/app/executors/database_advanced.py` | `MongoDBConnectExecutor` |
| `mongodb_delete` | `backend/app/executors/database_advanced.py` | `MongoDBDeleteExecutor` |
| `mongodb_disconnect` | `backend/app/executors/database_advanced.py` | `MongoDBDisconnectExecutor` |
| `mongodb_find` | `backend/app/executors/database_advanced.py` | `MongoDBFindExecutor` |
| `mongodb_insert` | `backend/app/executors/database_advanced.py` | `MongoDBInsertExecutor` |
| `mongodb_update` | `backend/app/executors/database_advanced.py` | `MongoDBUpdateExecutor` |
| `mouse_trigger` | `backend/app/executors/trigger.py` | `MouseTriggerExecutor` |
| `move_file` | `backend/app/executors/advanced.py` | `MoveFileExecutor` |
| `network_capture` | `backend/app/executors/advanced.py` | `NetworkCaptureExecutor` |
| `oracle_connect` | `backend/app/executors/database_advanced.py` | `OracleConnectExecutor` |
| `oracle_delete` | `backend/app/executors/database_relational.py` | `OracleDeleteExecutor` |
| `oracle_disconnect` | `backend/app/executors/database_advanced.py` | `OracleDisconnectExecutor` |
| `oracle_execute` | `backend/app/executors/database_advanced.py` | `OracleExecuteExecutor` |
| `oracle_insert` | `backend/app/executors/database_relational.py` | `OracleInsertExecutor` |
| `oracle_query` | `backend/app/executors/database_advanced.py` | `OracleQueryExecutor` |
| `oracle_update` | `backend/app/executors/database_relational.py` | `OracleUpdateExecutor` |
| `postgresql_connect` | `backend/app/executors/database_advanced.py` | `PostgreSQLConnectExecutor` |
| `postgresql_delete` | `backend/app/executors/database_relational.py` | `PostgreSQLDeleteExecutor` |
| `postgresql_disconnect` | `backend/app/executors/database_advanced.py` | `PostgreSQLDisconnectExecutor` |
| `postgresql_execute` | `backend/app/executors/database_advanced.py` | `PostgreSQLExecuteExecutor` |
| `postgresql_insert` | `backend/app/executors/database_relational.py` | `PostgreSQLInsertExecutor` |
| `postgresql_query` | `backend/app/executors/database_advanced.py` | `PostgreSQLQueryExecutor` |
| `postgresql_update` | `backend/app/executors/database_relational.py` | `PostgreSQLUpdateExecutor` |
| `printer_call` | `backend/app/executors/utility_tools.py` | `PrinterCallExecutor` |
| `probability_trigger` | `backend/app/executors/probability.py` | `ProbabilityTriggerExecutor` |
| `random_password_generator` | `backend/app/executors/utility_tools.py` | `RandomPasswordGeneratorExecutor` |
| `read_excel` | `backend/app/executors/advanced.py` | `ReadExcelExecutor` |
| `read_text_file` | `backend/app/executors/advanced.py` | `ReadTextFileExecutor` |
| `real_keyboard` | `backend/app/executors/advanced.py` | `RealKeyboardExecutor` |
| `real_mouse_click` | `backend/app/executors/advanced.py` | `RealMouseClickExecutor` |
| `real_mouse_drag` | `backend/app/executors/advanced.py` | `RealMouseDragExecutor` |
| `real_mouse_move` | `backend/app/executors/advanced.py` | `RealMouseMoveExecutor` |
| `real_mouse_scroll` | `backend/app/executors/advanced.py` | `RealMouseScrollExecutor` |
| `redis_connect` | `backend/app/executors/database_advanced.py` | `RedisConnectExecutor` |
| `redis_del` | `backend/app/executors/database_advanced.py` | `RedisDelExecutor` |
| `redis_disconnect` | `backend/app/executors/database_advanced.py` | `RedisDisconnectExecutor` |
| `redis_get` | `backend/app/executors/database_advanced.py` | `RedisGetExecutor` |
| `redis_hget` | `backend/app/executors/database_advanced.py` | `RedisHashGetExecutor` |
| `redis_hset` | `backend/app/executors/database_advanced.py` | `RedisHashSetExecutor` |
| `redis_set` | `backend/app/executors/database_advanced.py` | `RedisSetExecutor` |
| `rename_file` | `backend/app/executors/advanced.py` | `RenameFileExecutor` |
| `rename_folder` | `backend/app/executors/advanced.py` | `RenameFolderExecutor` |
| `rgb_to_cmyk` | `backend/app/executors/utility_tools.py` | `RGBToCMYKExecutor` |
| `rgb_to_hsv` | `backend/app/executors/utility_tools.py` | `RGBToHSVExecutor` |
| `run_command` | `backend/app/executors/advanced.py` | `RunCommandExecutor` |
| `screenshot_screen` | `backend/app/executors/advanced.py` | `ScreenshotScreenExecutor` |
| `send_email` | `backend/app/executors/advanced.py` | `SendEmailExecutor` |
| `set_clipboard` | `backend/app/executors/advanced.py` | `SetClipboardExecutor` |
| `sha_encrypt` | `backend/app/executors/utility_tools.py` | `SHAEncryptExecutor` |
| `share_file` | `backend/app/executors/advanced.py` | `ShareFileExecutor` |
| `share_folder` | `backend/app/executors/advanced.py` | `ShareFolderExecutor` |
| `shutdown_system` | `backend/app/executors/advanced.py` | `ShutdownSystemExecutor` |
| `sound_trigger` | `backend/app/executors/trigger.py` | `SoundTriggerExecutor` |
| `sqlite_connect` | `backend/app/executors/database_advanced.py` | `SQLiteConnectExecutor` |
| `sqlite_delete` | `backend/app/executors/database_relational2.py` | `SQLiteDeleteExecutor` |
| `sqlite_disconnect` | `backend/app/executors/database_advanced.py` | `SQLiteDisconnectExecutor` |
| `sqlite_execute` | `backend/app/executors/database_advanced.py` | `SQLiteExecuteExecutor` |
| `sqlite_insert` | `backend/app/executors/database_relational2.py` | `SQLiteInsertExecutor` |
| `sqlite_query` | `backend/app/executors/database_advanced.py` | `SQLiteQueryExecutor` |
| `sqlite_update` | `backend/app/executors/database_relational2.py` | `SQLiteUpdateExecutor` |
| `sqlserver_connect` | `backend/app/executors/database_advanced.py` | `SQLServerConnectExecutor` |
| `sqlserver_delete` | `backend/app/executors/database_relational2.py` | `SQLServerDeleteExecutor` |
| `sqlserver_disconnect` | `backend/app/executors/database_advanced.py` | `SQLServerDisconnectExecutor` |
| `sqlserver_execute` | `backend/app/executors/database_advanced.py` | `SQLServerExecuteExecutor` |
| `sqlserver_insert` | `backend/app/executors/database_relational2.py` | `SQLServerInsertExecutor` |
| `sqlserver_query` | `backend/app/executors/database_advanced.py` | `SQLServerQueryExecutor` |
| `sqlserver_update` | `backend/app/executors/database_relational2.py` | `SQLServerUpdateExecutor` |
| `stat_median` | `backend/app/executors/statistics.py` | `MedianExecutor` |
| `stat_mode` | `backend/app/executors/statistics.py` | `ModeExecutor` |
| `stat_normalize` | `backend/app/executors/statistics.py` | `NormalizeExecutor` |
| `stat_percentile` | `backend/app/executors/statistics.py` | `PercentileExecutor` |
| `stat_standardize` | `backend/app/executors/statistics.py` | `StandardizeExecutor` |
| `stat_stdev` | `backend/app/executors/statistics.py` | `StdevExecutor` |
| `stat_variance` | `backend/app/executors/statistics.py` | `VarianceExecutor` |
| `stop_share` | `backend/app/executors/advanced.py` | `StopShareExecutor` |
| `table_add_column` | `backend/app/executors/table.py` | `TableAddColumnExecutor` |
| `table_add_row` | `backend/app/executors/table.py` | `TableAddRowExecutor` |
| `table_clear` | `backend/app/executors/table.py` | `TableClearExecutor` |
| `table_delete_row` | `backend/app/executors/table.py` | `TableDeleteRowExecutor` |
| `table_export` | `backend/app/executors/table.py` | `TableExportExecutor` |
| `table_get_cell` | `backend/app/executors/table.py` | `TableGetCellExecutor` |
| `table_set_cell` | `backend/app/executors/table.py` | `TableSetCellExecutor` |
| `timestamp_converter` | `backend/app/executors/utility_tools.py` | `TimestampConverterExecutor` |
| `url_encode_decode` | `backend/app/executors/utility_tools.py` | `URLEncodeDecodeExecutor` |
| `uuid_generator` | `backend/app/executors/utility_tools.py` | `UUIDGeneratorExecutor` |
| `webhook_request` | `backend/app/executors/webhook.py` | `WebhookExecutor` |
| `webhook_trigger` | `backend/app/executors/trigger.py` | `WebhookTriggerExecutor` |
| `window_focus` | `backend/app/executors/advanced.py` | `WindowFocusExecutor` |
| `write_text_file` | `backend/app/executors/advanced.py` | `WriteTextFileExecutor` |

### 后续-Excel（59）

| moduleType | WebRPA 代表来源 | 执行器类 |
|---|---|---|
| `excel_activate_sheet` | `backend/app/executors/advanced_excel_yingdao.py` | `ExcelActivateSheetExecutor` |
| `excel_add_chart` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelAddChartExecutor` |
| `excel_add_image` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelAddImageExecutor` |
| `excel_add_sheet` | `backend/app/executors/advanced_openpyxl.py` | `ExcelAddSheetExecutor` |
| `excel_append_row` | `backend/app/executors/advanced_openpyxl.py` | `ExcelAppendRowExecutor` |
| `excel_auto_filter` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelAutoFilterExecutor` |
| `excel_clear_range` | `backend/app/executors/advanced_openpyxl.py` | `ExcelClearRangeExecutor` |
| `excel_clear_sheet` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelClearSheetExecutor` |
| `excel_clear_style` | `backend/app/executors/advanced_excel_yingdao.py` | `ExcelClearStyleExecutor` |
| `excel_conditional_format` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelConditionalFormatExecutor` |
| `excel_copy_range` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelCopyRangeExecutor` |
| `excel_copy_sheet` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelCopySheetExecutor` |
| `excel_count_rows` | `backend/app/executors/advanced_excel_yingdao.py` | `ExcelCountRowsExecutor` |
| `excel_create` | `backend/app/executors/advanced_openpyxl.py` | `ExcelCreateExecutor` |
| `excel_data_validation` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelDataValidationExecutor` |
| `excel_delete_cols` | `backend/app/executors/advanced_openpyxl.py` | `ExcelDeleteColsExecutor` |
| `excel_delete_rows` | `backend/app/executors/advanced_openpyxl.py` | `ExcelDeleteRowsExecutor` |
| `excel_delete_sheet` | `backend/app/executors/advanced_openpyxl.py` | `ExcelDeleteSheetExecutor` |
| `excel_fill_range` | `backend/app/executors/advanced_excel_yingdao.py` | `ExcelFillRangeExecutor` |
| `excel_find_empty_cell` | `backend/app/executors/advanced_excel_yingdao.py` | `ExcelFindEmptyCellExecutor` |
| `excel_find_empty_col` | `backend/app/executors/advanced_excel_yingdao.py` | `ExcelFindEmptyColExecutor` |
| `excel_find_empty_row` | `backend/app/executors/advanced_excel_yingdao.py` | `ExcelFindEmptyRowExecutor` |
| `excel_find_replace` | `backend/app/executors/advanced_openpyxl.py` | `ExcelFindReplaceExecutor` |
| `excel_freeze_panes` | `backend/app/executors/advanced_openpyxl.py` | `ExcelFreezePanesExecutor` |
| `excel_from_csv` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelFromCsvExecutor` |
| `excel_get_info` | `backend/app/executors/advanced_openpyxl.py` | `ExcelGetInfoExecutor` |
| `excel_hide` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelHideExecutor` |
| `excel_insert_cols` | `backend/app/executors/advanced_openpyxl.py` | `ExcelInsertColsExecutor` |
| `excel_insert_rows` | `backend/app/executors/advanced_openpyxl.py` | `ExcelInsertRowsExecutor` |
| `excel_list_sheets` | `backend/app/executors/advanced_openpyxl.py` | `ExcelListSheetsExecutor` |
| `excel_merge_cells` | `backend/app/executors/advanced_openpyxl.py` | `ExcelMergeCellsExecutor` |
| `excel_move_sheet` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelMoveSheetExecutor` |
| `excel_number_format` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelNumberFormatExecutor` |
| `excel_page_setup` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelPageSetupExecutor` |
| `excel_pivot_table` | `backend/app/executors/advanced_excel_yingdao.py` | `ExcelPivotTableExecutor` |
| `excel_protect_sheet` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelProtectSheetExecutor` |
| `excel_read_cell` | `backend/app/executors/advanced_openpyxl.py` | `ExcelReadCellExecutor` |
| `excel_read_dicts` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelReadDictsExecutor` |
| `excel_read_formula` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelReadFormulaExecutor` |
| `excel_read_range` | `backend/app/executors/advanced_openpyxl.py` | `ExcelReadRangeExecutor` |
| `excel_refresh_data` | `backend/app/executors/advanced_excel_yingdao.py` | `ExcelRefreshDataExecutor` |
| `excel_remove_duplicates` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelRemoveDuplicatesExecutor` |
| `excel_rename_sheet` | `backend/app/executors/advanced_openpyxl.py` | `ExcelRenameSheetExecutor` |
| `excel_run_macro` | `backend/app/executors/advanced_excel_yingdao.py` | `ExcelRunMacroExecutor` |
| `excel_save_as` | `backend/app/executors/advanced_excel_yingdao.py` | `ExcelSaveAsExecutor` |
| `excel_set_border` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelSetBorderExecutor` |
| `excel_set_comment` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelSetCommentExecutor` |
| `excel_set_formula` | `backend/app/executors/advanced_openpyxl.py` | `ExcelSetFormulaExecutor` |
| `excel_set_hyperlink` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelSetHyperlinkExecutor` |
| `excel_set_size` | `backend/app/executors/advanced_openpyxl.py` | `ExcelSetSizeExecutor` |
| `excel_set_style` | `backend/app/executors/advanced_openpyxl.py` | `ExcelSetStyleExecutor` |
| `excel_set_tab_color` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelSetTabColorExecutor` |
| `excel_set_zoom` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelSetZoomExecutor` |
| `excel_sort_range` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelSortRangeExecutor` |
| `excel_to_csv` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelToCsvExecutor` |
| `excel_to_pdf` | `backend/app/executors/advanced_excel_yingdao.py` | `ExcelToPdfExecutor` |
| `excel_write_cell` | `backend/app/executors/advanced_openpyxl.py` | `ExcelWriteCellExecutor` |
| `excel_write_dicts` | `backend/app/executors/advanced_openpyxl_pro.py` | `ExcelWriteDictsExecutor` |
| `excel_write_range` | `backend/app/executors/advanced_openpyxl.py` | `ExcelWriteRangeExecutor` |

### 后续-文档/PDF（42）

| moduleType | WebRPA 代表来源 | 执行器类 |
|---|---|---|
| `docx_to_html` | `backend/app/executors/document_convert.py` | `DocxToHTMLExecutor` |
| `docx_to_markdown` | `backend/app/executors/document_convert.py` | `DocxToMarkdownExecutor` |
| `epub_to_markdown` | `backend/app/executors/document_convert.py` | `EPUBToMarkdownExecutor` |
| `html_to_docx` | `backend/app/executors/document_convert.py` | `HTMLToDocxExecutor` |
| `html_to_markdown` | `backend/app/executors/document_convert.py` | `HTMLToMarkdownExecutor` |
| `images_to_pdf` | `backend/app/executors/pdf_convert.py` | `ImagesToPDFExecutor` |
| `latex_to_pdf` | `backend/app/executors/document_convert.py` | `LaTeXToPDFExecutor` |
| `markdown_to_docx` | `backend/app/executors/document_convert.py` | `MarkdownToDocxExecutor` |
| `markdown_to_epub` | `backend/app/executors/document_convert.py` | `MarkdownToEPUBExecutor` |
| `markdown_to_html` | `backend/app/executors/document_convert.py` | `MarkdownToHTMLExecutor` |
| `markdown_to_pdf` | `backend/app/executors/document_convert.py` | `MarkdownToPDFExecutor` |
| `org_to_html` | `backend/app/executors/document_convert.py` | `OrgModeToHTMLExecutor` |
| `pdf_add_watermark` | `backend/app/executors/pdf_ops.py` | `PDFAddWatermarkExecutor` |
| `pdf_compress` | `backend/app/executors/pdf_ops.py` | `PDFCompressExecutor` |
| `pdf_decrypt` | `backend/app/executors/pdf_ops.py` | `PDFDecryptExecutor` |
| `pdf_delete_pages` | `backend/app/executors/pdf_ops.py` | `PDFDeletePagesExecutor` |
| `pdf_encrypt` | `backend/app/executors/pdf_ops.py` | `PDFEncryptExecutor` |
| `pdf_extract_images` | `backend/app/executors/pdf_ops.py` | `PDFExtractImagesExecutor` |
| `pdf_extract_text` | `backend/app/executors/pdf_ops.py` | `PDFExtractTextExecutor` |
| `pdf_get_info` | `backend/app/executors/pdf_ops.py` | `PDFGetInfoExecutor` |
| `pdf_insert_pages` | `backend/app/executors/pdf_ops.py` | `PDFInsertPagesExecutor` |
| `pdf_merge` | `backend/app/executors/pdf_ops.py` | `PDFMergeExecutor` |
| `pdf_reorder_pages` | `backend/app/executors/pdf_ops.py` | `PDFReorderPagesExecutor` |
| `pdf_rotate` | `backend/app/executors/pdf_ops.py` | `PDFRotateExecutor` |
| `pdf_split` | `backend/app/executors/pdf_ops.py` | `PDFSplitExecutor` |
| `pdf_to_images` | `backend/app/executors/pdf_convert.py` | `PDFToImagesExecutor` |
| `pdf_to_word` | `backend/app/executors/pdf_convert.py` | `PDFToWordExecutor` |
| `rst_to_html` | `backend/app/executors/document_convert.py` | `RSTToHTMLExecutor` |
| `universal_doc_convert` | `backend/app/executors/document_convert.py` | `UniversalDocumentConvertExecutor` |
| `word_close` | `backend/app/executors/word_automation.py` | `WordCloseExecutor` |
| `word_insert_hyperlink` | `backend/app/executors/word_automation.py` | `WordInsertHyperlinkExecutor` |
| `word_insert_image` | `backend/app/executors/word_automation.py` | `WordInsertImageExecutor` |
| `word_insert_table` | `backend/app/executors/word_automation.py` | `WordInsertTableExecutor` |
| `word_move_cursor` | `backend/app/executors/word_automation.py` | `WordMoveCursorExecutor` |
| `word_open` | `backend/app/executors/word_automation.py` | `WordOpenExecutor` |
| `word_read_table` | `backend/app/executors/word_automation.py` | `WordReadTableExecutor` |
| `word_read_text` | `backend/app/executors/word_automation.py` | `WordReadTextExecutor` |
| `word_replace_text` | `backend/app/executors/word_automation.py` | `WordReplaceTextExecutor` |
| `word_save` | `backend/app/executors/word_automation.py` | `WordSaveExecutor` |
| `word_set_cursor` | `backend/app/executors/word_automation.py` | `WordSetCursorExecutor` |
| `word_to_pdf` | `backend/app/executors/word_automation.py` | `WordToPdfExecutor` |
| `word_write_text` | `backend/app/executors/word_automation.py` | `WordWriteTextExecutor` |

### 后续-企业/运维扩展（53）

| moduleType | WebRPA 代表来源 | 执行器类 |
|---|---|---|
| `allure_add_attachment` | `backend/app/executors/allure.py` | `AllureAddAttachmentExecutor` |
| `allure_add_step` | `backend/app/executors/allure.py` | `AllureAddStepExecutor` |
| `allure_generate_report` | `backend/app/executors/allure.py` | `AllureGenerateReportExecutor` |
| `allure_init` | `backend/app/executors/allure.py` | `AllureInitExecutor` |
| `allure_start_test` | `backend/app/executors/allure.py` | `AllureStartTestExecutor` |
| `allure_stop_test` | `backend/app/executors/allure.py` | `AllureStopTestExecutor` |
| `custom_module` | `backend/app/executors/custom_module.py` | `CustomModuleExecutor` |
| `network_monitor_start` | `backend/app/executors/network_monitor.py` | `NetworkMonitorStartExecutor` |
| `network_monitor_stop` | `backend/app/executors/network_monitor.py` | `NetworkMonitorStopExecutor` |
| `network_monitor_wait` | `backend/app/executors/network_monitor.py` | `NetworkMonitorWaitExecutor` |
| `notify_bark` | `backend/app/executors/notify_apprise.py` | `NotifyBarkExecutor` |
| `notify_dingtalk` | `backend/app/executors/notify_apprise.py` | `NotifyDingTalkExecutor` |
| `notify_discord` | `backend/app/executors/notify_apprise.py` | `NotifyDiscordExecutor` |
| `notify_feishu` | `backend/app/executors/notify_apprise.py` | `NotifyFeishuExecutor` |
| `notify_gotify` | `backend/app/executors/notify_apprise.py` | `NotifyGotifyExecutor` |
| `notify_matrix` | `backend/app/executors/notify_apprise.py` | `NotifyMatrixExecutor` |
| `notify_msteams` | `backend/app/executors/notify_apprise.py` | `NotifyMSTeamsExecutor` |
| `notify_ntfy` | `backend/app/executors/notify_apprise.py` | `NotifyNtfyExecutor` |
| `notify_pushbullet` | `backend/app/executors/notify_apprise.py` | `NotifyPushBulletExecutor` |
| `notify_pushover` | `backend/app/executors/notify_apprise.py` | `NotifyPushoverExecutor` |
| `notify_pushplus` | `backend/app/executors/notify_apprise.py` | `NotifyPushPlusExecutor` |
| `notify_rocketchat` | `backend/app/executors/notify_apprise.py` | `NotifyRocketChatExecutor` |
| `notify_serverchan` | `backend/app/executors/notify_apprise.py` | `NotifyServerChanExecutor` |
| `notify_slack` | `backend/app/executors/notify_apprise.py` | `NotifySlackExecutor` |
| `notify_telegram` | `backend/app/executors/notify_apprise.py` | `NotifyTelegramExecutor` |
| `notify_webhook` | `backend/app/executors/notify_apprise.py` | `NotifyWebhookExecutor` |
| `notify_wecom` | `backend/app/executors/notify_apprise.py` | `NotifyWeComExecutor` |
| `run_workflow_file` | `backend/app/executors/workflow_chain.py` | `RunWorkflowFileExecutor` |
| `sap_click_button` | `backend/app/executors/sap_automation.py` | `SapClickButtonExecutor` |
| `sap_close_warning` | `backend/app/executors/sap_automation.py` | `SapCloseWarningExecutor` |
| `sap_export_gridview_excel` | `backend/app/executors/sap_automation.py` | `SapExportGridViewExecutor` |
| `sap_get_field_value` | `backend/app/executors/sap_automation.py` | `SapGetFieldValueExecutor` |
| `sap_get_status_message` | `backend/app/executors/sap_automation.py` | `SapGetStatusMessageExecutor` |
| `sap_get_title` | `backend/app/executors/sap_automation.py` | `SapGetTitleExecutor` |
| `sap_login` | `backend/app/executors/sap_automation.py` | `SapLoginExecutor` |
| `sap_logout` | `backend/app/executors/sap_automation.py` | `SapLogoutExecutor` |
| `sap_maximize_window` | `backend/app/executors/sap_automation.py` | `SapMaximizeWindowExecutor` |
| `sap_read_gridview` | `backend/app/executors/sap_automation.py` | `SapReadGridViewExecutor` |
| `sap_run_tcode` | `backend/app/executors/sap_automation.py` | `SapRunTcodeExecutor` |
| `sap_select_combobox` | `backend/app/executors/sap_automation.py` | `SapSelectComboBoxExecutor` |
| `sap_select_tab` | `backend/app/executors/sap_automation.py` | `SapSelectTabExecutor` |
| `sap_send_vkey` | `backend/app/executors/sap_automation.py` | `SapSendVKeyExecutor` |
| `sap_set_checkbox` | `backend/app/executors/sap_automation.py` | `SapSetCheckboxExecutor` |
| `sap_set_field_value` | `backend/app/executors/sap_automation.py` | `SapSetFieldValueExecutor` |
| `sap_set_focus` | `backend/app/executors/sap_automation.py` | `SapSetFocusExecutor` |
| `ssh_connect` | `backend/app/executors/ssh.py` | `SSHConnectExecutor` |
| `ssh_disconnect` | `backend/app/executors/ssh.py` | `SSHDisconnectExecutor` |
| `ssh_download_file` | `backend/app/executors/ssh.py` | `SSHDownloadFileExecutor` |
| `ssh_execute_command` | `backend/app/executors/ssh.py` | `SSHExecuteCommandExecutor` |
| `ssh_upload_file` | `backend/app/executors/ssh.py` | `SSHUploadFileExecutor` |
| `start_screen_share` | `backend/app/executors/screen_share.py` | `StartScreenShareExecutor` |
| `stop_screen_share` | `backend/app/executors/screen_share.py` | `StopScreenShareExecutor` |
| `subflow` | `backend/app/executors/subflow.py` | `SubflowExecutor` |

### 排除-替代浏览器运行时（9）

| moduleType | WebRPA 代表来源 | 执行器类 |
|---|---|---|
| `dp_click` | `backend/app/executors/drissionpage.py` | `DpClickExecutor` |
| `dp_close` | `backend/app/executors/drissionpage.py` | `DpCloseExecutor` |
| `dp_get_html` | `backend/app/executors/drissionpage.py` | `DpGetHtmlExecutor` |
| `dp_get_text` | `backend/app/executors/drissionpage.py` | `DpGetTextExecutor` |
| `dp_input` | `backend/app/executors/drissionpage.py` | `DpInputExecutor` |
| `dp_open_page` | `backend/app/executors/drissionpage.py` | `DpOpenPageExecutor` |
| `dp_run_js` | `backend/app/executors/drissionpage.py` | `DpRunJsExecutor` |
| `dp_scroll` | `backend/app/executors/drissionpage.py` | `DpScrollExecutor` |
| `dp_wait_element` | `backend/app/executors/drissionpage.py` | `DpWaitElementExecutor` |

### 排除-桌面自动化（40）

| moduleType | WebRPA 代表来源 | 执行器类 |
|---|---|---|
| `desktop_app_close` | `backend/app/executors/desktop_automation.py` | `DesktopAppCloseExecutor` |
| `desktop_app_connect` | `backend/app/executors/desktop_automation.py` | `DesktopAppConnectExecutor` |
| `desktop_app_get_info` | `backend/app/executors/desktop_automation.py` | `DesktopAppGetInfoExecutor` |
| `desktop_app_start` | `backend/app/executors/desktop_automation.py` | `DesktopAppStartExecutor` |
| `desktop_app_wait_ready` | `backend/app/executors/desktop_automation.py` | `DesktopAppWaitReadyExecutor` |
| `desktop_assert_control` | `backend/app/executors/desktop_advanced.py` | `DesktopAssertControlExecutor` |
| `desktop_checkbox` | `backend/app/executors/desktop_automation.py` | `DesktopCheckboxExecutor` |
| `desktop_click_control` | `backend/app/executors/desktop_automation.py` | `DesktopClickControlExecutor` |
| `desktop_control_info` | `backend/app/executors/desktop_automation.py` | `DesktopControlInfoExecutor` |
| `desktop_control_tree` | `backend/app/executors/desktop_automation.py` | `DesktopControlTreeExecutor` |
| `desktop_dialog_handle` | `backend/app/executors/desktop_automation.py` | `DesktopDialogHandleExecutor` |
| `desktop_drag_control` | `backend/app/executors/desktop_automation.py` | `DesktopDragControlExecutor` |
| `desktop_extract_table` | `backend/app/executors/desktop_advanced.py` | `DesktopExtractTableExecutor` |
| `desktop_find_control` | `backend/app/executors/desktop_automation.py` | `DesktopFindControlExecutor` |
| `desktop_find_control_smart` | `backend/app/executors/desktop_advanced.py` | `DesktopFindControlSmartExecutor` |
| `desktop_get_app_state` | `backend/app/executors/desktop_advanced.py` | `DesktopGetAppStateExecutor` |
| `desktop_get_control_info` | `backend/app/executors/desktop_automation.py` | `DesktopGetControlInfoExecutor` |
| `desktop_get_control_tree` | `backend/app/executors/desktop_automation.py` | `DesktopGetControlTreeExecutor` |
| `desktop_get_focused_control` | `backend/app/executors/desktop_advanced.py` | `DesktopGetFocusedControlExecutor` |
| `desktop_get_property` | `backend/app/executors/desktop_automation.py` | `DesktopGetPropertyExecutor` |
| `desktop_get_text` | `backend/app/executors/desktop_automation.py` | `DesktopGetTextExecutor` |
| `desktop_hotkey` | `backend/app/executors/desktop_automation.py` | `DesktopHotkeyExecutor` |
| `desktop_input_control` | `backend/app/executors/desktop_automation.py` | `DesktopInputControlExecutor` |
| `desktop_list_operate` | `backend/app/executors/desktop_automation.py` | `DesktopListOperateExecutor` |
| `desktop_menu_click` | `backend/app/executors/desktop_automation.py` | `DesktopMenuClickExecutor` |
| `desktop_query_with_xpath` | `backend/app/executors/desktop_advanced.py` | `DesktopQueryWithXpathExecutor` |
| `desktop_radio` | `backend/app/executors/desktop_automation.py` | `DesktopRadioExecutor` |
| `desktop_scroll_control` | `backend/app/executors/desktop_automation.py` | `DesktopScrollControlExecutor` |
| `desktop_select_combo` | `backend/app/executors/desktop_automation.py` | `DesktopSelectComboExecutor` |
| `desktop_select_text` | `backend/app/executors/desktop_advanced.py` | `DesktopSelectTextExecutor` |
| `desktop_send_keys` | `backend/app/executors/desktop_automation.py` | `DesktopSendKeysExecutor` |
| `desktop_set_value` | `backend/app/executors/desktop_automation.py` | `DesktopSetValueExecutor` |
| `desktop_wait_control` | `backend/app/executors/desktop_automation.py` | `DesktopWaitControlExecutor` |
| `desktop_window_activate` | `backend/app/executors/desktop_automation.py` | `DesktopWindowActivateExecutor` |
| `desktop_window_capture` | `backend/app/executors/desktop_automation.py` | `DesktopWindowCaptureExecutor` |
| `desktop_window_list` | `backend/app/executors/desktop_automation.py` | `DesktopWindowListExecutor` |
| `desktop_window_move` | `backend/app/executors/desktop_automation.py` | `DesktopWindowMoveExecutor` |
| `desktop_window_resize` | `backend/app/executors/desktop_automation.py` | `DesktopWindowResizeExecutor` |
| `desktop_window_state` | `backend/app/executors/desktop_automation.py` | `DesktopWindowStateExecutor` |
| `desktop_window_topmost` | `backend/app/executors/desktop_automation.py` | `DesktopWindowTopmostExecutor` |

### 排除-Android（22）

| moduleType | WebRPA 代表来源 | 执行器类 |
|---|---|---|
| `phone_click_image` | `backend/app/executors/phone_vision.py` | `PhoneClickImageExecutor` |
| `phone_click_text` | `backend/app/executors/phone_vision.py` | `PhoneClickTextExecutor` |
| `phone_get_clipboard` | `backend/app/executors/phone_clipboard.py` | `PhoneGetClipboardExecutor` |
| `phone_image_exists` | `backend/app/executors/phone_vision.py` | `PhoneImageExistsExecutor` |
| `phone_input_text` | `backend/app/executors/phone_input.py` | `PhoneInputTextExecutor` |
| `phone_install_app` | `backend/app/executors/phone_app.py` | `PhoneInstallAppExecutor` |
| `phone_long_press` | `backend/app/executors/phone_advanced.py` | `PhoneLongPressExecutor` |
| `phone_press_key` | `backend/app/executors/phone_input.py` | `PhonePressKeyExecutor` |
| `phone_pull_file` | `backend/app/executors/phone_file.py` | `PhonePullFileExecutor` |
| `phone_push_file` | `backend/app/executors/phone_file.py` | `PhonePushFileExecutor` |
| `phone_screenshot` | `backend/app/executors/phone_screen.py` | `PhoneScreenshotExecutor` |
| `phone_set_brightness` | `backend/app/executors/phone_settings.py` | `PhoneSetBrightnessExecutor` |
| `phone_set_clipboard` | `backend/app/executors/phone_clipboard.py` | `PhoneSetClipboardExecutor` |
| `phone_set_volume` | `backend/app/executors/phone_settings.py` | `PhoneSetVolumeExecutor` |
| `phone_start_app` | `backend/app/executors/phone_app.py` | `PhoneStartAppExecutor` |
| `phone_start_mirror` | `backend/app/executors/phone_screen.py` | `PhoneStartMirrorExecutor` |
| `phone_stop_app` | `backend/app/executors/phone_advanced.py` | `PhoneStopAppExecutor` |
| `phone_stop_mirror` | `backend/app/executors/phone_screen.py` | `PhoneStopMirrorExecutor` |
| `phone_swipe` | `backend/app/executors/phone_touch.py` | `PhoneSwipeExecutor` |
| `phone_tap` | `backend/app/executors/phone_touch.py` | `PhoneTapExecutor` |
| `phone_uninstall_app` | `backend/app/executors/phone_advanced.py` | `PhoneUninstallAppExecutor` |
| `phone_wait_image` | `backend/app/executors/phone_vision.py` | `PhoneWaitImageExecutor` |

### 排除-OCR/验证码/视觉（5）

| moduleType | WebRPA 代表来源 | 执行器类 |
|---|---|---|
| `ai_vision_act` | `backend/app/executors/advanced_vision_act.py` | `AIVisionActExecutor` |
| `face_recognition` | `backend/app/executors/media.py` | `FaceRecognitionExecutor` |
| `image_ocr` | `backend/app/executors/media.py` | `ImageOCRExecutor` |
| `ocr_captcha` | `backend/app/executors/captcha.py` | `OCRCaptchaExecutor` |
| `slider_captcha` | `backend/app/executors/captcha.py` | `SliderCaptchaExecutor` |

### 排除-媒体/图像（51）

| moduleType | WebRPA 代表来源 | 执行器类 |
|---|---|---|
| `add_subtitle` | `backend/app/executors/media.py` | `AddSubtitleExecutor` |
| `add_watermark` | `backend/app/executors/media.py` | `AddWatermarkExecutor` |
| `adjust_volume` | `backend/app/executors/media.py` | `AdjustVolumeExecutor` |
| `audio_to_text` | `backend/app/executors/media.py` | `AudioToTextExecutor` |
| `bwm_embed_image` | `backend/app/executors/blind_watermark.py` | `BwmEmbedImageExecutor` |
| `bwm_embed_text` | `backend/app/executors/blind_watermark.py` | `BwmEmbedTextExecutor` |
| `bwm_extract_image` | `backend/app/executors/blind_watermark.py` | `BwmExtractImageExecutor` |
| `bwm_extract_text` | `backend/app/executors/blind_watermark.py` | `BwmExtractTextExecutor` |
| `camera_capture` | `backend/app/executors/media_record.py` | `CameraCaptureExecutor` |
| `camera_record` | `backend/app/executors/media_record.py` | `CameraRecordExecutor` |
| `click_image` | `backend/app/executors/advanced_image.py` | `ClickImageExecutor` |
| `compress_image` | `backend/app/executors/media.py` | `CompressImageExecutor` |
| `compress_video` | `backend/app/executors/media.py` | `CompressVideoExecutor` |
| `download_m3u8` | `backend/app/executors/media_m3u8.py` | `DownloadM3U8Executor` |
| `drag_image` | `backend/app/executors/advanced_image.py` | `DragImageExecutor` |
| `extract_audio` | `backend/app/executors/media.py` | `ExtractAudioExecutor` |
| `extract_frame` | `backend/app/executors/media.py` | `ExtractFrameExecutor` |
| `format_convert` | `backend/app/executors/media.py` | `FormatConvertExecutor` |
| `image_add_text` | `backend/app/executors/advanced_pillow.py` | `ImageAddTextExecutor` |
| `image_blur` | `backend/app/executors/advanced_pillow.py` | `ImageBlurExecutor` |
| `image_brightness` | `backend/app/executors/advanced_pillow.py` | `ImageBrightnessExecutor` |
| `image_color_balance` | `backend/app/executors/advanced_pillow.py` | `ImageColorBalanceExecutor` |
| `image_contrast` | `backend/app/executors/advanced_pillow.py` | `ImageContrastExecutor` |
| `image_convert_format` | `backend/app/executors/advanced_pillow.py` | `ImageConvertFormatExecutor` |
| `image_crop` | `backend/app/executors/advanced_pillow.py` | `ImageCropExecutor` |
| `image_exists` | `backend/app/executors/advanced_image.py` | `ImageExistsExecutor` |
| `image_filter` | `backend/app/executors/advanced_pillow.py` | `ImageFilterExecutor` |
| `image_flip` | `backend/app/executors/advanced_pillow.py` | `ImageFlipExecutor` |
| `image_get_info` | `backend/app/executors/advanced_pillow.py` | `ImageGetInfoExecutor` |
| `image_grayscale` | `backend/app/executors/media.py` | `ImageGrayscaleExecutor` |
| `image_merge` | `backend/app/executors/advanced_pillow.py` | `ImageMergeExecutor` |
| `image_remove_bg` | `backend/app/executors/advanced_pillow.py` | `ImageRemoveBackgroundExecutor` |
| `image_resize` | `backend/app/executors/advanced_pillow.py` | `ImageResizeExecutor` |
| `image_rotate` | `backend/app/executors/advanced_pillow.py` | `ImageRotateExecutor` |
| `image_round_corners` | `backend/app/executors/media.py` | `ImageRoundCornersExecutor` |
| `image_sharpen` | `backend/app/executors/advanced_pillow.py` | `ImageSharpenExecutor` |
| `image_thumbnail` | `backend/app/executors/advanced_pillow.py` | `ImageThumbnailExecutor` |
| `merge_media` | `backend/app/executors/media.py` | `MergeMediaExecutor` |
| `qr_decode` | `backend/app/executors/media.py` | `QRDecodeExecutor` |
| `qr_generate` | `backend/app/executors/media.py` | `QRGenerateExecutor` |
| `resize_video` | `backend/app/executors/media.py` | `ResizeVideoExecutor` |
| `rotate_video` | `backend/app/executors/media.py` | `RotateVideoExecutor` |
| `screen_record` | `backend/app/executors/media.py` | `ScreenRecordExecutor` |
| `trim_video` | `backend/app/executors/media.py` | `TrimVideoExecutor` |
| `video_speed` | `backend/app/executors/media.py` | `VideoSpeedExecutor` |
| `ytdlp_download` | `backend/app/executors/media_ytdlp.py` | `YtDlpDownloadExecutor` |
| `ytdlp_download_audio` | `backend/app/executors/media_ytdlp.py` | `YtDlpDownloadAudioExecutor` |
| `ytdlp_download_playlist` | `backend/app/executors/media_ytdlp.py` | `YtDlpDownloadPlaylistExecutor` |
| `ytdlp_download_subtitle` | `backend/app/executors/media_ytdlp.py` | `YtDlpDownloadSubtitleExecutor` |
| `ytdlp_get_info` | `backend/app/executors/media_ytdlp.py` | `YtDlpGetInfoExecutor` |
| `ytdlp_list_formats` | `backend/app/executors/media_ytdlp.py` | `YtDlpListFormatsExecutor` |

### 排除-AI/脚本执行（18）

| moduleType | WebRPA 代表来源 | 执行器类 |
|---|---|---|
| `ai_chat` | `backend/app/executors/ai.py` | `AIChatExecutor` |
| `ai_classify` | `backend/app/executors/ai_tasks.py` | `AIClassifyExecutor` |
| `ai_dedup_semantic` | `backend/app/executors/ai_tasks.py` | `AIDedupSemanticExecutor` |
| `ai_element_selector` | `backend/app/executors/ai_scraper.py` | `AIElementSelectorExecutor` |
| `ai_extract` | `backend/app/executors/ai_tasks.py` | `AIExtractExecutor` |
| `ai_generate_image` | `backend/app/executors/ai_media.py` | `AIGenerateImageExecutor` |
| `ai_generate_video` | `backend/app/executors/ai_media.py` | `AIGenerateVideoExecutor` |
| `ai_normalize` | `backend/app/executors/ai_tasks.py` | `AINormalizeExecutor` |
| `ai_route` | `backend/app/executors/ai_tasks.py` | `AIRouteExecutor` |
| `ai_sentiment` | `backend/app/executors/ai_tasks.py` | `AISentimentExecutor` |
| `ai_smart_scraper` | `backend/app/executors/ai_scraper.py` | `AISmartScraperExecutor` |
| `ai_summarize` | `backend/app/executors/ai_tasks.py` | `AISummarizeExecutor` |
| `ai_translate` | `backend/app/executors/ai_tasks.py` | `AITranslateExecutor` |
| `ai_vision` | `backend/app/executors/ai.py` | `AIVisionExecutor` |
| `firecrawl_crawl` | `backend/app/executors/ai_firecrawl.py` | `FirecrawlCrawlExecutor` |
| `firecrawl_map` | `backend/app/executors/ai_firecrawl.py` | `FirecrawlMapExecutor` |
| `firecrawl_scrape` | `backend/app/executors/ai_firecrawl.py` | `FirecrawlScrapeExecutor` |
| `python_script` | `backend/app/executors/python_script.py` | `PythonScriptExecutor` |

### 排除-平台专用（16）

| moduleType | WebRPA 代表来源 | 执行器类 |
|---|---|---|
| `feishu_bitable_read` | `backend/app/executors/feishu.py` | `FeishuBitableReadExecutor` |
| `feishu_bitable_write` | `backend/app/executors/feishu.py` | `FeishuBitableWriteExecutor` |
| `feishu_sheet_read` | `backend/app/executors/feishu.py` | `FeishuSheetReadExecutor` |
| `feishu_sheet_write` | `backend/app/executors/feishu.py` | `FeishuSheetWriteExecutor` |
| `qq_get_friends` | `backend/app/executors/qq.py` | `QQGetFriendListExecutor` |
| `qq_get_group_members` | `backend/app/executors/qq.py` | `QQGetGroupMembersExecutor` |
| `qq_get_groups` | `backend/app/executors/qq.py` | `QQGetGroupListExecutor` |
| `qq_get_login_info` | `backend/app/executors/qq.py` | `QQGetLoginInfoExecutor` |
| `qq_send_file` | `backend/app/executors/qq.py` | `QQSendFileExecutor` |
| `qq_send_image` | `backend/app/executors/qq.py` | `QQSendImageExecutor` |
| `qq_send_message` | `backend/app/executors/qq.py` | `QQSendMessageExecutor` |
| `qq_wait_message` | `backend/app/executors/qq.py` | `QQWaitMessageExecutor` |
| `wechat_send_file` | `backend/app/executors/wechat.py` | `WeChatSendFileExecutor` |
| `wechat_send_message` | `backend/app/executors/wechat.py` | `WeChatSendMessageExecutor` |
| `wps_bitable_read` | `backend/app/executors/wps.py` | `WpsBitableReadExecutor` |
| `wps_bitable_write` | `backend/app/executors/wps.py` | `WpsBitableWriteExecutor` |

### 待审（15）

| moduleType | WebRPA 代表来源 | 执行器类 |
|---|---|---|
| `audio_format_convert` | `backend/app/executors/format_factory.py` | `AudioFormatConvertExecutor` |
| `batch_format_convert` | `backend/app/executors/format_factory.py` | `BatchFormatConvertExecutor` |
| `dict_deep_copy` | `backend/app/executors/dict_advanced.py` | `DictDeepCopyExecutor` |
| `dict_filter` | `backend/app/executors/dict_advanced.py` | `DictFilterExecutor` |
| `dict_flatten` | `backend/app/executors/dict_advanced.py` | `DictFlattenExecutor` |
| `dict_get_path` | `backend/app/executors/dict_advanced.py` | `DictGetPathExecutor` |
| `dict_invert` | `backend/app/executors/dict_advanced.py` | `DictInvertExecutor` |
| `dict_map_values` | `backend/app/executors/dict_advanced.py` | `DictMapValuesExecutor` |
| `dict_merge` | `backend/app/executors/dict_advanced.py` | `DictMergeExecutor` |
| `dict_sort` | `backend/app/executors/dict_advanced.py` | `DictSortExecutor` |
| `image_format_convert` | `backend/app/executors/format_factory.py` | `ImageFormatConvertExecutor` |
| `note` | `backend/app/executors/note.py` | `NoteExecutor` |
| `video_format_convert` | `backend/app/executors/format_factory.py` | `VideoFormatConvertExecutor` |
| `video_to_audio` | `backend/app/executors/format_factory.py` | `VideoToAudioExecutor` |
| `video_to_gif` | `backend/app/executors/format_factory.py` | `VideoToGIFExecutor` |

## 三、非节点实体与产品能力

| 能力域 | WebRPA 实体/入口 | 建议 |
|---|---|---|
| 浏览器运行时 | `browser_engine.py`、`browser_manager.py`、`browser_process.py` | P0，全部替换为 CloakBrowser 适配层 |
| 录制与拾取 | `recorder.py`、`element_picker.py`、对应 API | P0/P1，保留选择器、提示信息和回写语义 |
| 工作流 API | `api/workflows.py`、`api/local_workflows.py` | P0，面向当前工作流与运行 |
| 运行调试 | `workflow_executor.py`、debug/log API | P0，归位 Run/RunEvent |
| 版本/发布/包 | `api/workflow_versions.py`、`published_workflows.py`、`workflow_package.py`、`workflow_bundle.py` | 排除，当前不需要版本管理和发布系统 |
| Manager/企业后台 | `dashboard.py`、`enterprise_*`、`orchestration.py`、`rbac.py`、`retention.py` | 后续，不能进入 Automation Kernel |
| 外部平台 | QQ、微信、飞书、WPS、SAP | 排除或后续独立插件，不进入首期核心 |
| 桌面/移动 | desktop、phone、ADB、系统鼠标键盘 | 排除，违反当前跨平台网页优先边界 |
| AI/OCR/媒体/文档 | ai、captcha、media、pdf、word | 排除或后续能力包 |

## 四、与当前 AutoFlow 目录架构的对齐结论

1. `reference/WebRPA` 只能作为源码基线和行为快照来源；新代码不得 import `reference/WebRPA`。
2. 工作流实体进入 `domain/automation`；执行编排进入 `application/automation`；节点执行器进入 `executors`；CloakBrowser、文件和数据库等外部实现进入 `infrastructure`；HTTP 入口进入 `adapters/http`。
3. Manager 的项目、调度、分析、资源和权限实体不得下沉到执行器；Studio 只消费自动化领域契约。
4. P0 节点先完成黄金流程：`open_page → click_element → input_text → wait → get_element_info`，再按本清单扩展。
5. 任何节点迁移都要补齐 `source_path/source_commit/target_path/action/changed_behavior/verification`，并保持一次提交只改变一类问题。
