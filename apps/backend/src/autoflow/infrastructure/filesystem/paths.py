from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    data_dir: Path
    database: Path
    logs: Path
    workspace: Path
    cache: Path
    temp: Path
    profiles: Path
    kernels: Path

    @classmethod
    def from_data_dir(cls, root: Path) -> "AppPaths":
        root = Path(root)
        if not root.is_absolute():
            raise ValueError("data directory must be absolute")
        return cls(
            data_dir=root,
            database=root / "data" / "autoflow.sqlite3",
            logs=root / "logs",
            workspace=root / "workspace",
            cache=root / "cache",
            temp=root / "tmp",
            profiles=root / "workspace" / "profiles",
            kernels=root / "data" / "kernels",
        )
