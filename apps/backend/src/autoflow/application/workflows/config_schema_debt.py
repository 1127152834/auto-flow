"""Panel fields the executor does not read yet (remediation M2 R2-11 debt baseline).

Frozen from the Studio field inventory; tests/unit/workflows/test_config_schema.py fails when an entry
is added or becomes stale, so this list only shrinks. They are known panel fields, so preflight does
not report them as unknown keys; rule 1 of the remediation still requires removing or reading them.
"""

PANEL_ONLY_KEYS: dict[str, frozenset[str]] = {
    "ai_chat": frozenset({"apiKey", "apiUrl", "model"}),
    "ai_classify": frozenset({"fields", "inputList", "maxWords", "normalizeType", "routes", "style", "targetFormat", "targetLang"}),
    "ai_dedup_semantic": frozenset({"categories", "fields", "inputText", "maxWords", "normalizeType", "routes", "style", "targetFormat", "targetLang"}),
    "ai_element_selector": frozenset({"apiKey", "apiUrl", "azureEndpoint", "llmModel", "llmProvider", "verbose"}),
    "ai_extract": frozenset({"categories", "inputList", "maxWords", "normalizeType", "routes", "style", "targetFormat", "targetLang"}),
    "ai_generate_image": frozenset({"ai", "apiBase", "apiKey", "model"}),
    "ai_generate_video": frozenset({"ai", "apiBase", "apiKey", "apiUrl"}),
    "ai_normalize": frozenset({"categories", "fields", "inputList", "maxWords", "routes", "style", "targetLang"}),
    "ai_route": frozenset({"categories", "fields", "inputList", "maxWords", "normalizeType", "style", "targetFormat", "targetLang"}),
    "ai_sentiment": frozenset({"categories", "fields", "inputList", "maxWords", "normalizeType", "routes", "style", "targetFormat", "targetLang"}),
    "ai_smart_scraper": frozenset({"apiKey", "apiUrl", "azureEndpoint", "headless", "llmModel", "llmProvider", "verbose"}),
    "ai_summarize": frozenset({"categories", "fields", "inputList", "normalizeType", "routes", "targetFormat", "targetLang"}),
    "ai_translate": frozenset({"categories", "fields", "inputList", "maxWords", "normalizeType", "routes", "style", "targetFormat"}),
    "ai_vision": frozenset({"apiKey", "apiUrl", "model"}),
    "ai_vision_act": frozenset({"apiKey", "apiUrl", "model"}),
    "allure_add_attachment": frozenset({"attachmentType"}),
    "allure_init": frozenset({"clean", "resultsDir"}),
    "api_trigger": frozenset({"apiTrigger"}),
    "element_change_trigger": frozenset({"checkInterval"}),
    "element_exists": frozenset({"leftValue"}),
    "element_visible": frozenset({"leftValue"}),
    "email_trigger": frozenset({"emailTrigger"}),
    "file_watcher_trigger": frozenset({"fileTrigger"}),
    "group": frozenset({"color"}),
    "network_capture": frozenset({"proxyPort", "targetPorts", "targetProcess"}),
    "note": frozenset({"content"}),
    "scheduled_task": frozenset({"taskName"}),
    "ssh_connect": frozenset({"ssh"}),
}

# Fields the editor adds to a new node that the executor does not read; the Studio test
# unknown-config-keys.test.ts fails when this differs from what a new node really contains.
EDITOR_DEFAULT_KEYS: dict[str, frozenset[str]] = {
    "ai_chat": frozenset({"resultVariable"}),
    "api_request": frozenset({"resultVariable"}),
    "base64": frozenset({"resultVariable"}),
    "dict_get": frozenset({"resultVariable"}),
    "dict_keys": frozenset({"resultVariable"}),
    "dict_operation": frozenset({"resultVariable"}),
    "hotkey_trigger": frozenset({"saveToVariable"}),
    "image_ocr": frozenset({"language"}),
    "json_parse": frozenset({"resultVariable"}),
    "list_get": frozenset({"resultVariable"}),
    "list_length": frozenset({"resultVariable"}),
    "network_capture": frozenset({"resultVariable"}),
    "regex_extract": frozenset({"resultVariable"}),
    "run_command": frozenset({"resultVariable"}),
    "string_case": frozenset({"resultVariable"}),
    "string_concat": frozenset({"resultVariable"}),
    "string_join": frozenset({"resultVariable"}),
    "string_replace": frozenset({"resultVariable"}),
    "string_split": frozenset({"resultVariable"}),
    "string_substring": frozenset({"resultVariable"}),
    "string_trim": frozenset({"resultVariable"}),
    "table_get_cell": frozenset({"resultVariable"}),
}
