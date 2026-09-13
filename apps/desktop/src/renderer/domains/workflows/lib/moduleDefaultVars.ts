// Source: WebRPA@5ccb900e, lib/moduleDefaultVars.ts; see SOURCE.md for license and adaptation boundaries.
/**
 * 模块默认变量名集中表
 *
 * 用于变量名输入框（VariableNameInput）和变量补全（VariableInput）
 * 当用户没填某个 result/saveTo 类字段时，按这里的默认名提供（也会出现在变量补全列表中）。
 *
 * 数据格式：[moduleType][fieldName] = 默认变量名
 *
 * 新增模块时只需在这一处添加，不要再到处分散硬编码。
 */
export const MODULE_DEFAULT_VARS: Record<string, Record<string, string>> = {
  // ==================== 媒体处理 ====================
  format_convert: { resultVariable: 'converted_path' },
  compress_image: { resultVariable: 'compressed_image' },
  compress_video: { resultVariable: 'compressed_video' },
  extract_audio: { resultVariable: 'extracted_audio' },
  trim_video: { resultVariable: 'trimmed_video' },
  merge_media: { resultVariable: 'merged_file' },
  add_watermark: { resultVariable: 'watermarked_file' },
  face_recognition: { resultVariable: 'face_match_result' },
  image_ocr: { resultVariable: 'ocr_text' },
  rotate_video: { resultVariable: 'rotated_video' },
  video_speed: { resultVariable: 'speed_video' },
  extract_frame: { resultVariable: 'frame_image' },
  add_subtitle: { resultVariable: 'subtitled_video' },
  adjust_volume: { resultVariable: 'adjusted_audio' },
  resize_video: { resultVariable: 'resized_video' },
  camera_capture: { saveToVariable: 'camera_photo' },
  camera_record: { saveToVariable: 'camera_video' },

  // ==================== 触发器 ====================
  element_change_trigger: {
    saveNewElementSelector: 'new_element_selector',
    saveChangeInfo: 'change_info',
  },
  webhook_trigger: { saveToVariable: 'webhook_data' },
  file_watcher_trigger: { saveToVariable: 'file_event' },
  email_trigger: { saveToVariable: 'email_data' },
  api_trigger: { saveToVariable: 'api_request' },
  mouse_trigger: { saveToVariable: 'mouse_event' },
  image_trigger: { saveToVariable: 'image_event' },
  sound_trigger: { saveToVariable: 'sound_event' },
  face_trigger: { saveToVariable: 'face_event' },
  gesture_trigger: { saveToVariable: 'gesture_data' },

  // ==================== 数据/网络/AI ====================
  api_request: { resultVariable: 'api_response' },
  read_excel: { resultVariable: 'excel_data' },
  // Excel 自动化（openpyxl）读取类模块
  extract_table_data: { variableName: 'table_data' },
  run_command: { resultVariable: 'cmd_output' },
  js_script: { resultVariable: 'js_result' },
  ai_chat: { resultVariable: 'ai_response' },
  ai_extract: { variableName: 'extracted_data' },
  ai_classify: { variableName: 'category' },
  ai_summarize: { variableName: 'summary' },
  ai_translate: { variableName: 'translation' },
  ai_sentiment: { variableName: 'sentiment' },
  ai_normalize: { variableName: 'normalized' },
  ai_dedup_semantic: { variableName: 'deduped_list' },
  ai_route: { variableName: 'route' },
  ai_vision: { resultVariable: 'vision_result' },
  ocr_captcha: { resultVariable: 'captcha_text' },
  list_operation: { resultVariable: 'list_result' },
  dict_operation: { resultVariable: 'dict_result' },
  string_replace: { resultVariable: 'replace_result' },
  regex_extract: { resultVariable: 'regex_result' },
  json_parse: { resultVariable: 'parsed_json' },
  base64: { resultVariable: 'base64_result' },
  db_query: { resultVariable: 'query_result' },
  list_get: { resultVariable: 'list_item' },
  list_length: { resultVariable: 'list_len' },
  dict_get: { resultVariable: 'dict_value' },
  dict_keys: { resultVariable: 'dict_keys' },
  list_files: { resultVariable: 'file_list' },
  get_file_info: { resultVariable: 'file_info' },
  read_text_file: { resultVariable: 'file_content' },
  network_capture: { resultVariable: 'captured_data' },
  firecrawl_scrape: { variableName: 'scrape_result' },
  firecrawl_map: { variableName: 'map_result' },
  firecrawl_crawl: { variableName: 'crawl_result' },

  // ==================== 手机自动化 ====================
  phone_get_clipboard: { variableName: 'phone_clipboard' },
  phone_click_image: { resultVariable: 'phone_click_result' },
  phone_wait_image: { resultVariable: 'phone_wait_result' },
  phone_image_exists: { resultVariable: 'phone_image_exists_result' },

  // ==================== 二维码 / 图像处理 ====================
  qr_generate: { resultVariable: 'qr_image' },
  qr_decode: { resultVariable: 'qr_content' },
  image_format_convert: { resultVariable: 'converted_image' },
  image_resize: { resultVariable: 'resized_image' },
  image_crop: { resultVariable: 'cropped_image' },
  image_rotate: { resultVariable: 'rotated_image' },
  image_flip: { resultVariable: 'flipped_image' },
  image_blur: { resultVariable: 'blurred_image' },
  image_sharpen: { resultVariable: 'sharpened_image' },
  image_brightness: { resultVariable: 'brightness_image' },
  image_contrast: { resultVariable: 'contrast_image' },
  image_color_balance: { resultVariable: 'balanced_image' },
  image_convert_format: { resultVariable: 'converted_image' },
  image_add_text: { resultVariable: 'text_image' },
  image_merge: { resultVariable: 'merged_image' },
  image_thumbnail: { resultVariable: 'thumbnail_image' },
  image_filter: { resultVariable: 'filtered_image' },
  image_get_info: { resultVariable: 'image_info' },
  image_remove_bg: { resultVariable: 'nobg_image' },
  image_grayscale: { resultVariable: 'grayscale_image' },
  image_round_corners: { resultVariable: 'rounded_image' },

  // ==================== 盲水印（隐式数字水印） ====================
  bwm_embed_text: { resultVariable: 'wm_bit_len' },
  bwm_extract_text: { resultVariable: 'extracted_text' },
  bwm_embed_image: { resultVariable: 'wm_image_shape' },
  bwm_extract_image: { resultVariable: 'extracted_wm_path' },

  // ==================== 实用工具 ====================
  file_hash_compare: { resultVariable: 'hash_compare_result' },
  file_diff_compare: { resultVariable: 'diff_result' },
  folder_hash_compare: { resultVariable: 'folder_hash_result' },
  folder_diff_compare: { resultVariable: 'folder_diff_result' },
  random_password_generator: { resultVariable: 'random_password' },
  url_encode_decode: { resultVariable: 'url_result' },
  md5_encrypt: { resultVariable: 'md5_hash' },
  sha_encrypt: { resultVariable: 'sha_hash' },
  timestamp_converter: { resultVariable: 'converted_time' },
  rgb_to_hsv: { resultVariable: 'hsv_color' },
  rgb_to_cmyk: { resultVariable: 'cmyk_color' },
  hex_to_cmyk: { resultVariable: 'cmyk_color' },
  uuid_generator: { resultVariable: 'uuid' },

  // ==================== PDF ====================
  pdf_extract_text: { resultVariable: 'pdf_text' },
  pdf_extract_images: { resultVariable: 'extracted_images' },
  pdf_get_info: { resultVariable: 'pdf_info' },
  pdf_to_images: { resultVariable: 'pdf_images' },
  pdf_to_word: { resultVariable: 'word_file' },

  // ==================== 控制流 / 循环 ====================
  foreach: { itemVariable: 'item', indexVariable: 'index' },
  foreach_dict: { keyVariable: 'key', valueVariable: 'value', indexVariable: 'index' },
  loop: { indexVariable: 'index' },
  infinite_loop: { indexVariable: 'loop_index' },

  // ==================== 数学/统计 ====================

  // ==================== 字典 ====================

  // ==================== 字符串 ====================
  string_split: { resultVariable: 'split_result' },
  string_join: { resultVariable: 'join_result' },
  string_concat: { resultVariable: 'concat_result' },
  string_trim: { resultVariable: 'trim_result' },
  string_case: { resultVariable: 'case_result' },
  string_substring: { resultVariable: 'substring_result' },

  // ==================== 桌面应用 ====================
  desktop_get_text: { controlVariable: 'desktop_control', saveToVariable: 'control_text' },
  desktop_get_control_info: { controlVariable: 'desktop_control', saveToVariable: 'control_info' },
  desktop_get_control_tree: { appVariable: 'desktop_app', saveToVariable: 'control_tree' },
  desktop_app_get_info: { appVariable: 'desktop_app', saveToVariable: 'app_info' },
  desktop_window_list: { saveToVariable: 'window_list' },
  desktop_get_property: { controlVariable: 'desktop_control', saveToVariable: 'property_value' },
  desktop_window_capture: { appVariable: 'desktop_app', saveToVariable: 'screenshot_path' },

  // 桌面影刀级新模块（智能查找/批量抓取/UI快照/XPath 等）
  desktop_find_control_smart: { appVariable: 'desktop_app', saveToVariable: 'desktop_control' },
  desktop_extract_table: { appVariable: 'desktop_app', variableName: 'extracted_data' },
  desktop_get_app_state: { appVariable: 'desktop_app', variableName: 'app_state' },
  desktop_query_with_xpath: { appVariable: 'desktop_app', saveToVariable: 'desktop_control' },
  desktop_select_text: { controlVariable: 'desktop_control', variableName: 'selected_text' },
  desktop_get_focused_control: { saveToVariable: 'focused_control' },

  // ==================== AI 媒体 ====================
  ai_generate_image: { variableName: 'ai_image_urls' },
  ai_generate_video: { variableName: 'ai_video_url' },
  audio_to_text: { resultVariable: 'transcribed_text' },

  // ==================== Allure 测试 ====================

  // ==================== 数据库扩展 ====================
  oracle_query: { variableName: 'oracle_result' },
  postgresql_query: { variableName: 'postgresql_result' },
  mongodb_find: { variableName: 'mongodb_result' },
  sqlserver_query: { variableName: 'sqlserver_result' },
  sqlite_query: { variableName: 'sqlite_result' },
  redis_get: { variableName: 'redis_value' },
  redis_hget: { variableName: 'redis_hash_value' },

  // ==================== SSH ====================
  ssh_execute_command: {
    errorVariable: 'ssh_error', outputVariable: 'ssh_output',
    exitCodeVariable: 'ssh_exit_code',
  },

  // ==================== SAP ====================
  // 这些模块除了输出变量，还通过 sessionVariable 读取 sap_login 建立的会话句柄
  sap_get_field_value: { sessionVariable: 'sap_session', saveToVariable: 'sap_value' },
  sap_get_status_message: { sessionVariable: 'sap_session', saveToVariable: 'sap_status_message' },
  sap_get_title: { sessionVariable: 'sap_session', saveToVariable: 'sap_title' },
  sap_read_gridview: { sessionVariable: 'sap_session', saveToVariable: 'sap_table_data' },
  sap_export_gridview_excel: { sessionVariable: 'sap_session' },

  // ==================== Webhook 请求 ====================
  webhook_request: {
    responseVariable: 'webhook_response', statusVariable: 'webhook_status',
    headersVariable: 'webhook_headers', cookiesVariable: 'webhook_cookies',
  },

  // ==================== 飞书 ====================
  feishu_bitable_read: { variableName: 'feishu_data' },
  feishu_sheet_read: { variableName: 'feishu_sheet_data' },

  // ==================== 文本/媒体识别 ====================

  // ==================== 任务 2.3 补登记：后端含非空默认内置变量的模块 ====================
  // 媒体格式转换 / 录屏
  audio_format_convert: { resultVariable: 'converted_audio' },
  batch_format_convert: { resultVariable: 'converted_files' },
  video_format_convert: { resultVariable: 'converted_video' },
  video_to_audio: { resultVariable: 'extracted_audio' },
  video_to_gif: { resultVariable: 'gif_path' },
  screen_record: { resultVariable: 'recording_path' },

  // 文件/文件夹操作
  copy_file: { resultVariable: 'copied_path' },
  move_file: { resultVariable: 'moved_path' },
  create_folder: { resultVariable: 'folder_path' },
  rename_folder: { resultVariable: 'new_folder_path' },
  file_exists: { resultVariable: 'exists' },
  write_text_file: { resultVariable: 'write_path' },

  // 桌面应用：appVariable=应用句柄变量、controlVariable=控件句柄变量、saveToVariable=输出
  desktop_app_close: { appVariable: 'desktop_app' },
  desktop_app_connect: { saveToVariable: 'desktop_app' },
  desktop_app_wait_ready: { appVariable: 'desktop_app' },
  desktop_assert_control: { controlVariable: 'desktop_control' },
  desktop_checkbox: { controlVariable: 'desktop_control' },
  desktop_click_control: { controlVariable: 'desktop_control' },
  desktop_drag_control: { controlVariable: 'desktop_control' },
  desktop_find_control: { appVariable: 'desktop_app', saveToVariable: 'desktop_control' },
  desktop_input_control: { controlVariable: 'desktop_control' },
  desktop_list_operate: { controlVariable: 'desktop_control', saveToVariable: 'list_result' },
  desktop_menu_click: { appVariable: 'desktop_app' },
  desktop_radio: { controlVariable: 'desktop_control' },
  desktop_scroll_control: { controlVariable: 'desktop_control' },
  desktop_select_combo: { controlVariable: 'desktop_control' },
  desktop_send_keys: { controlVariable: 'desktop_control' },
  desktop_set_value: { controlVariable: 'desktop_control' },
  desktop_window_activate: { appVariable: 'desktop_app' },
  desktop_window_move: { appVariable: 'desktop_app' },
  desktop_window_resize: { appVariable: 'desktop_app' },
  desktop_window_state: { appVariable: 'desktop_app' },
  desktop_window_topmost: { appVariable: 'desktop_app' },

  // QQ（NapCat）即时通讯查询类
  qq_get_friends: { resultVariable: 'qq_friends' },
  qq_get_group_members: { resultVariable: 'qq_group_members' },
  qq_get_groups: { resultVariable: 'qq_groups' },
  qq_get_login_info: { resultVariable: 'qq_login_info' },
  qq_wait_message: { resultVariable: 'qq_received_message' },

  // 分享 / 屏幕共享
  share_file: { resultVariable: 'share_url' },
  share_folder: { resultVariable: 'share_url' },
  start_screen_share: { resultVariable: 'screen_share_url' },

  // 其它（页面加载完成 / SAP 登录 / WPS 多维表读取）
  page_load_complete: { saveToVariable: 'page_loaded' },
  sap_login: { saveToVariable: 'sap_session' },
  wps_bitable_read: { variableName: 'wps_data' },

  // ==================== 补登记：Word 自动化 ====================
  // 后端 word_read_text / word_read_table 的 resultVariable 带非空默认值，
  // 即「创建即内置变量」，必须登记进来，否则补全列表看不到它们。
  word_read_text: { resultVariable: 'word_text' },
  word_read_table: { resultVariable: 'word_table' },

  // ==================== 补登记：桌面应用（应用/控件句柄变量）====================
  // desktop_app_start 的字段名以 addNode 为准：addNode 写的是 saveToVariable，
  // 这里曾错挂在 connectionVariable 上（取值相同但字段名不同），补全因此挂不上。
  desktop_app_start: { saveToVariable: 'desktop_app' },
  desktop_wait_control: { appVariable: 'desktop_app', saveToVariable: 'desktop_control' },

  // ==================== 补登记：SAP 会话句柄变量 ====================
  // 这一批模块都通过 sessionVariable 读取由 sap_login 建立的会话句柄，
  // 默认值统一为 sap_session，属于「创建即内置」的变量。
  sap_click_button: { sessionVariable: 'sap_session' },
  sap_close_warning: { sessionVariable: 'sap_session' },
  sap_logout: { sessionVariable: 'sap_session' },
  sap_maximize_window: { sessionVariable: 'sap_session' },
  sap_run_tcode: { sessionVariable: 'sap_session' },
  sap_select_combobox: { sessionVariable: 'sap_session' },
  sap_select_tab: { sessionVariable: 'sap_session' },
  sap_send_vkey: { sessionVariable: 'sap_session' },
  sap_set_checkbox: { sessionVariable: 'sap_session' },
  sap_set_field_value: { sessionVariable: 'sap_session' },
  sap_set_focus: { sessionVariable: 'sap_session' },

  // ==================== 以下条目由 addNode 事实源补齐（module-integrity-audit 任务 11） ====================
  // 取值一律以 workflowStore.ts 的 addNode 默认配置为准（设计决策 1）：addNode 决定运行时
  // 真实写入 node.data 的变量名，这里只是补全提示的兜底，必须与之一致，否则会产生幽灵变量。

  // ---------- AI 视觉与生成 ----------
  ai_element_selector: { variableName: 'element_selector' },
  ai_smart_scraper: { variableName: 'scraper_result' },

  // ---------- 桌面自动化控件操作 ----------
  desktop_control_info: {
    controlVariable: 'desktop_control',
    saveToVariable: 'control_info',
  },
  desktop_control_tree: {
    appVariable: 'desktop_app',
    saveToVariable: 'control_tree',
  },
  desktop_dialog_handle: { appVariable: 'desktop_app' },

  // ---------- 文档格式转换 ----------
  docx_to_html: { resultVariable: 'html_output' },
  docx_to_markdown: { resultVariable: 'markdown_output' },
  epub_to_markdown: { resultVariable: 'markdown_output' },
  html_to_docx: { resultVariable: 'docx_output' },
  html_to_markdown: { resultVariable: 'markdown_output' },
  latex_to_pdf: { resultVariable: 'pdf_output' },
  markdown_to_docx: { resultVariable: 'docx_output' },
  markdown_to_epub: { resultVariable: 'epub_output' },
  markdown_to_html: { resultVariable: 'html_output' },
  markdown_to_pdf: { resultVariable: 'pdf_output' },
  org_to_html: { resultVariable: 'html_output' },
  rst_to_html: { resultVariable: 'html_output' },
  universal_doc_convert: { resultVariable: 'convert_output' },

  // ---------- 网页与浏览器 ----------
  get_clipboard: { variableName: 'clipboard_content' },
  get_element_info: { variableName: 'element_value' },
  get_mouse_position: { variableName: 'mouse_pos' },
  get_time: { variableName: 'current_time' },

  // ---------- 其他 ----------
  hotkey_trigger: { saveToVariable: 'hotkey_data' },
  images_to_pdf: { resultVariable: 'pdf_result' },
  input_prompt: { variableName: 'user_input' },
  phone_pull_file: { variableName: 'phone_file_path' },
  phone_screenshot: { variableName: 'phone_screenshot_path' },
  qq_send_file: { resultVariable: 'qq_file_result' },
  qq_send_image: { resultVariable: 'qq_img_result' },
  qq_send_message: { resultVariable: 'qq_msg_result' },
  random_number: { variableName: 'random_num' },
  screenshot: { variableName: 'screenshot_path' },
  screenshot_screen: { variableName: 'screen_path' },
  set_variable: { variableName: 'my_var' },
  table_get_cell: { resultVariable: 'cell_value' },
  wechat_send_file: { resultVariable: 'wechat_file_result' },
  wechat_send_message: { resultVariable: 'wechat_msg_result' },

  // ---------- PDF 处理 ----------
  pdf_add_watermark: { resultVariable: 'watermarked_pdf' },
  pdf_compress: { resultVariable: 'compressed_pdf' },
  pdf_decrypt: { resultVariable: 'decrypted_pdf' },
  pdf_delete_pages: { resultVariable: 'result_pdf' },
  pdf_encrypt: { resultVariable: 'encrypted_pdf' },
  pdf_insert_pages: { resultVariable: 'result_pdf' },
  pdf_merge: { resultVariable: 'merged_pdf' },
  pdf_reorder_pages: { resultVariable: 'reordered_pdf' },
  pdf_rotate: { resultVariable: 'rotated_pdf' },
  pdf_split: { resultVariable: 'split_pdfs' },

}

/**
 * 获取某个模块某个字段的默认变量名
 * 找不到时返回 undefined
 */
export function getModuleDefaultVar(moduleType: string, field: string): string | undefined {
  return MODULE_DEFAULT_VARS[moduleType]?.[field]
}

/**
 * 获取某个模块所有定义的默认变量名（多个字段）
 */
export function getModuleAllDefaultVars(moduleType: string): Record<string, string> {
  return MODULE_DEFAULT_VARS[moduleType] || {}
}

/**
 * 权威「会产生变量的字段名」清单（唯一数据源）。
 *
 * 变量名输入框 / 变量引用补全 / 变量追踪等所有需要“从节点配置中提取已定义变量”
 * 的地方都应引用此清单，确保任何模块（含创建时即内置变量的模块）的变量都能被
 * 自动补全识别到，避免各处各自维护、出现遗漏。
 */
export const VARIABLE_NAME_FIELDS: string[] = [
  // 通用
  'variableName', 'resultVariable', 'outputVariable', 'targetVariable', 'dataVariable',
  'saveResult', 'saveToVariable',
  // 循环/遍历
  'itemVariable', 'indexVariable', 'loopIndexVariable', 'keyVariable', 'valueVariable',
  // 坐标
  'variableNameX', 'variableNameY',
  // 列表/字典/表格
  'listVariable', 'dictVariable', 'tableVariable',
  // 类型化结果
  'imageVariable', 'textVariable', 'urlVariable', 'fileVariable', 'sourceVariable',
  'responseVariable', 'cookieVariable', 'headerVariable', 'bodyVariable', 'statusVariable',
  'errorVariable', 'countVariable', 'sumVariable', 'avgVariable', 'maxVariable', 'minVariable',
  'connectionVariable', 'shareVariable', 'sessionVariable',
  // 注意单复数：后端实际用的是 headersVariable / cookiesVariable（复数），
  // 上面的 headerVariable / cookieVariable（单数）是历史写法，两者都要收，
  // 否则用户在这些字段改填自定义变量名后补全与变量追踪会漏掉。
  'headersVariable', 'cookiesVariable', 'exitCodeVariable',
  // Python 脚本
  'stdoutVariable', 'stderrVariable', 'returnCodeVariable',
  // 桌面自动化
  'appVariable', 'controlVariable',
  // 触发器/元素变化
  'saveNewElementSelector', 'saveChangeInfo', 'dataSource',
]


/**
 * 审计辅助：校验 MODULE_DEFAULT_VARS 中每个字段名都在 VARIABLE_NAME_FIELDS 白名单内。
 *
 * 背景：collectNodeVarNames 从「配置侧」提取已填变量名时，只认 VARIABLE_NAME_FIELDS
 * 白名单里的字段。如果某模块在 MODULE_DEFAULT_VARS 用了一个不在白名单内的字段名，
 * 那么当用户在该字段填了自定义变量名时（而非沿用默认名），补全/变量追踪就会漏掉它。
 * 因此「默认变量字段名必须全部收录进白名单」是内置变量补全完整性的硬约束。
 *
 * @returns 不在白名单内的 {type, field} 列表；为空表示全部合规（Property 6 通过）。
 */
export function findUnregisteredVarFields(): { type: string; field: string }[] {
  const whitelist = new Set<string>(VARIABLE_NAME_FIELDS)
  const result: { type: string; field: string }[] = []
  for (const [type, fields] of Object.entries(MODULE_DEFAULT_VARS)) {
    for (const field of Object.keys(fields)) {
      if (!whitelist.has(field)) {
        result.push({ type, field })
      }
    }
  }
  return result
}

/**
 * 收集一个节点在「创建时」应自动建立的变量名集合：
 *  1) 节点配置里已填写的变量名字段（VARIABLE_NAME_FIELDS）
 *  2) 该模块类型自带的默认变量名（MODULE_DEFAULT_VARS）——即使配置里尚未填，
 *     创建时也应内置（例如循环模块的 index、遍历模块的 item/index）。
 * 供流程图 addNode 与模块条创建路径共用，确保任何模块创建即在全局变量中建好自带变量。
 */
export function collectNodeVarNames(moduleType: string, data?: Record<string, unknown>): string[] {
  const names = new Set<string>()
  if (data) {
    for (const f of VARIABLE_NAME_FIELDS) {
      const v = (data as Record<string, unknown>)[f]
      if (typeof v === 'string' && v.trim()) names.add(v.trim())
    }
  }
  const defs = MODULE_DEFAULT_VARS[moduleType]
  if (defs) {
    for (const v of Object.values(defs)) {
      if (v && typeof v === 'string' && v.trim()) names.add(v.trim())
    }
  }
  return Array.from(names)
}
