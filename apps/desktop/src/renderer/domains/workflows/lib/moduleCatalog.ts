// WebRPA category data and approved AutoFlow scope; shared by UI and service adapters.
import type { ModuleType } from '../types/index'

const sourceModuleCategories = [
  // ===== 浏览器自动化 =====
  {
    name: '网页导航',
    color: 'bg-blue-500',
    modules: ['open_page', 'use_opened_page', 'close_page', 'refresh_page', 'go_back', 'go_forward', 'switch_tab', 'switch_iframe', 'switch_to_main', 'wait_page_load', 'page_load_complete'] as ModuleType[],
  },
  {
    name: '网页元素交互',
    color: 'bg-indigo-500',
    modules: ['click_element', 'hover_element', 'input_text', 'select_dropdown', 'set_checkbox', 'drag_element', 'scroll_page', 'handle_dialog', 'upload_file', 'inject_javascript'] as ModuleType[],
  },
  {
    name: '网页元素查询',
    color: 'bg-indigo-600',
    modules: ['get_element_info', 'get_child_elements', 'get_sibling_elements', 'element_exists', 'element_visible', 'wait_element', 'extract_table_data'] as ModuleType[],
  },
  {
    name: '网页数据采集',
    color: 'bg-emerald-500',
    modules: ['screenshot', 'save_image', 'download_file', 'network_capture', 'network_monitor_start', 'network_monitor_wait', 'network_monitor_stop'] as ModuleType[],
  },
  {
    name: 'DP 反检测自动化',
    color: 'bg-teal-600',
    modules: ['dp_open_page', 'dp_click', 'dp_input', 'dp_get_text', 'dp_get_html', 'dp_run_js', 'dp_wait_element', 'dp_scroll', 'dp_close'] as ModuleType[],
  },
  // ===== 桌面自动化 =====
  {
    name: '鼠标操作',
    color: 'bg-violet-500',
    modules: ['real_mouse_click', 'real_mouse_move', 'real_mouse_drag', 'real_mouse_scroll', 'get_mouse_position'] as ModuleType[],
  },
  {
    name: '键盘操作',
    color: 'bg-purple-500',
    modules: ['real_keyboard', 'keyboard_action'] as ModuleType[],
  },
  {
    name: '图像识别与点击',
    color: 'bg-rose-500',
    modules: ['click_image', 'click_text', 'hover_image', 'hover_text', 'drag_image', 'image_exists', 'wait_image'] as ModuleType[],
  },
  {
    name: '屏幕与录制',
    color: 'bg-pink-500',
    modules: ['screenshot_screen', 'screen_record', 'window_focus', 'camera_capture', 'camera_record', 'macro_recorder'] as ModuleType[],
  },
  {
    name: '桌面应用控制',
    color: 'bg-slate-600',
    modules: [
      'desktop_app_start', 'desktop_app_connect', 'desktop_app_close', 'desktop_app_get_info', 'desktop_app_wait_ready',
      'desktop_window_activate', 'desktop_window_state', 'desktop_window_move', 'desktop_window_resize', 'desktop_window_list', 'desktop_window_capture',
      'desktop_find_control', 'desktop_find_control_smart', 'desktop_control_info', 'desktop_control_tree', 'desktop_wait_control',
      'desktop_click_control', 'desktop_input_control', 'desktop_get_text', 'desktop_set_value',
      'desktop_select_combo', 'desktop_checkbox', 'desktop_radio', 'desktop_drag_control', 'desktop_menu_click',
      'desktop_list_operate', 'desktop_send_keys', 'desktop_get_property', 'desktop_dialog_handle',
      'desktop_hotkey', 'desktop_extract_table', 'desktop_get_app_state', 'desktop_query_with_xpath',
      'desktop_select_text', 'desktop_get_focused_control', 'desktop_assert_control',
      'desktop_window_topmost', 'desktop_scroll_control', 'desktop_get_control_info', 'desktop_get_control_tree',
    ] as ModuleType[],
  },
  {
    name: '系统操作',
    color: 'bg-gray-600',
    modules: ['shutdown_system', 'lock_screen', 'run_command', 'set_clipboard', 'get_clipboard'] as ModuleType[],
  },
  // ===== 手机自动化 =====
  {
    name: '手机自动化',
    color: 'bg-cyan-600',
    modules: ['phone_tap', 'phone_swipe', 'phone_long_press', 'phone_input_text', 'phone_press_key', 'phone_screenshot', 'phone_start_mirror', 'phone_stop_mirror', 'phone_install_app', 'phone_start_app', 'phone_stop_app', 'phone_uninstall_app', 'phone_push_file', 'phone_pull_file', 'phone_click_image', 'phone_click_text', 'phone_wait_image', 'phone_image_exists', 'phone_set_volume', 'phone_set_brightness', 'phone_set_clipboard', 'phone_get_clipboard'] as ModuleType[],
  },
  // ===== 流程控制 =====
  {
    name: '流程控制',
    color: 'bg-orange-500',
    modules: ['condition', 'loop', 'infinite_loop', 'foreach', 'foreach_dict', 'break_loop', 'continue_loop', 'assert_checkpoint', 'stop_workflow', 'wait', 'scheduled_task', 'subflow', 'run_workflow_file', 'input_prompt'] as ModuleType[],
  },
  {
    name: '触发器',
    color: 'bg-yellow-500',
    modules: ['webhook_trigger', 'hotkey_trigger', 'file_watcher_trigger', 'email_trigger', 'api_trigger', 'mouse_trigger', 'image_trigger', 'sound_trigger', 'face_trigger', 'gesture_trigger', 'element_change_trigger', 'probability_trigger'] as ModuleType[],
  },
  // ===== 数据处理 =====
  {
    name: '变量与运算',
    color: 'bg-teal-500',
    modules: ['set_variable', 'increment_decrement', 'json_parse', 'base64', 'random_number', 'get_time'] as ModuleType[],
  },
  {
    name: '文本处理',
    color: 'bg-lime-600',
    modules: ['string_concat', 'string_replace', 'string_split', 'string_join', 'string_trim', 'string_case', 'string_substring', 'regex_extract'] as ModuleType[],
  },
  {
    name: '列表操作',
    color: 'bg-green-600',
    modules: ['list_operation', 'list_get', 'list_length', 'list_export', 'list_sum', 'list_average', 'list_max', 'list_min', 'list_sort', 'list_unique', 'list_slice', 'list_reverse', 'list_find', 'list_count', 'list_filter', 'list_map', 'list_merge', 'list_flatten', 'list_chunk', 'list_remove_empty', 'list_intersection', 'list_union', 'list_difference', 'list_cartesian_product', 'list_shuffle', 'list_sample'] as ModuleType[],
  },
  {
    name: '字典操作',
    color: 'bg-teal-600',
    modules: ['dict_operation', 'dict_get', 'dict_keys', 'dict_merge', 'dict_filter', 'dict_map_values', 'dict_invert', 'dict_sort', 'dict_deep_copy', 'dict_get_path', 'dict_flatten'] as ModuleType[],
  },
  {
    name: '数学与统计',
    color: 'bg-cyan-700',
    modules: ['math_round', 'math_base_convert', 'math_floor', 'math_modulo', 'math_abs', 'math_sqrt', 'math_power', 'math_log', 'math_trig', 'math_exp', 'math_gcd', 'math_lcm', 'math_factorial', 'math_permutation', 'math_percentage', 'math_clamp', 'math_random_advanced', 'stat_median', 'stat_mode', 'stat_variance', 'stat_stdev', 'stat_percentile', 'stat_normalize', 'stat_standardize'] as ModuleType[],
  },
  {
    name: '表格与CSV',
    color: 'bg-sky-500',
    modules: ['table_add_row', 'table_add_column', 'table_set_cell', 'table_get_cell', 'table_delete_row', 'table_clear', 'table_export', 'read_excel', 'csv_parse', 'csv_generate', 'list_to_string_advanced'] as ModuleType[],
  },
  {
    name: 'Excel自动化',
    color: 'bg-emerald-600',
    modules: [
      'excel_create', 'excel_add_sheet', 'excel_delete_sheet', 'excel_rename_sheet', 'excel_list_sheets',
      'excel_copy_sheet', 'excel_move_sheet', 'excel_set_tab_color', 'excel_clear_sheet', 'excel_get_info',
      'excel_write_cell', 'excel_read_cell', 'excel_write_range', 'excel_read_range', 'excel_append_row',
      'excel_write_dicts', 'excel_read_dicts', 'excel_copy_range', 'excel_clear_range', 'excel_find_replace',
      'excel_insert_rows', 'excel_delete_rows', 'excel_insert_cols', 'excel_delete_cols', 'excel_hide',
      'excel_set_size', 'excel_set_formula', 'excel_read_formula', 'excel_merge_cells', 'excel_freeze_panes',
      'excel_set_style', 'excel_set_border', 'excel_number_format', 'excel_set_hyperlink', 'excel_set_comment',
      'excel_add_image', 'excel_add_chart', 'excel_data_validation', 'excel_conditional_format',
      'excel_auto_filter', 'excel_sort_range', 'excel_remove_duplicates', 'excel_to_csv', 'excel_from_csv',
      'excel_protect_sheet', 'excel_page_setup', 'excel_set_zoom',
      'excel_count_rows', 'excel_find_empty_row', 'excel_find_empty_col', 'excel_find_empty_cell',
      'excel_fill_range', 'excel_clear_style', 'excel_activate_sheet', 'excel_save_as',
      'excel_pivot_table', 'excel_to_pdf', 'excel_run_macro', 'excel_refresh_data',
    ] as ModuleType[],
  },
  // ===== 数据库 =====
  {
    name: '数据库',
    color: 'bg-sky-600',
    modules: [
      'db_connect', 'db_query', 'db_execute', 'db_insert', 'db_update', 'db_delete', 'db_close',
      'oracle_connect', 'oracle_query', 'oracle_execute', 'oracle_insert', 'oracle_update', 'oracle_delete', 'oracle_disconnect',
      'postgresql_connect', 'postgresql_query', 'postgresql_execute', 'postgresql_insert', 'postgresql_update', 'postgresql_delete', 'postgresql_disconnect',
      'mongodb_connect', 'mongodb_find', 'mongodb_insert', 'mongodb_update', 'mongodb_delete', 'mongodb_disconnect',
      'sqlserver_connect', 'sqlserver_query', 'sqlserver_execute', 'sqlserver_insert', 'sqlserver_update', 'sqlserver_delete', 'sqlserver_disconnect',
      'sqlite_connect', 'sqlite_query', 'sqlite_execute', 'sqlite_insert', 'sqlite_update', 'sqlite_delete', 'sqlite_disconnect',
      'redis_connect', 'redis_get', 'redis_set', 'redis_del', 'redis_hget', 'redis_hset', 'redis_disconnect',
    ] as ModuleType[],
  },
  // ===== 文件与文档 =====
  {
    name: '文件管理',
    color: 'bg-amber-600',
    modules: ['list_files', 'copy_file', 'move_file', 'delete_file', 'rename_file', 'create_folder', 'rename_folder', 'file_exists', 'get_file_info', 'read_text_file', 'write_text_file'] as ModuleType[],
  },
  {
    name: 'Word自动化',
    color: 'bg-blue-700',
    modules: [
      'word_open', 'word_read_text', 'word_write_text',
      'word_set_cursor', 'word_move_cursor', 'word_replace_text',
      'word_read_table', 'word_insert_table',
      'word_insert_image', 'word_insert_hyperlink',
      'word_to_pdf', 'word_save', 'word_close',
    ] as ModuleType[],
  },
  {
    name: 'PDF处理',
    color: 'bg-red-600',
    modules: ['pdf_to_images', 'images_to_pdf', 'pdf_merge', 'pdf_split', 'pdf_extract_text', 'pdf_extract_images', 'pdf_encrypt', 'pdf_decrypt', 'pdf_add_watermark', 'pdf_rotate', 'pdf_delete_pages', 'pdf_get_info', 'pdf_compress', 'pdf_insert_pages', 'pdf_reorder_pages', 'pdf_to_word'] as ModuleType[],
  },
  {
    name: '文档转换',
    color: 'bg-orange-600',
    modules: ['markdown_to_html', 'html_to_markdown', 'markdown_to_pdf', 'markdown_to_docx', 'docx_to_markdown', 'html_to_docx', 'docx_to_html', 'markdown_to_epub', 'epub_to_markdown', 'latex_to_pdf', 'rst_to_html', 'org_to_html', 'universal_doc_convert'] as ModuleType[],
  },
  {
    name: '文件对比',
    color: 'bg-teal-800',
    modules: ['file_hash_compare', 'file_diff_compare', 'folder_hash_compare', 'folder_diff_compare'] as ModuleType[],
  },
  // ===== 媒体处理 =====
  {
    name: '图像编辑',
    color: 'bg-pink-600',
    modules: ['compress_image', 'image_resize', 'image_crop', 'image_rotate', 'image_flip', 'image_blur', 'image_sharpen', 'image_brightness', 'image_contrast', 'image_color_balance', 'image_add_text', 'image_merge', 'image_thumbnail', 'image_filter', 'image_grayscale', 'image_round_corners', 'image_remove_bg', 'add_watermark', 'image_get_info', 'image_convert_format', 'qr_generate', 'qr_decode'] as ModuleType[],
  },
  {
    name: '盲水印',
    color: 'bg-purple-700',
    modules: ['bwm_embed_text', 'bwm_extract_text', 'bwm_embed_image', 'bwm_extract_image'] as ModuleType[],
  },
  {
    name: '视频处理',
    color: 'bg-purple-600',
    modules: ['format_convert', 'compress_video', 'trim_video', 'merge_media', 'rotate_video', 'video_speed', 'extract_frame', 'add_subtitle', 'resize_video', 'download_m3u8', 'ytdlp_download', 'ytdlp_download_audio', 'ytdlp_get_info', 'ytdlp_list_formats', 'ytdlp_download_subtitle', 'ytdlp_download_playlist'] as ModuleType[],
  },
  {
    name: '音频处理',
    color: 'bg-violet-600',
    modules: ['extract_audio', 'adjust_volume', 'audio_to_text'] as ModuleType[],
  },
  {
    name: '媒体格式转换',
    color: 'bg-rose-600',
    modules: ['image_format_convert', 'video_format_convert', 'audio_format_convert', 'video_to_audio', 'video_to_gif', 'batch_format_convert'] as ModuleType[],
  },
  // ===== AI 能力 =====
  {
    name: 'AI对话与视觉',
    color: 'bg-violet-700',
    modules: ['ai_chat', 'ai_vision', 'ai_vision_act'] as ModuleType[],
  },
  {
    name: 'AI数据处理',
    color: 'bg-indigo-700',
    modules: ['ai_extract', 'ai_classify', 'ai_summarize', 'ai_translate', 'ai_sentiment', 'ai_normalize', 'ai_dedup_semantic', 'ai_route'] as ModuleType[],
  },
  {
    name: 'AI生成',
    color: 'bg-purple-700',
    modules: ['ai_generate_image', 'ai_generate_video'] as ModuleType[],
  },
  {
    name: 'AI爬虫',
    color: 'bg-fuchsia-700',
    modules: ['ai_smart_scraper', 'ai_element_selector', 'firecrawl_scrape', 'firecrawl_map', 'firecrawl_crawl'] as ModuleType[],
  },
  {
    name: 'AI识别',
    color: 'bg-rose-700',
    modules: ['ocr_captcha', 'slider_captcha', 'face_recognition', 'image_ocr'] as ModuleType[],
  },
  // ===== 网络与通信 =====
  {
    name: '网络请求',
    color: 'bg-sky-700',
    modules: ['api_request', 'webhook_request', 'send_email'] as ModuleType[],
  },
  {
    name: '消息推送',
    color: 'bg-amber-600',
    modules: ['notify_discord', 'notify_telegram', 'notify_dingtalk', 'notify_wecom', 'notify_feishu', 'notify_bark', 'notify_slack', 'notify_msteams', 'notify_pushover', 'notify_pushbullet', 'notify_gotify', 'notify_serverchan', 'notify_pushplus', 'notify_webhook', 'notify_ntfy', 'notify_matrix', 'notify_rocketchat'] as ModuleType[],
  },
  {
    name: 'QQ机器人',
    color: 'bg-blue-500',
    modules: ['qq_send_message', 'qq_send_image', 'qq_send_file', 'qq_wait_message', 'qq_get_friends', 'qq_get_groups', 'qq_get_group_members', 'qq_get_login_info'] as ModuleType[],
  },
  {
    name: '微信机器人',
    color: 'bg-green-500',
    modules: ['wechat_send_message', 'wechat_send_file'] as ModuleType[],
  },
  {
    name: '飞书自动化',
    color: 'bg-blue-600',
    modules: ['feishu_bitable_write', 'feishu_bitable_read', 'feishu_sheet_write', 'feishu_sheet_read'] as ModuleType[],
  },
  {
    name: 'WPS多维表格',
    color: 'bg-red-600',
    modules: ['wps_bitable_write', 'wps_bitable_read'] as ModuleType[],
  },
  {
    name: 'SSH远程',
    color: 'bg-slate-700',
    modules: ['ssh_connect', 'ssh_execute_command', 'ssh_upload_file', 'ssh_download_file', 'ssh_disconnect'] as ModuleType[],
  },
  {
    name: '局域网共享',
    color: 'bg-cyan-500',
    modules: ['share_folder', 'share_file', 'stop_share', 'start_screen_share', 'stop_screen_share'] as ModuleType[],
  },
  {
    name: 'SAP自动化',
    color: 'bg-blue-800',
    modules: ['sap_login', 'sap_logout', 'sap_run_tcode', 'sap_set_field_value', 'sap_get_field_value', 'sap_click_button', 'sap_send_vkey', 'sap_get_status_message', 'sap_get_title', 'sap_close_warning', 'sap_set_checkbox', 'sap_select_combobox', 'sap_select_tab', 'sap_read_gridview', 'sap_export_gridview_excel', 'sap_set_focus', 'sap_maximize_window'] as ModuleType[],
  },
  // ===== 实用工具 =====
  {
    name: '加密与编码',
    color: 'bg-indigo-800',
    modules: ['md5_encrypt', 'sha_encrypt', 'url_encode_decode', 'random_password_generator', 'uuid_generator'] as ModuleType[],
  },
  {
    name: '颜色与时间转换',
    color: 'bg-pink-800',
    modules: ['rgb_to_hsv', 'rgb_to_cmyk', 'hex_to_cmyk', 'timestamp_converter'] as ModuleType[],
  },
  {
    name: '通知与日志',
    color: 'bg-amber-700',
    modules: ['print_log', 'export_log', 'play_sound', 'system_notification', 'text_to_speech'] as ModuleType[],
  },
  {
    name: '媒体播放',
    color: 'bg-rose-700',
    modules: ['play_music', 'play_video', 'view_image'] as ModuleType[],
  },
  {
    name: '脚本执行',
    color: 'bg-slate-700',
    modules: ['js_script', 'python_script', 'printer_call'] as ModuleType[],
  },
  // ===== 测试报告 =====
  {
    name: '测试报告',
    color: 'bg-emerald-600',
    modules: ['allure_init', 'allure_start_test', 'allure_add_step', 'allure_add_attachment', 'allure_stop_test', 'allure_generate_report'] as ModuleType[],
  },
  // ===== 画布工具 =====
  {
    name: '画布工具',
    color: 'bg-stone-500',
    modules: ['group', 'note'] as ModuleType[],
  },
]
// AutoFlow currently exposes Web automation; retain source definitions for imported documents.
const excludedCategories = new Set([
  '鼠标操作', '键盘操作', '图像识别与点击', '屏幕与录制', '桌面应用控制', '手机自动化', 'SAP自动化',
  'Excel自动化', '文件管理', 'Word自动化', 'PDF处理', '文档转换', '文件对比',
  '图像编辑', '盲水印', '视频处理', '音频处理', '媒体格式转换', '媒体播放',
  'QQ机器人', '微信机器人', '飞书自动化', 'WPS多维表格',
])
export const excludedModuleTypes = new Set<ModuleType>([
  ...sourceModuleCategories.filter(c => excludedCategories.has(c.name)).flatMap(c => c.modules),
  'read_excel', 'notify_feishu',
])
export const moduleCategories = sourceModuleCategories
  .filter(c => !excludedCategories.has(c.name))
  .map(c => ({ ...c, modules: c.modules.filter(type => !excludedModuleTypes.has(type)) }))

/** Check imported custom-module contents as well as top-level nodes, without modifying documents. */
export function findExcludedModuleType(nodes: readonly unknown[], resolveCustomNodes: (id: string) => readonly unknown[] | undefined = () => undefined): string | null {
  const pending = [...nodes]
  const visited = new Set<string>()
  while (pending.length) {
    const value = pending.pop()
    if (!value || typeof value !== 'object') continue
    const node = value as { type?: unknown; data?: { moduleType?: unknown; customModuleId?: unknown } }
    const type = node.data?.moduleType ?? node.type
    if (typeof type === 'string' && excludedModuleTypes.has(type as ModuleType)) return type
    const id = node.data?.customModuleId
    if (type === 'custom_module' && typeof id === 'string' && !visited.has(id)) {
      visited.add(id)
      const children = resolveCustomNodes(id)
      if (children) pending.push(...children)
    }
  }
  return null
}
