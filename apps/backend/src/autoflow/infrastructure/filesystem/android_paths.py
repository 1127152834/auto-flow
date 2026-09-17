import os
from pathlib import Path


def android_runtime_root() -> Path:
    """Host-wide root: remains stable across workspace switches and sidecars."""
    configured = os.environ.get("AUTOFLOW_ANDROID_RUNTIME_ROOT")
    return Path(configured).resolve() if configured else Path.home() / ".autoflow" / "android-runtime"
