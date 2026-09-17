from typing import Any


def android_definitions() -> list[dict[str, Any]]:
    result = []
    entries: list[tuple[str, str, dict[str, Any], dict[str, Any], int]] = [
        ("launch_app", "启动安卓应用", {"packageName": {"type": "string"}}, {"packageName": "com.android.settings"}, 30),
        ("tap", "点击安卓坐标", {key: {"type": "number"} for key in ("x", "y", "basisWidth", "basisHeight")}, {"x": 0, "y": 0, "basisWidth": 720, "basisHeight": 1280}, 15),
        ("key", "安卓系统按键", {"key": {"type": "string", "enum": ["HOME", "BACK", "ENTER", "APP_SWITCH"]}}, {"key": "BACK"}, 15),
        ("screenshot", "安卓截图", {"variableName": {"type": "string"}}, {"variableName": "android_screen"}, 15),
        ("manual", "人工处理安卓", {"prompt": {"type": "string"}}, {"prompt": "请完成操作后返回这里，点击完成并继续。"}, 600),
    ]
    for kind, title, properties, defaults, timeout in entries:
        result.append({"type": "android_" + kind, "title": title, "description": title,
                       "category": "安卓", "runnable": True,
                       "defaultConfig": {**defaults, "timeoutSeconds": timeout},
                       "configSchema": {"type": "object", "properties": {**properties, "timeoutSeconds": {"type": "number", "exclusiveMinimum": 0}}, "required": list(defaults), "additionalProperties": False},
                       "inputPorts": ["in"], "outputPorts": ["out"]})
    return result
