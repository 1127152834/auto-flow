from typing import Any


def preview_cleanup(resources: list[dict[str, Any]], workspace_identity: str) -> list[dict[str, Any]]:
    return [{"id": item["id"], "purpose": item.get("purpose", "android"), "size": item.get("size", 0), "reversible": False} for item in resources if item.get("workspaceId") == workspace_identity]
