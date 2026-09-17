from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from autoflow.infrastructure.database import session as database_session


def _config(database: Path) -> Config:
    config = Config(str(Path(database_session.__file__).with_name("alembic.ini")))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    return config


def test_studio_backend_history_has_one_merged_head(tmp_path: Path) -> None:
    scripts = ScriptDirectory.from_config(_config(tmp_path / "heads.sqlite3"))

    assert scripts.get_heads() == ["0013_merge_project_runtime"]
    assert scripts.get_revision("0013_merge_project_runtime").down_revision == (
        "0012_workflow_document_requests",
        "pm06_project_capability_reads",
    )
    assert scripts.get_revision("0011_merge_android_project_data").down_revision == (
        "0010_android_fleet",
        "0009_merge_project_data",
    )
    assert scripts.get_revision("0012_workflow_document_requests").down_revision == (
        "0011_merge_android_project_data"
    )


def test_restored_android_revisions_match_the_recorded_source_bytes() -> None:
    versions = Path(database_session.__file__).with_name("migrations") / "versions"
    expected = {
        "0007_android_devices.py": "03b1c995f0cf542b1f7db29181efb39e3f9e585ffb9012e1298795a6c209ed2d",
        "0008_merge_android_m4.py": "743ef6ed9cf442377e5b8bc300e58db247ae95aea75eb8b0a8caf158b3754e01",
        "0009_merge_android_m5.py": "0d56f34fc9d647896d7dd1ece2c8ff81aca163582b27b692b318053864a0de32",
        "0010_android_fleet.py": "9e49465c1f0db103273ab7c6cbbf810307caca0f1c883d3c2add41fdafa6507c",
    }

    import hashlib

    assert {
        name: hashlib.sha256((versions / name).read_bytes()).hexdigest()
        for name in expected
    } == expected
